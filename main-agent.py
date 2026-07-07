"""
main-agent.py — 命令行交互式 AI 智能体入口

基于 LLM（大语言模型）的多轮对话智能体，支持：
  - 自动加载 tools/ 目录下的工具函数
  - 多工具并行调用（保持提交顺序）
  - 连续错误熔断机制
  - 用户记忆系统（可选）
  - 对话历史自动清理

用法:
    python main-agent.py          # 交互式对话
    输入 exit / quit 退出
"""

import concurrent.futures
import importlib
import inspect
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

# ────────────────────────── 日志配置 ──────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("agent")

# ────────────────────────── 记忆系统加载 ──────────────────────────

MEMORY_ENABLED: bool = True

try:
    from tools.memory_tool import (
        read_user_memory,
        update_user_memory,
        list_memory_categories,
        consolidate_memory_summary,
    )
    logger.info("记忆系统已加载")
except ImportError as e:
    MEMORY_ENABLED = False
    logger.warning("记忆系统加载失败: %s，记忆功能已禁用", e)


# ────────────────────────── 配置常量 ──────────────────────────

MAX_TURNS: int = 100                 # 单次对话最大工具调用轮数
MAX_HISTORY_MESSAGES: int = 12       # 保留的最近消息数量
MAX_CONSECUTIVE_ERRORS: int = 3      # 连续错误熔断阈值
TOOL_CALL_DELAY: float = 0.3         # 工具调用后等待间隔（秒）


# ────────────────────────── 工具加载 ──────────────────────────

def load_tools_config(file_path: str) -> List[Dict[str, Any]]:
    """从 JSON 文件加载工具配置（Function Calling 格式）。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("工具配置文件 '%s' 不存在", file_path)
        return []
    except json.JSONDecodeError as e:
        logger.error("工具配置文件 JSON 解析失败: %s", e)
        return []
    except Exception as e:
        logger.error("加载工具配置失败: %s", e)
        return []


def auto_load_tool_functions(tools_dir: str = "tools") -> Dict[str, Callable]:
    """自动扫描并加载 tools/ 目录下的所有公开函数。

    加载规则:
      - 文件名不以下划线开头
      - 函数定义在模块自身（不导入自其他模块）
      - 函数名不以下划线开头
    """
    registry: Dict[str, Callable] = {}

    if not os.path.isdir(tools_dir):
        logger.warning("工具目录 '%s' 不存在", tools_dir)
        return registry

    for file_name in sorted(os.listdir(tools_dir)):
        if not file_name.endswith(".py") or file_name.startswith("_"):
            continue

        module_name = file_name[:-3]
        try:
            module = importlib.import_module(f"{tools_dir}.{module_name}")
            functions = inspect.getmembers(module, inspect.isfunction)

            for func_name, func_obj in functions:
                # 仅加载模块自身定义的公开函数
                if func_obj.__module__ == module.__name__ and not func_name.startswith("_"):
                    registry[func_name] = func_obj
                    logger.info("已加载工具: %s (来自 %s)", func_name, module_name)

        except Exception as e:
            logger.error("加载模块 '%s' 失败: %s", module_name, e)

    return registry


# ────────────────────────── 系统提示词 ──────────────────────────

def load_system_prompt(file_path: str, variables: Optional[Dict[str, str]] = None) -> str:
    """从 Markdown 文件加载系统提示词，支持变量替换。

    Args:
        file_path: Markdown 提示词文件路径
        variables: 模板变量字典，如 {'project_root': '/path'}

    Returns:
        替换变量后的提示词字符串
    """
    if not os.path.exists(file_path):
        logger.warning("提示词文件 '%s' 不存在，使用默认提示词", file_path)
        return "你是一个专业的 AI 助手，能够根据用户的请求调用工具并提供帮助。"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if variables:
            for key, value in variables.items():
                placeholder = f"{{{{{key}}}}}"
                content = content.replace(placeholder, str(value))

        return content

    except Exception as e:
        logger.error("读取提示词文件失败: %s", e)
        return "你是一个专业的智能助手。"


def append_memory_context(system_prompt: str) -> str:
    """将用户记忆摘要注入系统提示词末尾。

    Args:
        system_prompt: 基础系统提示词

    Returns:
        附加了记忆上下文的提示词
    """
    if not MEMORY_ENABLED:
        return system_prompt

    try:
        summary = consolidate_memory_summary()
        if not summary or "暂无用户记忆数据" in summary:
            logger.info("暂无用户记忆数据，跳过注入")
            return system_prompt

        memory_block = (
            "\n\n---\n\n"
            "## 用户记忆（个性化上下文）\n\n"
            "以下是对当前用户的历史记忆，请据此调整回复风格与行为偏好：\n\n"
            f"{summary}\n\n"
            "**使用规则：**\n"
            "- 若记忆与当前输入冲突，以当前输入为准，并调用 update_user_memory 更新\n"
            "- 发现新的用户偏好或信息时，主动调用 update_user_memory 记录\n"
        )
        logger.info("已注入用户记忆上下文")
        return system_prompt + memory_block

    except Exception as e:
        logger.warning("注入记忆上下文失败: %s", e)
        return system_prompt


# ────────────────────────── 工具执行 ──────────────────────────

def is_error_result(text: str) -> bool:
    """判断工具执行结果是否为错误。

    检查结果中是否包含错误状态标记，而非依赖自然语言文本匹配。
    """
    error_markers = [
        "[ERROR]", "[STATUS: FAILED]", "[STATUS: SECURITY_DENIED]",
        "[STATUS: TIMEOUT_ERROR]", "[STATUS: UNRESOLVABLE]",
    ]
    return any(marker in text for marker in error_markers)


def execute_tool(tool_call: Any, available_tools: Dict[str, Callable]) -> Dict[str, Any]:
    """执行单个工具调用并返回统一格式的结果。

    Args:
        tool_call: LLM 返回的工具调用对象
        available_tools: 可用工具函数注册表

    Returns:
        {'result_dict': {...}, 'is_success': bool}
    """
    f_name = tool_call.function.name
    f_id = tool_call.id

    # ── 解析参数 ──
    try:
        f_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        return {
            "result_dict": {
                "role": "tool",
                "tool_call_id": f_id,
                "name": f_name,
                "content": f"[ERROR] 工具参数不是有效的 JSON: {e}",
            },
            "is_success": False,
        }

    # ── 查找并执行工具 ──
    if f_name not in available_tools:
        return {
            "result_dict": {
                "role": "tool",
                "tool_call_id": f_id,
                "name": f_name,
                "content": f"[ERROR] 工具 '{f_name}' 未注册。可用工具: {', '.join(available_tools.keys())}",
            },
            "is_success": False,
        }

    tool_function = available_tools[f_name]
    try:
        res = tool_function(**f_args)
        is_success = not is_error_result(str(res))
    except TypeError as e:
        res = f"[ERROR] 工具参数不匹配: {e}"
        is_success = False
    except Exception as e:
        logger.exception("工具 '%s' 执行异常", f_name)
        res = f"[ERROR] 工具执行异常: {e}"
        is_success = False

    return {
        "result_dict": {
            "role": "tool",
            "tool_call_id": f_id,
            "name": f_name,
            "content": str(res),
        },
        "is_success": is_success,
    }


# ────────────────────────── 消息管理 ──────────────────────────

def purify_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """清理对话历史，保留 system、user 和纯文本 assistant 消息。

    移除带 tool_calls 的 assistant 消息和所有 tool 消息，
    因为这些中间过程不应占据上下文窗口。
    """
    purified: List[Dict[str, Any]] = []
    for msg in messages:
        # 兼容 dict 和 object 两种格式
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
        else:
            role = getattr(msg, "role", "")
            content = getattr(msg, "content", "")
            tool_calls = getattr(msg, "tool_calls", None)

        # system 和 user 消息始终保留
        if role in ("system", "user"):
            purified.append({"role": role, "content": content})
            continue

        # assistant 消息仅保留纯文本（无 tool_calls）
        if role == "assistant" and not tool_calls and content:
            purified.append({"role": role, "content": content})

    return purified


def enforce_message_limit(messages: List[Dict[str, Any]],
                          max_count: int = MAX_HISTORY_MESSAGES) -> List[Dict[str, Any]]:
    """限制对话历史长度，始终保留 system prompt。

    Args:
        messages: 消息列表
        max_count: 最大保留消息数

    Returns:
        截断后的消息列表
    """
    if len(messages) <= max_count:
        return messages

    # system prompt 始终保留
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    # 保留最近的消息
    keep_count = max_count - len(system_msgs)
    kept = other_msgs[-keep_count:] if keep_count > 0 else []

    logger.info("对话历史过长，已清理为最近的 %d 条消息", max_count)
    return system_msgs + kept


# ────────────────────────── LLM 客户端 ──────────────────────────

class LLMClient:
    """兼容 OpenAI API 的大语言模型客户端封装。"""

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, messages: List[Dict[str, Any]],
                 tools: Optional[List[Dict[str, Any]]] = None) -> Optional[Any]:
        """调用 LLM API 生成回复。

        Args:
            messages: 对话消息列表
            tools: Function Calling 工具定义（可选）

        Returns:
            LLM 回复消息对象，失败返回 None
        """
        logger.info("正在调用 LLM API (model=%s)...", self.model)
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "temperature": 0.1,
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message

        except Exception as e:
            logger.error("LLM API 调用失败: %s", e)
            return None


# ────────────────────────── 主对话循环 ──────────────────────────

def run_conversation_loop(llm: LLMClient,
                          messages: List[Dict[str, Any]],
                          tools_config: List[Dict[str, Any]],
                          available_tools: Dict[str, Callable]) -> None:
    """运行交互式多轮对话循环。

    Args:
        llm: LLM 客户端实例
        messages: 初始消息列表（含 system prompt）
        tools_config: 工具定义配置
        available_tools: 已注册的工具函数
    """
    print("\n" + "=" * 60)
    print("  Easy Agents — 命令行智能助手")
    print("  输入 exit / quit 退出")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("再见！")
            break

        # ── 清理对话历史 ──
        messages = purify_messages(messages)
        messages = enforce_message_limit(messages)

        # ── 添加用户消息 ──
        messages.append({"role": "user", "content": user_input})

        # ── 多轮工具调用循环 ──
        turn = 0
        consecutive_errors = 0
        final_response = ""
        tools_used: List[str] = []

        while turn < MAX_TURNS:
            turn += 1
            print(f"\n  [思考中... 第 {turn} 轮]")

            llm_response = llm.generate(messages=messages, tools=tools_config)

            if llm_response is None:
                print("  [错误] LLM API 调用失败，对话终止。")
                break

            messages.append(llm_response)

            # ── 无工具调用 → 最终文本回复 ──
            if not llm_response.tool_calls:
                final_response = llm_response.content or ""
                print(f"\nAI: {final_response}")
                break

            # ── 并行执行工具调用 ──
            tool_count = len(llm_response.tool_calls)
            print(f"  [工具] 正在执行 {tool_count} 个工具...")

            # 使用 ThreadPoolExecutor 并行执行，保持提交顺序
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 提交所有任务，记录索引
                futures = [
                    (i, executor.submit(execute_tool, tc, available_tools))
                    for i, tc in enumerate(llm_response.tool_calls)
                ]
                # 按提交顺序收集结果（不是完成顺序）
                tool_results: List[Dict[str, Any]] = [
                    future.result() for _, future in futures
                ]

            # ── 处理工具结果 ──
            for output in tool_results:
                result = output["result_dict"]
                tool_name = result["name"]
                content_preview = result["content"][:80].replace("\n", " ")

                print(f"  [{tool_name}] {content_preview}...")
                messages.append(result)

                # 统计工具使用（排除记忆系统内部工具）
                if tool_name not in (
                    "read_user_memory", "list_memory_categories",
                    "consolidate_memory_summary", "update_user_memory",
                ):
                    tools_used.append(tool_name)

                # 追踪连续错误
                if not output["is_success"]:
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0

            # ── 熔断检测 ──
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"\n  [熔断] 工具连续失败 {MAX_CONSECUTIVE_ERRORS} 次，强制终止工具链。")
                messages.append({
                    "role": "user",
                    "content": (
                        "系统提示：底层工具链持续返回错误。"
                        "请停止尝试调用工具，直接向用户说明任务无法完成的原因。"
                    ),
                })
                # 给模型一次最终回复机会
                final_llm = llm.generate(messages=messages, tools=None)
                if final_llm and final_llm.content:
                    final_response = final_llm.content
                    print(f"\nAI: {final_response}")
                break

            time.sleep(TOOL_CALL_DELAY)

        else:
            # while 循环正常结束（达到最大轮数）而非 break
            print(f"\n  [提示] 达到最大对话轮数 ({MAX_TURNS})，对话终止。")

        # ── 自动更新用户记忆 ──
        _auto_update_memory(user_input, tools_used)

    print("\n会话结束。\n")


def _auto_update_memory(user_input: str, tools_used: List[str]) -> None:
    """根据本轮对话自动更新用户记忆。

    Args:
        user_input: 用户本轮输入
        tools_used: 本轮使用的工具列表
    """
    if not MEMORY_ENABLED or not tools_used:
        return

    try:
        unique_tools = list(set(tools_used))
        history_entry = (
            f"- 用户需求: {user_input[:100]}\n"
            f"- 使用工具: {', '.join(unique_tools)}"
        )
        update_user_memory("history", history_entry)

        tech_entry = f"- 用户使用工具: {', '.join(unique_tools)}"
        update_user_memory("knowledge", tech_entry)

        logger.info("已自动更新用户记忆")
    except Exception as e:
        logger.warning("自动更新记忆失败: %s", e)


# ────────────────────────── 入口 ──────────────────────────

def main() -> None:
    """主入口函数。"""
    # ── 环境变量 ──
    API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    MODEL_ID = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

    if not API_KEY:
        print("[警告] 未设置 DEEPSEEK_API_KEY 环境变量")
        print("请运行: export DEEPSEEK_API_KEY='your-key'")
        # 不直接退出，允许用户从环境或其他方式获得 key

    # ── PaddleOCR 相关环境变量 ──
    os.environ.setdefault('PADDLE_PDX_HOME',
                          os.path.join(os.path.dirname(__file__), ".paddlex"))
    os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', "True")

    # ── 加载工具 ──
    tools_config = load_tools_config("tool_configure.json")
    available_tools = auto_load_tool_functions("tools")

    if not available_tools:
        print("[警告] 未加载到任何工具函数，请检查 tools/ 目录")

    print(f"[系统] 已加载 {len(available_tools)} 个工具函数")
    print(f"[系统] 已加载 {len(tools_config)} 个工具定义")

    # ── 初始化 LLM ──
    llm = LLMClient(model=MODEL_ID, api_key=API_KEY, base_url=BASE_URL)

    # ── 构建系统提示词 ──
    project_root = os.path.abspath(os.path.dirname(__file__))
    system_vars = {
        "env_version": f"Python {sys.version_info.major}.{sys.version_info.minor}",
        "project_root": project_root,
    }

    base_prompt = load_system_prompt("EasyAgent.md", variables=system_vars)
    system_prompt = append_memory_context(base_prompt)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]

    # ── 启动对话循环 ──
    run_conversation_loop(llm, messages, tools_config, available_tools)


if __name__ == "__main__":
    main()
