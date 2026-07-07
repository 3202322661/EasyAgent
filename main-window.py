"""
main-window.py - AI 智能体可视化工作台
========================================
基于 PyQt5 构建的图形界面，替代命令行交互。
实现了智能体对话、工具调用可视化、配置管理等功能。

依赖安装:
    pip install PyQt5 openai

运行方式:
    python main-window.py
"""

import concurrent.futures
import importlib
import inspect
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from PySide6.QtCore import (
    Qt, QThread, Signal, QEvent
)
from PySide6.QtGui import (
    QFont, QColor
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSplitter,
    QTreeWidget, QTreeWidgetItem, QGroupBox,
    QStatusBar, QMessageBox, QGridLayout, QTextBrowser
)
from openai import OpenAI

# ============================================================
#  样式表 - 现代化暗色/亮色混合风格
# ============================================================
STYLE_SHEET = """
QMainWindow {
    background-color: #f5f5f5;
}

QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #d0d0d0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #2c3e50;
}

QLineEdit {
    border: 1px solid #ccc;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
    background-color: #ffffff;
}
QLineEdit:focus {
    border-color: #3498db;
}

QTextEdit, QTextBrowser {
    border: 1px solid #d0d0d0;
    border-radius: 5px;
    background-color: #ffffff;
    font-size: 13px;
}

QPushButton {
    border: none;
    border-radius: 5px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: bold;
    color: white;
    background-color: #3498db;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:pressed {
    background-color: #2471a3;
}
QPushButton:disabled {
    background-color: #bdc3c7;
    color: #7f8c8d;
}

QPushButton#btnSend {
    background-color: #27ae60;
    min-width: 80px;
}
QPushButton#btnSend:hover {
    background-color: #229954;
}

QPushButton#btnClear {
    background-color: #e74c3c;
    min-width: 60px;
}
QPushButton#btnClear:hover {
    background-color: #c0392b;
}

QPushButton#btnStop {
    background-color: #e67e22;
    min-width: 60px;
}
QPushButton#btnStop:hover {
    background-color: #d35400;
}

QPushButton#btnSetting {
    background-color: #95a5a6;
    min-width: 60px;
}
QPushButton#btnSetting:hover {
    background-color: #7f8c8d;
}

QTreeWidget {
    border: 1px solid #d0d0d0;
    border-radius: 5px;
    background-color: #ffffff;
    font-size: 12px;
}

QStatusBar {
    background-color: #ecf0f1;
    color: #2c3e50;
    font-size: 12px;
    border-top: 1px solid #d0d0d0;
}

QSplitter::handle {
    background-color: #d0d0d0;
    width: 2px;
}
"""


# ============================================================
#  工具加载与执行（复用 main-agent.py 的逻辑）
# ============================================================

def load_tools_config(file_path: str) -> List[Dict[str, Any]]:
    """加载工具配置文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"加载工具配置失败: {str(e)}")
        return []


def auto_load_tool_functions(tools_dir: str = "tools") -> dict:
    """自动加载 tools 目录下的所有工具函数"""
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
                        print(f"[加载] 工具函数: {func_name} 来自 {module_name}")
            except Exception as e:
                print(f"[错误] 加载模块 {module_name}: {str(e)}")
    return registry


# 全局加载工具
_TOOLS_CONFIG = load_tools_config("tool_configure.json")
_AVAILABLE_TOOLS = auto_load_tool_functions("tools")


def execute_tool(tool_call, available_tools: dict) -> dict:
    """执行单个工具调用"""
    f_name = tool_call.function.name
    f_id = tool_call.id
    is_success = True

    try:
        f_args = json.loads(tool_call.function.arguments)
    except Exception as json_error:
        return {
            "result_dict": {
                "role": "tool",
                "tool_call_id": f_id,
                "name": f_name,
                "content": f"参数解析错误: {str(json_error)}"
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


# ============================================================
#  LLM 调用线程（异步，不阻塞 UI）
# ============================================================

class LLMWorker(QThread):
    """在后台线程中调用 LLM API，通过信号将结果传回 UI"""
    response_received = Signal(object)   # 发送 LLM 回复消息
    tool_called = Signal(str, str, str)  # (工具名, 参数, 结果)
    finished_one_round = Signal()        # 一轮对话结束
    error_occurred = Signal(str)         # 错误信息
    ai_message = Signal(str)             # AI 最终文字回复
    status_update = Signal(str)          # 状态更新

    def __init__(self, api_key: str, base_url: str, model: str,
                 messages: list, tools_config: list, available_tools: dict,
                 max_turns: int = 30):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.messages = messages
        self.tools_config = tools_config
        self.available_tools = available_tools
        self.max_turns = max_turns
        self._is_running = True

    def stop(self):
        """请求停止"""
        self._is_running = False

    def run(self):
        """线程主函数 - 执行多轮对话逻辑"""
        if not self.api_key:
            self.error_occurred.emit("⚠️ API Key 未设置！请在设置中填写。")
            return

        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            self.error_occurred.emit(f"⚠️ OpenAI 客户端初始化失败: {str(e)}")
            return

        turn = 0
        consecutive_errors = 0

        while turn < self.max_turns and self._is_running:
            turn += 1
            self.status_update.emit(f"🤔 正在思考 第 {turn} 轮...")

            try:
                kwargs = {
                    "model": self.model,
                    "messages": self.messages,
                    "stream": False,
                    "temperature": 0.1
                }
                if self.tools_config:
                    kwargs["tools"] = self.tools_config

                response = client.chat.completions.create(**kwargs)
                llm_response = response.choices[0].message

            except Exception as e:
                self.error_occurred.emit(f"⚠️ API 调用失败: {str(e)}")
                break

            if llm_response is None:
                self.error_occurred.emit("⚠️ 模型返回为空")
                break

            # 将 Assistant 消息加入对话历史
            self.messages.append(llm_response)
            self.response_received.emit(llm_response)

            # ---- 检查是否有工具调用 ----
            if llm_response.tool_calls:
                tool_count = len(llm_response.tool_calls)
                self.status_update.emit(f"🔧 正在调用 {tool_count} 个工具...")

                # 并行执行工具
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(execute_tool, tc, self.available_tools)
                        for tc in llm_response.tool_calls
                    ]
                    tool_results = [
                        future.result()
                        for future in concurrent.futures.as_completed(futures)
                    ]

                for output in tool_results:
                    result = output["result_dict"]
                    tool_name = result["name"]
                    # 找到对应的参数
                    tc_param = ""
                    for tc in llm_response.tool_calls:
                        if tc.id == result.get("tool_call_id"):
                            tc_param = tc.function.arguments
                            break

                    # 发送工具调用信号（用于UI更新）
                    self.tool_called.emit(tool_name, tc_param, result["content"])

                    self.messages.append(result)

                    if not output["is_success"]:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                # 连续错误检测
                if consecutive_errors >= 3:
                    self.status_update.emit("⚠️ 工具连续出错，强制结束...")
                    self.messages.append({
                        "role": "user",
                        "content": "系统提示：底层执行工具链持续返回错误或无结果。请不要再尝试调用任何工具，直接基于现状向用户回复说明任务为何无法完成。"
                    })

                time.sleep(0.3)
                continue  # 继续下一轮思考

            else:
                # 没有工具调用 -> AI 最终文字回复
                final_text = llm_response.content or "(无文字回复)"
                self.ai_message.emit(final_text)
                self.status_update.emit("✅ 回复完成")
                break

        else:
            self.status_update.emit(f"⚠️ 达到最大对话轮数 ({self.max_turns})")

        self.finished_one_round.emit()


# ============================================================
#  主窗口
# ============================================================

class AgentWindow(QMainWindow):
    """AI 智能体可视化主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🤖 AI 智能体工作台")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # ---------- 对话历史 ----------
        self.messages: List[Dict] = []
        self._init_system_message()

        # ---------- LLM 工作线程 ----------
        self.worker: Optional[LLMWorker] = None

        # ---------- 配置 ----------
        self.config_data = self._load_config()

        # ---------- 构建 UI ----------
        self._setup_ui()
        self._apply_config_to_ui()

        # ---------- 状态 ----------
        self.is_waiting = False

        # 居中显示
        self._center_on_screen()

    # ----------------------------------------------------------
    #  初始化系统消息
    # ----------------------------------------------------------
    def _init_system_message(self):
        self.messages = [
            {
                "role": "system",
                "content": "你是一个智能助手，能够根据用户的请求调用工具并提供有用的信息。"
            }
        ]

    # ----------------------------------------------------------
    #  配置管理
    # ----------------------------------------------------------
    def _load_config(self) -> dict:
        """从配置文件加载 API 设置"""
        config_path = "agent_config.json"
        default = {
            "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "max_turns": 30
        }
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    default.update(saved)
        except Exception:
            pass
        return default

    def _save_config(self):
        """保存 API 配置到文件"""
        config_path = "agent_config.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"配置文件保存失败: {str(e)}")

    def _apply_config_to_ui(self):
        """将配置数据应用到 UI 控件"""
        self.txtApiKey.setText(self.config_data.get("api_key", ""))
        self.txtBaseUrl.setText(self.config_data.get("base_url", ""))
        self.txtModel.setText(self.config_data.get("model", ""))
        self.txtMaxTurns.setText(str(self.config_data.get("max_turns", 30)))

    def _gather_config_from_ui(self):
        """从 UI 控件收集配置"""
        self.config_data["api_key"] = self.txtApiKey.text().strip()
        self.config_data["base_url"] = self.txtBaseUrl.text().strip()
        self.config_data["model"] = self.txtModel.text().strip()
        try:
            self.config_data["max_turns"] = int(self.txtMaxTurns.text().strip())
        except ValueError:
            self.config_data["max_turns"] = 30

    # ----------------------------------------------------------
    #  UI 构建
    # ----------------------------------------------------------
    def _setup_ui(self):
        """构建完整的用户界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # ========== 顶部标题 ==========
        title_bar = QLabel("🤖 AI 智能体工作台  —  可视化交互界面")
        title_bar.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #2c3e50;
            padding: 10px 0;
        """)
        title_bar.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_bar)

        # ========== 配置区域（可折叠） ==========
        self._build_config_area(main_layout)

        # ========== 主内容区（分割器） ==========
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：对话面板
        left_panel = self._build_chat_panel()
        splitter.addWidget(left_panel)

        # 右侧：工具调用状态面板
        right_panel = self._build_tool_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([750, 350])
        main_layout.addWidget(splitter, stretch=1)

        # ========== 底部输入区 ==========
        self._build_input_area(main_layout)

        # ========== 状态栏 ==========
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("✅ 就绪")
        self.status_bar.addWidget(self.status_label)

    # ----------------------------------------------------------
    #  配置区域
    # ----------------------------------------------------------
    def _build_config_area(self, parent_layout):
        config_box = QGroupBox("⚙️ 模型配置")
        config_layout = QGridLayout(config_box)
        config_layout.setSpacing(8)

        # API Key
        config_layout.addWidget(QLabel("API Key:"), 0, 0)
        self.txtApiKey = QLineEdit()
        self.txtApiKey.setEchoMode(QLineEdit.Password)
        self.txtApiKey.setPlaceholderText("输入你的 API Key")
        config_layout.addWidget(self.txtApiKey, 0, 1)

        # Base URL
        config_layout.addWidget(QLabel("Base URL:"), 1, 0)
        self.txtBaseUrl = QLineEdit()
        self.txtBaseUrl.setPlaceholderText("https://api.deepseek.com")
        config_layout.addWidget(self.txtBaseUrl, 1, 1)

        # Model
        config_layout.addWidget(QLabel("Model:"), 2, 0)
        self.txtModel = QLineEdit()
        self.txtModel.setPlaceholderText("deepseek-chat")
        config_layout.addWidget(self.txtModel, 2, 1)

        # Max Turns
        config_layout.addWidget(QLabel("最大轮数:"), 3, 0)
        self.txtMaxTurns = QLineEdit()
        self.txtMaxTurns.setPlaceholderText("30")
        self.txtMaxTurns.setMaximumWidth(100)
        config_layout.addWidget(self.txtMaxTurns, 3, 1)

        # 按钮
        btn_save = QPushButton("💾 保存配置")
        btn_save.clicked.connect(self._on_save_config)
        config_layout.addWidget(btn_save, 3, 2)

        btn_show_key = QPushButton("👁️ 显示/隐藏")
        btn_show_key.setObjectName("btnSetting")
        btn_show_key.clicked.connect(self._toggle_api_key_visibility)
        config_layout.addWidget(btn_show_key, 0, 2)

        parent_layout.addWidget(config_box)

    def _toggle_api_key_visibility(self):
        if self.txtApiKey.echoMode() == QLineEdit.Password:
            self.txtApiKey.setEchoMode(QLineEdit.Normal)
        else:
            self.txtApiKey.setEchoMode(QLineEdit.Password)

    def _on_save_config(self):
        self._gather_config_from_ui()
        self._save_config()
        QMessageBox.information(self, "保存成功", "配置已保存！")

    # ----------------------------------------------------------
    #  对话面板
    # ----------------------------------------------------------
    def _build_chat_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("💬 对话区")
        label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(label)

        # 消息浏览器
        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(True)
        self.chat_browser.setReadOnly(True)
        self.chat_browser.setMinimumWidth(400)
        self.chat_browser.document().setDefaultStyleSheet("""
            body { font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; font-size: 13px; }
            .user-msg { background-color: #d5e8f9; padding: 8px 12px; border-radius: 8px; margin: 4px 0; }
            .ai-msg { background-color: #f0f0f0; padding: 8px 12px; border-radius: 8px; margin: 4px 0; }
            .tool-msg { background-color: #fef9e7; padding: 6px 10px; border-radius: 6px; margin: 2px 0; font-family: monospace; font-size: 12px; }
            .divider { border-top: 1px solid #ddd; margin: 8px 0; }
        """)
        layout.addWidget(self.chat_browser, stretch=1)

        return panel

    # ----------------------------------------------------------
    #  工具调用状态面板
    # ----------------------------------------------------------
    def _build_tool_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("🔧 工具调用日志")
        label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(label)

        self.tool_tree = QTreeWidget()
        self.tool_tree.setHeaderLabels(["时间", "工具", "状态"])
        self.tool_tree.setColumnWidth(0, 80)
        self.tool_tree.setColumnWidth(1, 120)
        self.tool_tree.setColumnWidth(2, 60)
        self.tool_tree.setAlternatingRowColors(True)
        self.tool_tree.setRootIsDecorated(True)
        layout.addWidget(self.tool_tree, stretch=1)

        # 清空日志按钮
        btn_clear_log = QPushButton("🗑️ 清空日志")
        btn_clear_log.setObjectName("btnClear")
        btn_clear_log.clicked.connect(self.tool_tree.clear)
        layout.addWidget(btn_clear_log)

        return panel

    # ----------------------------------------------------------
    #  输入区域
    # ----------------------------------------------------------
    def _build_input_area(self, parent_layout):
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 4, 0, 4)
        input_layout.setSpacing(8)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("输入你的问题，按 Ctrl+Enter 发送...")
        self.input_edit.setMaximumHeight(80)
        self.input_edit.setMinimumHeight(50)
        self.input_edit.setAcceptRichText(False)
        self.input_edit.installEventFilter(self)
        input_layout.addWidget(self.input_edit, stretch=1)

        # 按钮组
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        self.btn_send = QPushButton("🚀 发送")
        self.btn_send.setObjectName("btnSend")
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setMinimumWidth(80)
        btn_layout.addWidget(self.btn_send)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.setObjectName("btnClear")
        self.btn_clear.clicked.connect(self._on_clear_chat)
        btn_layout.addWidget(self.btn_clear)

        input_layout.addLayout(btn_layout)

        parent_layout.addWidget(input_widget)

    # ----------------------------------------------------------
    #  事件过滤器（支持 Ctrl+Enter 发送）
    # ----------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self.input_edit:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Return:
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    # ----------------------------------------------------------
    #  核心交互逻辑
    # ----------------------------------------------------------
    def _on_send(self):
        """发送用户消息"""
        if self.is_waiting:
            QMessageBox.information(self, "提示", "正在处理中，请等待回复完成...")
            return

        text = self.input_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请输入内容后再发送")
            return

        # 收集最新配置
        self._gather_config_from_ui()

        # 校验 API Key
        if not self.config_data.get("api_key"):
            QMessageBox.warning(self, "配置缺失", "请先设置 API Key！")
            return

        # 显示用户消息
        self._append_user_message(text)

        # 添加到消息历史
        self.messages.append({"role": "user", "content": text})

        # 清空输入框
        self.input_edit.clear()

        # 切换状态
        self._set_waiting_state(True)

        # 启动后台线程
        self.worker = LLMWorker(
            api_key=self.config_data["api_key"],
            base_url=self.config_data["base_url"],
            model=self.config_data["model"],
            messages=self.messages,
            tools_config=_TOOLS_CONFIG,
            available_tools=_AVAILABLE_TOOLS,
            max_turns=self.config_data.get("max_turns", 30)
        )
        self.worker.response_received.connect(self._on_llm_response)
        self.worker.tool_called.connect(self._on_tool_called)
        self.worker.ai_message.connect(self._on_ai_final_message)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.status_update.connect(self._on_status_update)
        self.worker.finished_one_round.connect(self._on_round_finished)
        self.worker.start()

    def _on_stop(self):
        """停止当前对话"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait()
            self._append_system_message("⏸️ 用户手动停止了对话")
            self._set_waiting_state(False)
            self.status_label.setText("⏸️ 已停止")

    def _on_clear_chat(self):
        """清空对话"""
        if self.is_waiting:
            QMessageBox.information(self, "提示", "请等待当前对话结束再清空")
            return

        reply = QMessageBox.question(
            self, "确认清空", "确定要清空所有对话记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.chat_browser.clear()
            self.tool_tree.clear()
            self.messages.clear()
            self._init_system_message()
            self.status_label.setText("✅ 对话已清空")

    # ----------------------------------------------------------
    #  状态切换
    # ----------------------------------------------------------
    def _set_waiting_state(self, waiting: bool):
        self.is_waiting = waiting
        self.btn_send.setEnabled(not waiting)
        self.btn_stop.setEnabled(waiting)
        self.input_edit.setEnabled(not waiting)
        if waiting:
            self.input_edit.setPlaceholderText("⏳ AI 正在思考中...")
        else:
            self.input_edit.setPlaceholderText("输入你的问题，按 Ctrl+Enter 发送...")

    # ----------------------------------------------------------
    #  信号处理
    # ----------------------------------------------------------
    def _on_llm_response(self, response):
        """收到 LLM 回复（可能有工具调用）"""
        if hasattr(response, 'content') and response.content:
            # 这里不重复显示，等最终 AI 消息
            pass

    def _on_tool_called(self, tool_name: str, params: str, result: str):
        """工具被调用"""
        now = datetime.now().strftime("%H:%M:%S")

        # 工具树
        item = QTreeWidgetItem([now, tool_name, "✅ 成功"])
        item.setForeground(2, QColor("#27ae60"))

        # 展开查看参数和结果
        param_item = QTreeWidgetItem(["", "参数", params[:120] + ("..." if len(params) > 120 else "")])
        param_item.setForeground(1, QColor("#8e44ad"))
        item.addChild(param_item)

        result_preview = result[:150] + ("..." if len(result) > 150 else "")
        result_item = QTreeWidgetItem(["", "结果", result_preview])
        result_item.setForeground(1, QColor("#d35400"))
        item.addChild(result_item)

        self.tool_tree.addTopLevelItem(item)
        self.tool_tree.expandItem(item)

        # 在聊天区也显示工具调用
        self._append_tool_message(tool_name, params, result)

        self.status_label.setText(f"🔧 工具: {tool_name}")

    def _on_ai_final_message(self, text: str):
        """AI 最终文字回复"""
        self._append_ai_message(text)
        self.status_label.setText("✅ AI 回复完成")

    def _on_error(self, error_msg: str):
        """发生错误"""
        self._append_system_message(f"❌ {error_msg}")
        self.status_label.setText(f"❌ {error_msg}")

    def _on_status_update(self, status: str):
        """状态更新"""
        self.status_label.setText(status)

    def _on_round_finished(self):
        """一轮对话结束"""
        self._set_waiting_state(False)
        self.status_label.setText("✅ 就绪，可以继续对话")

    # ----------------------------------------------------------
    #  消息渲染（富文本）
    # ----------------------------------------------------------
    def _append_user_message(self, text: str):
        """追加用户消息到聊天区"""
        html = f"""
        <div class="user-msg">
            <b style="color:#2980b9;">🧑 你</b>
            <p style="margin:4px 0 0 0;">{self._escape_html(text)}</p>
        </div>
        <hr class="divider">
        """
        self.chat_browser.append(html)
        self._scroll_to_bottom()

    def _append_ai_message(self, text: str):
        """追加 AI 消息"""
        html = f"""
        <div class="ai-msg">
            <b style="color:#27ae60;">🤖 AI 助手</b>
            <p style="margin:4px 0 0 0;">{self._escape_html(text)}</p>
        </div>
        <hr class="divider">
        """
        self.chat_browser.append(html)
        self._scroll_to_bottom()

    def _append_tool_message(self, tool_name: str, params: str, result: str):
        """追加工具调用消息"""
        try:
            params_pretty = json.dumps(json.loads(params), ensure_ascii=False, indent=2)
        except Exception:
            params_pretty = params

        html = f"""
        <div class="tool-msg">
            <b style="color:#8e44ad;">🔧 工具调用: {self._escape_html(tool_name)}</b>
            <details>
                <summary style="cursor:pointer; color:#3498db;">查看详情</summary>
                <pre style="background:#f8f9fa; padding:8px; border-radius:4px; margin:4px 0; font-size:11px; white-space:pre-wrap;">
参数:
{self._escape_html(params_pretty)}

结果:
{self._escape_html(result)}
                </pre>
            </details>
        </div>
        """
        self.chat_browser.append(html)
        self._scroll_to_bottom()

    def _append_system_message(self, text: str):
        """追加系统消息"""
        html = f"""
        <div style="text-align:center; color:#7f8c8d; font-size:12px; padding:4px 0;">
            ⚙️ {self._escape_html(text)}
        </div>
        <hr class="divider">
        """
        self.chat_browser.append(html)
        self._scroll_to_bottom()

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        if not text:
            return ""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&#x27;")
        # 换行转 <br>
        text = text.replace("\n", "<br>")
        return text

    def _scroll_to_bottom(self):
        """滚动聊天区到底部"""
        scrollbar = self.chat_browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ----------------------------------------------------------
    #  窗口居中
    # ----------------------------------------------------------
    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    # ----------------------------------------------------------
    #  窗口关闭事件
    # ----------------------------------------------------------
    def closeEvent(self, event):
        """关闭时终止后台线程"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait()
        self._save_config()
        event.accept()


# ============================================================
#  程序入口
# ============================================================

def main():
    # 环境变量（兼容原有逻辑）
    os.environ['PADDLE_PDX_HOME'] = os.environ.get(
        'PADDLE_PDX_HOME',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.paddlex')
    )
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = "True"

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    app.setFont(QFont("Microsoft YaHei", 10))

    window = AgentWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
