import concurrent.futures
import importlib
import inspect
import json
import time

from openai import OpenAI
from typing import Dict, Any, List

import os

def load_tools_config(file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"加载工具配置失败: {str(e)}")
        return []

def auto_load_tool_functions(tools_dir: str = "tools") -> dict:
    registry = {}

    if not os.path.isdir(tools_dir):
        print(f"工具目录 {tools_dir} 不存在。")
        return registry
    for file_name in os.listdir(tools_dir):
        if file_name.endswith(".py") and not file_name.startswith("__"):
            module_name = file_name[:-3]
            try:
                module = importlib.import_module(f"{tools_dir}.{module_name}")
                functions = inspect.getmembers(module, inspect.isfunction)

                for func_name, func_obj in functions:
                    if func_obj.__module__ == module.__name__ and not func_name.startswith("_"):
                        registry[func_name] = func_obj
                        print(f"已加载工具函数: {func_name} 来自模块 {module_name}")
            except Exception as e:
                print(f"加载模块 {module_name} 时发生错误: {str(e)}")
    return registry

def execute_tool(tool_call):
    f_name = tool_call.function.name
    f_id = tool_call.id

    is_success = True

    try:
        f_args = json.loads(tool_call.function.arguments)
    except Exception as json_error:
        error_json_content = f"大模型生成参数不是有效的JSON格式: {str(json_error)}"
        return {
            "result_dict": {
                "role": "tool",
                "tool_call_id": f_id,
                "name": f_name,
                "content": error_json_content
            },
            "is_success": False
        }

    if f_name in available_tools:
        tool_function = available_tools[f_name]
        try:
            res = tool_function(**f_args)
            if "错误" in str(res) or "failed" in str(res).lower():
                is_success = False
        except Exception as script_error:
            res = f"工具执行失败: {str(script_error)}"
            is_success = False
    else:
        res = f"工具 {f_name} 不可用"
        is_success = False
    return {
        "result_dict": {
            "role": "tool",
            "tool_call_id": f_id,
            "name": f_name,
            "content": str(res)
        },
        "is_success": is_success
    }

tools_config = load_tools_config("tool_configure.json")
available_tools = auto_load_tool_functions("tools")

class OpenAICompatibleClient:
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.client = OpenAI(api_key=api_key,
                             base_url=base_url)

    def generate(self, messages: List[Dict[str, Any]], tools: list = None) -> Any:
        print("正在调用大语言模型API...")
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "temperature": 0.1
            }

            if tools:
                kwargs["tools"] = tools

            response = self.client.chat.completions.create(**kwargs)

            return response.choices[0].message
        except Exception as e:
            print(f"[ERROR] 调用大语言模型API时发生错误: {e} ")
            return None

if __name__ == "__main__":
    API_KEY = os.environ.get("DEEPSEEK_API_KEY")  # 请替换为你的实际API Key
    BASE_URL = "https://api.deepseek.com"
    MODEL_ID = "deepseek-v4-flash"

    LLM = OpenAICompatibleClient(
        model = MODEL_ID,
        base_url = BASE_URL,
        api_key = API_KEY
    )

    messages = [
        {"role": "system", "content": "你是一个智能助手，能够根据用户的请求调用工具并提供有用的信息。"}
    ]

    max_turns = 30

    while True:
        user_input = input("User: ")

        if user_input.lower() in ["exit", "quit"]:
            print("Exiting...")
            break

        messages.append({"role": "user", "content": user_input})

        turn = 0
        consecutive_errors = 0

        while turn < max_turns:
            turn += 1
            print(f"正在思考 第 {turn} 轮...")

            LLM_response = LLM.generate(
                messages=messages,
                tools=tools_config
            )

            if LLM_response is None:
                print("大语言模型API调用失败，无法继续对话。")
                break

            messages.append(LLM_response)

            if LLM_response.tool_calls:
                print("大语言模型请求调用工具...")
                print(f"大语言模型自动调用了{len(LLM_response.tool_calls)}个工具。")

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(execute_tool, tool_call) for tool_call in LLM_response.tool_calls]
                    tool_results = [future.result() for future in concurrent.futures.as_completed(futures)]

                for output in tool_results:
                    result = output["result_dict"]
                    print(f"工具调用结果: {result['name']} - {result['content']}")
                    messages.append(result)

                    if not output["is_success"]:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                if consecutive_errors >= 3:
                    print("检测到底层工具连续发生严重错误，任务判定为‘不可解决’。强制要求模型进行最终复盘说明...")
                    messages.append({
                        "role": "user",
                        "content": "系统提示：底层执行工具链持续返回错误或无结果。请不要再尝试调用任何工具，直接基于现状向用户回复说明任务为何无法完成。"
                    })
                    break

                time.sleep(0.5)
                continue
            else:
                print(f"AI助手: {LLM_response.content}")
                break
        else:
            print(f"达到单次对话最大轮数({max_turns}轮)，结束本次对话。")
            break