"""
main-window.py — AI 智能体可视化工作台

基于 PySide6 的暗黑科技风 GUI，VS Code 双栏布局：
  左侧: 工具面板（工具树 + 状态信息 + 操作按钮）
  右侧: 聊天区域（消息显示 + 输入框 + 发送按钮）

特性:
  - 斜杠命令 (/clear, /tools, /status, /exit)
  - 异步 LLM 调用（不阻塞 UI）
  - 工具调用实时展示
  - 连续错误自动熔断
  - API 配置持久化（agent_config.json）

依赖:
    pip install PySide6 openai

运行:
    python main-window.py
"""

import concurrent.futures
import importlib
import inspect
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QThread, Signal, QEvent, QTimer
from PySide6.QtGui import (
    QFont, QColor, QTextCursor, QKeyEvent, QPixmap, QPainter,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSplitter,
    QTreeWidget, QTreeWidgetItem, QGroupBox,
    QStatusBar, QMessageBox, QGridLayout, QTextBrowser,
    QFrame, QScrollBar, QListWidget, QListWidgetItem,
)
from openai import OpenAI

# ────────────────────────── 日志 ──────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("gui")


# ════════════════════════════════════════════════════════════
#  样式表 — 精致暗黑风 (VS Code 色彩体系)
# ════════════════════════════════════════════════════════════

STYLE_SHEET = """
/* ── 全局基础 ── */
QMainWindow { background-color: #1a1b1e; }
QWidget {
    background-color: #1a1b1e;
    color: #c9d1d9;
    font-family: "Microsoft YaHei", -apple-system, "Segoe UI", "Consolas", sans-serif;
}

/* ── 侧边栏 ── */
QFrame#SidePanel {
    background-color: #151618;
    border-right: 1px solid #2d2e31;
}
QLabel#SideTitle {
    color: #8b949e; font-size: 11px; font-weight: bold;
    letter-spacing: 0.5px; text-transform: uppercase;
    padding: 12px 14px 6px 14px; background: transparent;
}
QLabel#SideItem {
    color: #c9d1d9; font-size: 13px; padding: 7px 14px;
    background: transparent; border-radius: 4px;
}
QLabel#SideItem:hover { background-color: #1f2023; color: #58a6ff; }
QLabel#SideItemActive {
    color: #58a6ff; font-size: 13px; padding: 7px 14px;
    background: #1f2023; border-left: 2px solid #58a6ff;
    border-radius: 0 4px 4px 0;
}
QLabel#SideSection {
    color: #8b949e; font-size: 10px; font-weight: bold;
    letter-spacing: 1px; text-transform: uppercase;
    padding: 16px 14px 4px 14px; background: transparent;
}
QFrame#SideDivider {
    background-color: #2d2e31; max-height: 1px; margin: 4px 14px;
}

/* ── 顶部系统状态栏 ── */
QLabel#SystemStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1c1d20, stop:1 #151618);
    color: #8b949e; font-size: 11px; padding: 5px 16px;
    border-bottom: 1px solid #2d2e31;
    font-family: "Consolas", "Microsoft YaHei", monospace;
}

/* ── 聊天消息区 ── */
QTextBrowser#ChatDisplay {
    background-color: #1a1b1e; color: #c9d1d9; font-size: 14px;
    border: none; padding: 16px 20px;
    selection-background-color: #1f3a5f;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}

/* ── 输入框 ── */
QTextEdit#InputEdit {
    background-color: #212226; color: #c9d1d9; font-size: 13.5px;
    border: 1px solid #343539; border-radius: 8px; padding: 10px 16px;
    selection-background-color: #1f3a5f;
    font-family: "Microsoft YaHei", "Consolas", sans-serif;
}
QTextEdit#InputEdit:focus { border-color: #58a6ff; background-color: #1c1d20; }
QTextEdit#InputEdit:disabled { background-color: #1a1b1e; color: #484f58; }

/* ── 发送按钮 ── */
QPushButton#BtnSend {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #238636, stop:1 #1e7a30);
    color: #FFFFFF; font-size: 13px; font-weight: bold;
    border: none; border-radius: 8px; padding: 8px 20px; min-width: 72px;
}
QPushButton#BtnSend:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2ea043, stop:1 #238636);
}
QPushButton#BtnSend:pressed { background-color: #1a6a2a; }
QPushButton#BtnSend:disabled { background: #2d2e31; color: #484f58; }

/* ── 辅助按钮 ── */
QPushButton#BtnTool {
    background-color: #212226; color: #8b949e; font-size: 12px;
    border: 1px solid #343539; border-radius: 6px;
    padding: 6px 14px; min-width: 50px;
}
QPushButton#BtnTool:hover {
    background-color: #2d2e31; border-color: #58a6ff; color: #c9d1d9;
}
QPushButton#BtnTool:pressed { background-color: #1a1b1e; }
QPushButton#BtnTool:checked {
    background-color: #1f3a5f; border-color: #58a6ff; color: #58a6ff;
}

/* ── 底部栏 ── */
QLabel#FooterLabel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #151618, stop:1 #1a1b1e);
    color: #484f58; font-size: 11px; padding: 3px 16px;
    border-top: 1px solid #2d2e31; font-family: "Consolas", monospace;
}

/* ── 滚动条 ── */
QScrollBar:vertical { background-color: transparent; width: 8px; border: none; }
QScrollBar::handle:vertical {
    background-color: #343539; border-radius: 4px;
    min-height: 30px; margin: 2px;
}
QScrollBar::handle:vertical:hover { background-color: #484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background-color: transparent; height: 8px; border: none; }
QScrollBar::handle:horizontal {
    background-color: #343539; border-radius: 4px;
    min-width: 30px; margin: 2px;
}
QScrollBar::handle:horizontal:hover { background-color: #484f58; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

/* ── 树形控件 ── */
QTreeWidget {
    background-color: transparent; color: #c9d1d9;
    font-size: 12px; border: none; outline: none;
}
QTreeWidget::item { padding: 4px 8px; border-radius: 4px; }
QTreeWidget::item:hover { background-color: #1f2023; }
QTreeWidget::item:selected { background-color: #1f3a5f; color: #58a6ff; }

/* ── 输入容器 ── */
QWidget#InputContainer {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1e1f22, stop:1 #1a1b1e);
    border-top: 1px solid #2d2e31; padding: 10px 16px;
}

/* ── 设置按钮 ── */
QPushButton#BtnSettings {
    background-color: transparent; color: #8b949e; font-size: 12px;
    border: 1px solid #343539; border-radius: 6px; padding: 4px 12px;
}
QPushButton#BtnSettings:hover {
    background-color: #212226; border-color: #58a6ff; color: #c9d1d9;
}
"""


# ════════════════════════════════════════════════════════════
#  工具加载模块
# ════════════════════════════════════════════════════════════

def load_tools_config(file_path: str) -> List[Dict[str, Any]]:
    """从 JSON 文件加载 Function Calling 工具定义。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error("加载工具配置失败: %s", e)
        return []


def auto_load_tool_functions(tools_dir: str = "tools") -> Dict[str, Callable]:
    """自动扫描 tools/ 目录加载所有公开函数。"""
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
            for func_name, func_obj in inspect.getmembers(module, inspect.isfunction):
                if func_obj.__module__ == module.__name__ and not func_name.startswith("_"):
                    registry[func_name] = func_obj
                    logger.info("[工具] 已加载: %s", func_name)
        except Exception as e:
            logger.error("加载模块 '%s' 失败: %s", module_name, e)
    return registry


# 全局单例
_TOOLS_CONFIG = load_tools_config("tool_configure.json")
_AVAILABLE_TOOLS = auto_load_tool_functions("tools")


def execute_tool(tool_call: Any, available_tools: Dict[str, Callable]) -> Dict[str, Any]:
    """执行单个工具调用并返回统一格式结果。

    Returns:
        {'result_dict': {...}, 'is_success': bool}
    """
    f_name = tool_call.function.name
    f_id = tool_call.id

    # 解析参数
    try:
        f_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        return {
            "result_dict": {
                "role": "tool", "tool_call_id": f_id,
                "name": f_name,
                "content": f"[ERROR] 参数 JSON 解析失败: {e}",
            },
            "is_success": False,
        }

    if f_name not in available_tools:
        return {
            "result_dict": {
                "role": "tool", "tool_call_id": f_id,
                "name": f_name,
                "content": f"[ERROR] 工具 '{f_name}' 不可用",
            },
            "is_success": False,
        }

    tool_func = available_tools[f_name]
    try:
        res = tool_func(**f_args)
        error_markers = ["[ERROR]", "[STATUS: FAILED]", "[STATUS: SECURITY_DENIED]",
                         "[STATUS: TIMEOUT_ERROR]", "[STATUS: UNRESOLVABLE]"]
        is_success = not any(m in str(res) for m in error_markers)
    except Exception as e:
        res = f"[ERROR] 工具执行异常: {e}"
        is_success = False

    return {
        "result_dict": {
            "role": "tool", "tool_call_id": f_id,
            "name": f_name, "content": str(res),
        },
        "is_success": is_success,
    }


# ════════════════════════════════════════════════════════════
#  LLM 后台工作线程
# ════════════════════════════════════════════════════════════

class LLMWorker(QThread):
    """异步 LLM 调用线程 — 不阻塞 UI。"""

    # 信号定义
    status_update = Signal(str)        # 状态更新
    tool_called = Signal(str, str, str)  # 工具名, 参数, 结果
    ai_message = Signal(str)           # AI 文本回复
    error_occurred = Signal(str)       # 错误信息
    finished_one_round = Signal()      # 本轮结束

    def __init__(self, api_key: str, base_url: str, model: str,
                 messages: list, tools_config: list,
                 available_tools: dict, max_turns: int = 30):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.messages = messages
        self.tools_config = tools_config
        self.available_tools = available_tools
        self.max_turns = max_turns
        self._running = True

    def stop(self) -> None:
        """请求停止线程。"""
        self._running = False

    def run(self) -> None:
        """线程主函数 — 执行多轮对话。"""
        if not self.api_key:
            self.error_occurred.emit("API Key 未设置！请在设置中配置。")
            self.finished_one_round.emit()
            return

        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            self.error_occurred.emit(f"OpenAI 客户端初始化失败: {e}")
            self.finished_one_round.emit()
            return

        turn = 0
        consecutive_errors = 0

        while turn < self.max_turns and self._running:
            turn += 1
            self.status_update.emit(f"[思考] Agent 分析中... (第 {turn} 轮)")

            # ── 调用 LLM API ──
            try:
                kwargs: Dict[str, Any] = {
                    "model": self.model,
                    "messages": self.messages,
                    "stream": False,
                    "temperature": 0.1,
                }
                if self.tools_config:
                    kwargs["tools"] = self.tools_config

                response = client.chat.completions.create(**kwargs)
                llm_response = response.choices[0].message

            except Exception as e:
                self.error_occurred.emit(f"API 调用失败: {e}")
                break

            if llm_response is None:
                self.error_occurred.emit("模型返回为空")
                break

            self.messages.append(llm_response)

            # ── 有工具调用 → 并行执行 ──
            if llm_response.tool_calls:
                tool_count = len(llm_response.tool_calls)
                self.status_update.emit(
                    f"[工具] 激活 {tool_count} 个工具..."
                )

                # 并行执行，按提交顺序收集结果（非完成顺序）
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    indexed_futures = [
                        (i, executor.submit(execute_tool, tc, self.available_tools))
                        for i, tc in enumerate(llm_response.tool_calls)
                    ]
                    tool_results = [
                        future.result() for _, future in indexed_futures
                    ]

                for tc, output in zip(llm_response.tool_calls, tool_results):
                    result = output["result_dict"]
                    tool_name = result["name"]
                    tc_params = tc.function.arguments

                    self.tool_called.emit(tool_name, tc_params, result["content"])
                    self.messages.append(result)

                    if not output["is_success"]:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                # ── 熔断 ──
                if consecutive_errors >= 3:
                    self.status_update.emit(
                        "[熔断] 工具连续出错！Agent 终止工具链。"
                    )
                    fault_report = (
                        "--- 任务失败报告 ---\n"
                        "底层工具链持续返回错误。请检查:\n"
                        "  1. 第三方依赖是否完整\n"
                        "  2. 配置文件路径是否正确\n"
                        "  3. API 或网络连接是否正常\n"
                        "---------------------"
                    )
                    self.ai_message.emit(
                        f'<div style="color:#f85149;background:#2d1b1b;'
                        f'padding:12px;border:1px solid #f85149;'
                        f'border-radius:6px;font-family:Consolas;'
                        f'white-space:pre-wrap;">{fault_report}</div>'
                    )
                    self.messages.append({
                        "role": "user",
                        "content": (
                            "系统提示：工具链持续返回错误。"
                            "请停止调用工具，直接向用户说明原因。"
                        ),
                    })

                time.sleep(0.3)
                continue

            else:
                # ── 无工具调用 → 最终文字回复 ──
                final_text = llm_response.content or ""
                self.ai_message.emit(final_text)
                self.status_update.emit("[完成] 回复已生成")
                break

        else:
            self.status_update.emit(
                f"[提示] 达到最大轮数 ({self.max_turns})"
            )

        self.finished_one_round.emit()


# ════════════════════════════════════════════════════════════
#  主窗口 — VS Code 风格双栏布局
# ════════════════════════════════════════════════════════════

class AgentWindow(QMainWindow):
    """AI 智能体可视化工作台主窗口。"""

    # ── 常量 ──
    DEFAULT_CONFIG: Dict[str, Any] = {
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "max_turns": 30,
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agent Studio — 本地自主 Agent")
        self.setMinimumSize(1000, 720)
        self.resize(1280, 840)

        # 对话状态
        self.messages: List[Dict[str, Any]] = []
        self._init_system_message()

        # 工作线程
        self.worker: Optional[LLMWorker] = None

        # 配置
        self.config_data = self._load_config()

        # UI
        self._setup_ui()
        self._update_status_bar()

        # 输入锁
        self.is_waiting = False

        # 居中
        self._center_on_screen()

    # ────────────────────────────────────────────────
    #  系统消息初始化
    # ────────────────────────────────────────────────

    def _init_system_message(self) -> None:
        self.messages = [{
            "role": "system",
            "content": (
                "你是一个智能助手，能根据用户请求调用工具并提供帮助。"
                "请用中文回复，保持简洁专业。"
            ),
        }]

    # ────────────────────────────────────────────────
    #  配置管理
    # ────────────────────────────────────────────────

    def _load_config(self) -> Dict[str, Any]:
        """加载配置（agent_config.json / 环境变量）。"""
        config = dict(self.DEFAULT_CONFIG)
        config["api_key"] = os.environ.get("DEEPSEEK_API_KEY", "")

        config_path = "agent_config.json"
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    config.update(saved)
        except Exception:
            pass

        return config

    def _save_config(self) -> None:
        """保存配置到文件。"""
        try:
            with open("agent_config.json", 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"无法保存配置: {e}")

    # ────────────────────────────────────────────────
    #  UI 构建
    # ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """构建主界面。"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ① 顶部状态栏
        self._build_system_status(main_layout)

        # ② 双栏主体
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        self._build_side_panel(splitter)          # 左侧
        splitter.addWidget(self._build_main_area())  # 右侧
        splitter.setSizes([220, 1060])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, stretch=1)

        # ③ 底部状态栏
        self._build_footer(main_layout)

    # ── ① 顶部系统状态栏 ──

    def _build_system_status(self, parent_layout) -> None:
        bar = QLabel()
        bar.setObjectName("SystemStatusBar")
        bar.setTextFormat(Qt.RichText)
        bar.setText(self._format_system_status())
        bar.setFixedHeight(30)
        parent_layout.addWidget(bar)
        self.system_status_label = bar

    def _format_system_status(self) -> str:
        model = self.config_data.get("model", "deepseek-chat")
        has_key = bool(self.config_data.get("api_key"))
        color = "#3fb950" if has_key else "#f85149"
        status = "Connected" if has_key else "Disconnected"
        py_ver = f"Python {sys.version_info.major}.{sys.version_info.minor}"
        return (
            f'<span style="color:{color};">● {status}</span>'
            f' &nbsp;|&nbsp; '
            f'<span style="color:#8b949e;">Model:</span> '
            f'<span style="color:#d2a8ff;">{model}</span>'
            f' &nbsp;|&nbsp; '
            f'<span style="color:#8b949e;">Env:</span> '
            f'<span style="color:#ffa657;">{py_ver}</span>'
        )

    # ── ② 侧边栏 ──

    def _build_side_panel(self, parent_splitter) -> None:
        panel = QFrame()
        panel.setObjectName("SidePanel")
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        title = QLabel("EXPLORER")
        title.setObjectName("SideTitle")
        layout.addWidget(title)

        # 工具树
        self.tool_tree = QTreeWidget()
        self.tool_tree.setHeaderHidden(True)
        self.tool_tree.setIndentation(16)
        self.tool_tree.setFrameShape(QFrame.NoFrame)
        self._populate_tool_tree()
        layout.addWidget(self.tool_tree, stretch=1)

        # 分隔线
        for _ in range(2):
            div = QFrame()
            div.setObjectName("SideDivider")
            div.setFrameShape(QFrame.HLine)
            layout.addWidget(div)

        # 状态区
        status_title = QLabel("STATUS")
        status_title.setObjectName("SideTitle")
        layout.addWidget(status_title)

        self.side_labels: Dict[str, QLabel] = {}
        for key, default in [("api", "●  API: ---"), ("model", "Model: ---"), ("tools", "Tools: ---")]:
            lbl = QLabel(default)
            lbl.setObjectName("SideItem")
            layout.addWidget(lbl)
            self.side_labels[key] = lbl

        # 分隔线
        div3 = QFrame()
        div3.setObjectName("SideDivider")
        div3.setFrameShape(QFrame.HLine)
        layout.addWidget(div3)

        # 操作按钮区
        actions_title = QLabel("ACTIONS")
        actions_title.setObjectName("SideTitle")
        layout.addWidget(actions_title)

        for text, slot in [("Clear Chat", self._clear_chat),
                           ("Settings", self._show_settings_dialog)]:
            btn = QPushButton(text)
            btn.setObjectName("BtnTool")
            btn.clicked.connect(slot)
            btn.setCursor(Qt.PointingHandCursor)
            layout.addWidget(btn)

        layout.addStretch()

        self._update_side_info()
        parent_splitter.addWidget(panel)

    def _populate_tool_tree(self) -> None:
        """填充工具树（按模块分组）。"""
        self.tool_tree.clear()

        if not _AVAILABLE_TOOLS:
            item = QTreeWidgetItem(["No tools loaded"])
            item.setForeground(0, QColor("#484f58"))
            self.tool_tree.addTopLevelItem(item)
            return

        # 按模块分组
        groups: Dict[str, List[tuple]] = {}
        for name, func in _AVAILABLE_TOOLS.items():
            mod = func.__module__.split(".")[-1] if func.__module__ else "other"
            groups.setdefault(mod, []).append((name, func))

        for mod_name, tools in sorted(groups.items()):
            group = QTreeWidgetItem([mod_name])
            group.setForeground(0, QColor("#8b949e"))
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
            self.tool_tree.addTopLevelItem(group)

            for t_name, t_func in sorted(tools):
                child = QTreeWidgetItem(["  " + t_name])
                child.setForeground(0, QColor("#c9d1d9"))
                doc = t_func.__doc__ or ""
                child.setToolTip(0, doc[:100])
                group.addChild(child)

        self.tool_tree.expandAll()

    def _update_side_info(self) -> None:
        """更新侧边栏状态信息。"""
        has_key = bool(self.config_data.get("api_key"))
        self.side_labels["api"].setText(
            f"●  API: {'Connected' if has_key else 'Disconnected'}"
        )
        self.side_labels["api"].setStyleSheet(
            f"color: {'#3fb950' if has_key else '#f85149'}; "
            f"background: transparent; padding: 4px 14px; font-size: 12px;"
        )

        self.side_labels["model"].setText(
            f"Model: {self.config_data.get('model', '---')}"
        )
        self.side_labels["model"].setStyleSheet(
            "color: #d2a8ff; background: transparent; padding: 4px 14px; font-size: 12px;"
        )

        self.side_labels["tools"].setText(
            f"Tools: {len(_AVAILABLE_TOOLS)} loaded"
        )
        self.side_labels["tools"].setStyleSheet(
            "color: #8b949e; background: transparent; padding: 4px 14px; font-size: 12px;"
        )

    # ── ③ 主区域 ──

    def _build_main_area(self) -> QWidget:
        area = QWidget()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_chat_area(layout)
        self._build_input_area(layout)
        return area

    def _build_chat_area(self, parent_layout) -> None:
        self.chat_display = QTextBrowser()
        self.chat_display.setObjectName("ChatDisplay")
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setReadOnly(True)
        self.chat_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chat_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        parent_layout.addWidget(self.chat_display, stretch=1)

        self._show_welcome()

    def _show_welcome(self) -> None:
        """显示欢迎消息。"""
        welcome = (
            '<div style="margin:32px 0;">'
            '<div style="font-size:26px;font-weight:bold;color:#58a6ff;'
            'text-align:center;letter-spacing:0.5px;">Agent Studio</div>'
            '<div style="font-size:14px;color:#484f58;text-align:center;'
            'margin-top:8px;">Local Autonomous Agent</div>'
            '<hr style="border:none;border-top:1px solid #2d2e31;margin:24px 0;">'
            '<div style="font-size:12px;color:#484f58;text-align:center;">'
            'Commands: <b>/clear</b> | <b>/tools</b> | '
            '<b>/status</b> | <b>/exit</b>'
            '</div></div>'
        )
        self.chat_display.setHtml(welcome)

    def _build_input_area(self, parent_layout) -> None:
        container = QWidget()
        container.setObjectName("InputContainer")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.input_edit = QTextEdit()
        self.input_edit.setObjectName("InputEdit")
        self.input_edit.setPlaceholderText(
            "输入指令 (Enter 发送, Shift+Enter 换行)..."
        )
        self.input_edit.setFixedHeight(44)
        self.input_edit.setAcceptRichText(False)
        self.input_edit.installEventFilter(self)
        layout.addWidget(self.input_edit, stretch=1)

        self.btn_send = QPushButton("Send")
        self.btn_send.setObjectName("BtnSend")
        self.btn_send.setFixedHeight(40)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self._send_message)
        layout.addWidget(self.btn_send)

        parent_layout.addWidget(container)

    # ── ④ 底部状态栏 ──

    def _build_footer(self, parent_layout) -> None:
        footer = QLabel(
            "<b>Enter</b> to send  |  <b>Shift+Enter</b> newline"
        )
        footer.setObjectName("FooterLabel")
        footer.setTextFormat(Qt.RichText)
        footer.setFixedHeight(26)
        parent_layout.addWidget(footer)

    # ────────────────────────────────────────────────
    #  事件处理
    # ────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        """拦截输入框按键：Enter 发送，Shift+Enter 换行。"""
        if obj == self.input_edit and event.type() == QEvent.KeyPress:
            key_event = event
            if (key_event.key() == Qt.Key_Return
                    and not key_event.modifiers() & Qt.ShiftModifier):
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    # ────────────────────────────────────────────────
    #  消息发送
    # ────────────────────────────────────────────────

    def _send_message(self) -> None:
        """发送用户消息。"""
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        # 斜杠命令
        if text.startswith("/"):
            self._handle_slash_command(text)
            self.input_edit.clear()
            return

        # 防重复发送
        if self.is_waiting:
            return

        self.input_edit.clear()

        # 显示用户消息
        self._append_to_chat(
            f'<div style="color:#c9d1d9;font-size:14px;line-height:1.7;'
            f'padding:8px 0;">'
            f'<div style="color:#ffa657;font-weight:bold;margin-bottom:4px;">'
            f'You:</div>{text}</div>'
        )

        self.messages.append({"role": "user", "content": text})

        # 锁定输入 + 启动工作线程
        self._set_input_enabled(False)
        self._start_worker()

    def _set_input_enabled(self, enabled: bool) -> None:
        """切换输入控件的启用状态。"""
        self.is_waiting = not enabled
        self.input_edit.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)
        if enabled:
            self.input_edit.setPlaceholderText(
                "输入指令 (Enter 发送, Shift+Enter 换行)..."
            )
            self.input_edit.setFocus()
        else:
            self.input_edit.setPlaceholderText(
                "Agent 处理中，请稍候..."
            )

    # ────────────────────────────────────────────────
    #  斜杠命令
    # ────────────────────────────────────────────────

    def _handle_slash_command(self, text: str) -> None:
        cmd = text.lower().strip()
        handlers = {
            "/clear":  self._clear_chat,
            "/tools":  self._show_tools,
            "/status": self._show_status,
            "/exit":   self.close,
        }
        handler = handlers.get(cmd)
        if handler:
            handler()
        else:
            self._append_to_chat(
                f'<div style="color:#d29922;background:#2d2b1b;'
                f'padding:8px 12px;border-radius:6px;margin:4px 0;'
                f'font-size:13px;">'
                f'Unknown: <b>{text}</b><br>'
                f'Available: /clear, /tools, /status, /exit</div>'
            )

    def _clear_chat(self) -> None:
        """清空聊天记录。"""
        self.chat_display.clear()
        self._show_welcome()
        self._init_system_message()

    def _show_tools(self) -> None:
        """在聊天区显示可用工具列表。"""
        if not _AVAILABLE_TOOLS:
            self._append_to_chat(
                '<div style="color:#d29922;padding:8px;">'
                'No tools loaded.</div>'
            )
            return

        rows = "".join(
            f'<tr><td style="color:#58a6ff;padding:4px 12px;'
            f'font-family:Consolas,monospace;">{n}</td>'
            f'<td style="color:#8b949e;padding:4px 12px;">'
            f'{f.__doc__ or "No description"}</td></tr>'
            for n, f in sorted(_AVAILABLE_TOOLS.items())
        )

        self._append_to_chat(
            f'<div style="background:#212226;border:1px solid #343539;'
            f'border-radius:8px;padding:12px;margin:8px 0;">'
            f'<div style="color:#58a6ff;font-weight:bold;font-size:14px;'
            f'margin-bottom:8px;">Tools ({len(_AVAILABLE_TOOLS)})</div>'
            f'<table style="width:100%;font-size:12px;">{rows}</table>'
            f'</div>'
        )

    def _show_status(self) -> None:
        """显示系统状态。"""
        items = [
            ("API Status", "Connected" if self.config_data.get("api_key") else "Disconnected"),
            ("API URL", str(self.config_data.get("base_url", "N/A"))),
            ("Model", str(self.config_data.get("model", "N/A"))),
            ("Max Turns", str(self.config_data.get("max_turns", 30))),
            ("Working Dir", os.getcwd()),
            ("Messages", str(len(self.messages))),
            ("Tools Loaded", str(len(_AVAILABLE_TOOLS))),
        ]

        rows = "".join(
            f'<tr><td style="color:#8b949e;padding:3px 10px;">{k}</td>'
            f'<td style="color:#ffa657;padding:3px 10px;">{v}</td></tr>'
            for k, v in items
        )

        self._append_to_chat(
            f'<div style="background:#212226;border:1px solid #343539;'
            f'border-radius:8px;padding:12px;margin:8px 0;">'
            f'<div style="color:#58a6ff;font-weight:bold;font-size:14px;'
            f'margin-bottom:8px;">System Status</div>'
            f'<table style="width:100%;font-size:12px;">{rows}</table>'
            f'</div>'
        )

    def _show_settings_dialog(self) -> None:
        """显示设置对话框。"""
        QMessageBox.information(
            self, "Settings",
            f"API URL: {self.config_data.get('base_url', 'N/A')}\n"
            f"Model: {self.config_data.get('model', 'N/A')}\n"
            f"Max Turns: {self.config_data.get('max_turns', 30)}\n\n"
            f"编辑 agent_config.json 以修改设置。"
        )

    # ────────────────────────────────────────────────
    #  工作线程管理
    # ────────────────────────────────────────────────

    def _start_worker(self) -> None:
        """启动 LLM 后台工作线程。"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)

        self.worker = LLMWorker(
            api_key=self.config_data.get("api_key", ""),
            base_url=self.config_data.get("base_url", ""),
            model=self.config_data.get("model", "deepseek-chat"),
            messages=self.messages,
            tools_config=_TOOLS_CONFIG,
            available_tools=_AVAILABLE_TOOLS,
            max_turns=self.config_data.get("max_turns", 30),
        )

        self.worker.status_update.connect(self._on_status_update)
        self.worker.tool_called.connect(self._on_tool_called)
        self.worker.ai_message.connect(self._on_ai_message)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished_one_round.connect(self._on_finished)

        self.worker.start()

    # ────────────────────────────────────────────────
    #  信号处理
    # ────────────────────────────────────────────────

    def _on_status_update(self, status_text: str) -> None:
        """处理状态更新信号。"""
        # 颜色映射
        if "错误" in status_text or "失败" in status_text or "熔断" in status_text:
            color = "#f85149"
        elif "完成" in status_text or "成功" in status_text:
            color = "#3fb950"
        elif "提示" in status_text or "达到" in status_text:
            color = "#d29922"
        else:
            color = "#79c0ff"

        self._append_to_chat(
            f'<div style="color:{color};font-size:12px;padding:3px 0;'
            f'font-family:Consolas,monospace;">{status_text}</div>'
        )
        self.system_status_label.setText(
            f'<span style="color:#79c0ff;">● Working</span>'
            f' &nbsp;|&nbsp; {status_text[:60]}'
        )

    def _on_tool_called(self, tool_name: str, params: str, result: str) -> None:
        """处理工具调用信号。"""
        # 格式化参数
        try:
            params_obj = json.loads(params)
            params_str = json.dumps(params_obj, ensure_ascii=False, indent=2)
        except Exception:
            params_str = params

        # 截断结果
        result_display = result[:300] + "..." if len(result) > 300 else result

        # 判断成功/失败
        error_markers = ["[ERROR]", "[STATUS: FAILED]", "不可用"]
        is_success = not any(m in result for m in error_markers)
        result_color = "#3fb950" if is_success else "#f85149"
        status_tag = "SUCCESS" if is_success else "FAILED"

        self._append_to_chat(
            f'<div style="background:#212226;border:1px solid #343539;'
            f'border-radius:8px;padding:10px 12px;margin:6px 0;'
            f'font-family:Consolas,monospace;font-size:12px;">'
            f'<div style="color:#58a6ff;font-weight:bold;">'
            f'[Tool] {tool_name}</div>'
            f'<div style="color:#484f58;margin:4px 0;">'
            f'Args: <span style="color:#ffa657;">{params_str}</span></div>'
            f'<div style="color:{result_color};margin:4px 0;">'
            f'[{status_tag}] {result_display}</div>'
            f'</div>'
        )

    def _on_ai_message(self, message: str) -> None:
        """处理 AI 文本回复信号。"""
        if "```" in message:
            formatted = self._format_code_blocks(message)
        else:
            formatted = message.replace("\n", "<br>")

        self._append_to_chat(
            f'<div style="color:#c9d1d9;font-size:14px;line-height:1.7;'
            f'padding:8px 0;">'
            f'<div style="color:#58a6ff;font-weight:bold;margin-bottom:6px;">'
            f'AI:</div>{formatted}</div>'
        )

    @staticmethod
    def _format_code_blocks(text: str) -> str:
        """将 Markdown 代码块转换为带样式 HTML。"""
        def replace_code(match):
            lang = match.group(1) or "code"
            code = (match.group(2)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
            return (
                f'<div style="background:#161719;border:1px solid #343539;'
                f'border-radius:8px;padding:14px;margin:10px 0;'
                f'font-family:Consolas,monospace;font-size:12px;'
                f'white-space:pre-wrap;overflow-x:auto;">'
                f'<div style="color:#8b949e;font-size:11px;'
                f'margin-bottom:6px;">{lang}</div>'
                f'<code style="color:#c9d1d9;">{code}</code>'
                f'</div>'
            )

        formatted = re.sub(r'```(\w*)\n(.*?)```', replace_code,
                           text, flags=re.DOTALL)
        return formatted.replace("\n", "<br>")

    def _on_error(self, error_text: str) -> None:
        """处理错误信号。"""
        self._append_to_chat(
            f'<div style="color:#f85149;background:#2d1b1b;'
            f'border:1px solid #f85149;border-radius:8px;'
            f'padding:10px 12px;margin:6px 0;font-size:13px;'
            f'font-family:Consolas,monospace;">'
            f'{error_text}</div>'
        )

    def _on_finished(self) -> None:
        """本轮对话完成，解锁输入。"""
        self._set_input_enabled(True)
        self.system_status_label.setText(self._format_system_status())
        self._update_side_info()
        self.input_edit.setFocus()

    # ────────────────────────────────────────────────
    #  辅助方法
    # ────────────────────────────────────────────────

    def _append_to_chat(self, html: str) -> None:
        """向聊天区追加 HTML 内容并滚动到底部。"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertHtml(html)
        self.chat_display.insertHtml(
            '<hr style="border:none;border-top:1px solid #212226;'
            'margin:4px 0;">'
        )
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _update_status_bar(self) -> None:
        self.system_status_label.setText(self._format_system_status())

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    def closeEvent(self, event) -> None:
        """窗口关闭时清理线程。"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()


# ════════════════════════════════════════════════════════════
#  程序入口
# ════════════════════════════════════════════════════════════

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    app.setApplicationDisplayName("Agent Studio")
    window = AgentWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
