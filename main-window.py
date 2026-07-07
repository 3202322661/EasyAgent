"""
main-window.py — Claude Code 风格智能体工作台
=================================================
基于 PySide6 构建，严格遵循暗黑科技风 UI 设计哲学。
VS Code 双栏布局（侧边工具面板 + 主聊天区）+ 实时状态反馈。

依赖安装:
    pip install PySide6 openai

运行方式:
    python main-window.py
"""

import concurrent.futures
import importlib
import inspect
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from PySide6.QtCore import (
    Qt, QThread, Signal, QEvent, QTimer
)
from PySide6.QtGui import (
    QFont, QColor, QIcon, QTextCursor, QKeyEvent, QPixmap, QPainter, QLinearGradient
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSplitter,
    QTreeWidget, QTreeWidgetItem, QGroupBox,
    QStatusBar, QMessageBox, QGridLayout, QTextBrowser,
    QFrame, QScrollBar, QListWidget, QListWidgetItem
)
from openai import OpenAI


# ============================================================
#  🎨 精致暗黑风样式表
#  渐变背景 · 圆角卡片 · 微妙阴影 · VS Code 色彩体系
# ============================================================
STYLE_SHEET = """
/* ---- 全局基础 ---- */
QMainWindow {
    background-color: #1a1b1e;
}
QWidget {
    background-color: #1a1b1e;
    color: #c9d1d9;
    font-family: "Microsoft YaHei", -apple-system, "Segoe UI", "Consolas", sans-serif;
}

/* ---- 侧边栏 ---- */
QFrame#SidePanel {
    background-color: #151618;
    border-right: 1px solid #2d2e31;
}
QLabel#SideTitle {
    color: #8b949e;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 12px 14px 6px 14px;
    background: transparent;
}
QLabel#SideItem {
    color: #c9d1d9;
    font-size: 13px;
    padding: 7px 14px;
    background: transparent;
    border-radius: 4px;
}
QLabel#SideItem:hover {
    background-color: #1f2023;
    color: #58a6ff;
}
QLabel#SideItemActive {
    color: #58a6ff;
    font-size: 13px;
    padding: 7px 14px;
    background: #1f2023;
    border-left: 2px solid #58a6ff;
    border-radius: 0 4px 4px 0;
}
QLabel#SideSection {
    color: #8b949e;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 16px 14px 4px 14px;
    background: transparent;
}
QFrame#SideDivider {
    background-color: #2d2e31;
    max-height: 1px;
    margin: 4px 14px;
}

/* ---- 系统状态栏 (顶部) ---- */
QLabel#SystemStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1c1d20, stop:1 #151618);
    color: #8b949e;
    font-size: 11px;
    padding: 5px 16px;
    border-bottom: 1px solid #2d2e31;
    font-family: "Consolas", "Microsoft YaHei", monospace;
}

/* ---- 聊天消息区域 ---- */
QTextBrowser#ChatDisplay {
    background-color: #1a1b1e;
    color: #c9d1d9;
    font-size: 14px;
    border: none;
    padding: 16px 20px;
    selection-background-color: #1f3a5f;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}

/* ---- 输入框 ---- */
QTextEdit#InputEdit {
    background-color: #212226;
    color: #c9d1d9;
    font-size: 13.5px;
    border: 1px solid #343539;
    border-radius: 8px;
    padding: 10px 16px;
    selection-background-color: #1f3a5f;
    font-family: "Microsoft YaHei", "Consolas", sans-serif;
}
QTextEdit#InputEdit:focus {
    border-color: #58a6ff;
    background-color: #1c1d20;
}
QTextEdit#InputEdit:disabled {
    background-color: #1a1b1e;
    color: #484f58;
}

/* ---- 发送按钮 ---- */
QPushButton#BtnSend {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #238636, stop:1 #1e7a30);
    color: #FFFFFF;
    font-size: 13px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    min-width: 72px;
}
QPushButton#BtnSend:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2ea043, stop:1 #238636);
}
QPushButton#BtnSend:pressed {
    background-color: #1a6a2a;
}
QPushButton#BtnSend:disabled {
    background: #2d2e31;
    color: #484f58;
}

/* ---- 辅助按钮 ---- */
QPushButton#BtnTool {
    background-color: #212226;
    color: #8b949e;
    font-size: 12px;
    border: 1px solid #343539;
    border-radius: 6px;
    padding: 6px 14px;
    min-width: 50px;
}
QPushButton#BtnTool:hover {
    background-color: #2d2e31;
    border-color: #58a6ff;
    color: #c9d1d9;
}
QPushButton#BtnTool:pressed {
    background-color: #1a1b1e;
}
QPushButton#BtnTool:checked {
    background-color: #1f3a5f;
    border-color: #58a6ff;
    color: #58a6ff;
}

/* ---- 底部栏 ---- */
QLabel#FooterLabel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #151618, stop:1 #1a1b1e);
    color: #484f58;
    font-size: 11px;
    padding: 3px 16px;
    border-top: 1px solid #2d2e31;
    font-family: "Consolas", monospace;
}

/* ---- 滚动条 (暗色精致) ---- */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #343539;
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #343539;
    border-radius: 4px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #484f58;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ---- 设置对话框按钮 ---- */
QPushButton#BtnSettings {
    background-color: transparent;
    color: #8b949e;
    font-size: 12px;
    border: 1px solid #343539;
    border-radius: 6px;
    padding: 4px 12px;
}
QPushButton#BtnSettings:hover {
    background-color: #212226;
    border-color: #58a6ff;
    color: #c9d1d9;
}

/* ---- 树形控件/列表 (侧边工具列表) ---- */
QTreeWidget {
    background-color: transparent;
    color: #c9d1d9;
    font-size: 12px;
    border: none;
    outline: none;
}
QTreeWidget::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QTreeWidget::item:hover {
    background-color: #1f2023;
}
QTreeWidget::item:selected {
    background-color: #1f3a5f;
    color: #58a6ff;
}
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    border-image: none;
}
QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {
    border-image: none;
}

/* ---- 输入容器背景 ---- */
QWidget#InputContainer {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1e1f22, stop:1 #1a1b1e);
    border-top: 1px solid #2d2e31;
    padding: 10px 16px;
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
        print(f"[配置] 加载工具配置失败: {str(e)}")
        return []


def auto_load_tool_functions(tools_dir: str = "tools") -> dict:
    """自动加载 tools 目录下的所有工具函数"""
    registry = {}
    if not os.path.isdir(tools_dir):
        print(f"[工具] 工具目录 {tools_dir} 不存在。")
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

    status_update = Signal(str)
    tool_called = Signal(str, str, str)
    ai_message = Signal(str)
    error_occurred = Signal(str)
    finished_one_round = Signal()

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
            self.error_occurred.emit("API Key 未设置！请在设置中填写。")
            self.finished_one_round.emit()
            return

        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            self.error_occurred.emit(f"OpenAI 客户端初始化失败: {str(e)}")
            self.finished_one_round.emit()
            return

        turn = 0
        consecutive_errors = 0

        while turn < self.max_turns and self._is_running:
            turn += 1
            self.status_update.emit(f"[思考中] Agent 正在分析... (第 {turn} 轮)")

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
                self.error_occurred.emit(f"API 调用失败: {str(e)}")
                break

            if llm_response is None:
                self.error_occurred.emit("模型返回为空")
                break

            # 将 Assistant 消息加入对话历史
            self.messages.append(llm_response)

            # ---- 检查是否有工具调用 ----
            if llm_response.tool_calls:
                tool_count = len(llm_response.tool_calls)
                self.status_update.emit(f"[工具触发] 自动激活工具箱 ({tool_count} 个工具)")

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

                    # 发送工具调用信号
                    self.tool_called.emit(tool_name, tc_param, result["content"])
                    self.messages.append(result)

                    if not output["is_success"]:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                # 连续错误检测 —— 熔断机制
                if consecutive_errors >= 3:
                    self.status_update.emit(
                        "[熔断] 工具连续出错！Agent 任务失败退场报告..."
                    )
                    fault_report = (
                        "--- Agent 任务失败退场报告 ---\n"
                        "底层执行工具链持续返回错误或无结果。请检查：\n"
                        "  1. 第三方依赖是否安装完整\n"
                        "  2. 配置文件路径是否正确\n"
                        "  3. API 或网络连接是否正常\n"
                        "-----------------------------"
                    )
                    self.ai_message.emit(
                        f'<div style="color:#f85149;background:#2d1b1b;padding:12px;'
                        f'border:1px solid #f85149;border-radius:6px;'
                        f'font-family:Consolas;white-space:pre-wrap;">{fault_report}</div>'
                    )
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
                self.status_update.emit("回复完成")
                break

        else:
            self.status_update.emit(f"达到最大对话轮数 ({self.max_turns})")

        self.finished_one_round.emit()


# ============================================================
#  主窗口 — VS Code 风格双栏布局
# ============================================================

class AgentWindow(QMainWindow):
    """AI 智能体可视化主窗口 —— 双栏布局 + 精致暗黑风"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agent Studio — 本地自主 Agent")
        self.setMinimumSize(1000, 720)
        self.resize(1280, 840)

        # ---------- 对话历史 ----------
        self.messages: List[Dict] = []
        self._init_system_message()

        # ---------- LLM 工作线程 ----------
        self.worker: Optional[LLMWorker] = None

        # ---------- 配置 ----------
        self.config_data = self._load_config()

        # ---------- 构建 UI ----------
        self._setup_ui()
        self._update_status_bar()

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

    # ----------------------------------------------------------
    #  UI 构建 — 双栏布局（侧边栏 + 主区域）
    # ----------------------------------------------------------
    def _setup_ui(self):
        """构建完整的用户界面 —— VS Code 风格双栏布局"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== ① 顶部系统状态栏 ==========
        self._build_system_status(main_layout)

        # ========== ② 双栏主体（侧边栏 + 聊天区域）==========
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        # 左侧面板（侧边栏）
        self._build_side_panel(splitter)

        # 右侧主区域
        right_area = self._build_main_area()
        splitter.addWidget(right_area)

        # 设置比例：侧边栏 200px，主区域拉伸
        splitter.setSizes([200, 800])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, stretch=1)

        # ========== ③ 底部状态栏 ==========
        self._build_footer(main_layout)

    # ----------------------------------------------------------
    #  ① 顶部系统状态栏
    # ----------------------------------------------------------
    def _build_system_status(self, parent_layout):
        """构建顶部系统状态栏"""
        status_bar = QLabel()
        status_bar.setObjectName("SystemStatusBar")
        status_bar.setTextFormat(Qt.RichText)
        status_bar.setText(self._format_system_status())
        status_bar.setFixedHeight(30)
        parent_layout.addWidget(status_bar)
        self.system_status_label = status_bar

    def _format_system_status(self):
        """格式化系统状态文本"""
        model_name = self.config_data.get("model", "deepseek-chat")
        api_status = "Connected" if self.config_data.get("api_key") else "Disconnected"
        api_color = "#3fb950" if self.config_data.get("api_key") else "#f85149"
        python_ver = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return (
            f'<span style="color:{api_color};">● {api_status}</span>'
            f' &nbsp; &nbsp; '
            f'<span style="color:#8b949e;">Model:</span> '
            f'<span style="color:#d2a8ff;">{model_name}</span>'
            f' &nbsp; &nbsp; '
            f'<span style="color:#8b949e;">Env:</span> '
            f'<span style="color:#ffa657;">{python_ver}</span>'
        )

    # ----------------------------------------------------------
    #  ② 侧边栏 — 类似 VS Code / Claude Code 的工具面板
    # ----------------------------------------------------------
    def _build_side_panel(self, parent_splitter):
        """构建左侧工具面板"""
        side_panel = QFrame()
        side_panel.setObjectName("SidePanel")
        side_panel.setFixedWidth(220)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        # --- 面板标题 ---
        title = QLabel("EXPLORER")
        title.setObjectName("SideTitle")
        side_layout.addWidget(title)

        # --- 工具列表区 ---
        self.tool_tree = QTreeWidget()
        self.tool_tree.setObjectName("ToolTree")
        self.tool_tree.setHeaderHidden(True)
        self.tool_tree.setIndentation(16)
        self.tool_tree.setFrameShape(QFrame.NoFrame)
        self._populate_tool_tree()
        side_layout.addWidget(self.tool_tree, stretch=1)

        # --- 分隔线 ---
        divider = QFrame()
        divider.setObjectName("SideDivider")
        divider.setFrameShape(QFrame.HLine)
        side_layout.addWidget(divider)

        # --- 系统状态区 ---
        status_title = QLabel("STATUS")
        status_title.setObjectName("SideTitle")
        side_layout.addWidget(status_title)

        # API 状态
        self.side_api_status = QLabel()
        self.side_api_status.setObjectName("SideItem")
        side_layout.addWidget(self.side_api_status)

        # 模型信息
        self.side_model_info = QLabel()
        self.side_model_info.setObjectName("SideItem")
        side_layout.addWidget(self.side_model_info)

        # 工具数量
        self.side_tool_count = QLabel()
        self.side_tool_count.setObjectName("SideItem")
        side_layout.addWidget(self.side_tool_count)

        # --- 分隔线 ---
        divider2 = QFrame()
        divider2.setObjectName("SideDivider")
        divider2.setFrameShape(QFrame.HLine)
        side_layout.addWidget(divider2)

        # --- 操作按钮区 ---
        actions_title = QLabel("ACTIONS")
        actions_title.setObjectName("SideTitle")
        side_layout.addWidget(actions_title)

        btn_clear_side = QPushButton("Clear Chat")
        btn_clear_side.setObjectName("BtnTool")
        btn_clear_side.clicked.connect(self._clear_chat)
        btn_clear_side.setCursor(Qt.PointingHandCursor)
        side_layout.addWidget(btn_clear_side)

        btn_settings = QPushButton("Settings")
        btn_settings.setObjectName("BtnTool")
        btn_settings.clicked.connect(self._show_settings_dialog)
        btn_settings.setCursor(Qt.PointingHandCursor)
        side_layout.addWidget(btn_settings)

        # 底部留白
        side_layout.addStretch()

        # 更新侧边栏信息
        self._update_side_info()

        parent_splitter.addWidget(side_panel)

    def _populate_tool_tree(self):
        """填充工具树"""
        self.tool_tree.clear()

        if not _AVAILABLE_TOOLS:
            item = QTreeWidgetItem(["No tools loaded"])
            item.setForeground(0, QColor("#484f58"))
            self.tool_tree.addTopLevelItem(item)
            return

        # 按模块分组
        groups = {}
        for name, func in _AVAILABLE_TOOLS.items():
            module_name = func.__module__.split(".")[-1] if func.__module__ else "other"
            if module_name not in groups:
                groups[module_name] = []
            groups[module_name].append((name, func))

        for module_name, tools in sorted(groups.items()):
            group_item = QTreeWidgetItem([module_name])
            group_item.setForeground(0, QColor("#8b949e"))
            font = group_item.font(0)
            font.setBold(True)
            font.setPointSize(11)
            group_item.setFont(0, font)
            self.tool_tree.addTopLevelItem(group_item)

            for tool_name, tool_func in sorted(tools):
                child = QTreeWidgetItem(["  " + tool_name])
                child.setForeground(0, QColor("#c9d1d9"))
                child_font = child.font(0)
                child_font.setPointSize(11)
                child.setFont(0, child_font)
                # 存描述为 tooltip
                doc = tool_func.__doc__ or ""
                child.setToolTip(0, doc[:100] if len(doc) > 100 else doc)
                group_item.addChild(child)

        self.tool_tree.expandAll()

    def _update_side_info(self):
        """更新侧边栏状态信息"""
        api_key = self.config_data.get("api_key", "")
        api_color = "#3fb950" if api_key else "#f85149"
        api_text = "Connected" if api_key else "Disconnected"
        self.side_api_status.setText(f"●  API: {api_text}")
        self.side_api_status.setStyleSheet(f"color: {api_color}; background: transparent; padding: 4px 14px; font-size: 12px;")

        model = self.config_data.get("model", "deepseek-chat")
        self.side_model_info.setText(f"Model: {model}")
        self.side_model_info.setStyleSheet("color: #d2a8ff; background: transparent; padding: 4px 14px; font-size: 12px;")

        tool_count = len(_AVAILABLE_TOOLS)
        self.side_tool_count.setText(f"Tools: {tool_count} loaded")
        self.side_tool_count.setStyleSheet("color: #8b949e; background: transparent; padding: 4px 14px; font-size: 12px;")

    # ----------------------------------------------------------
    #  ③ 主区域（聊天 + 输入）
    # ----------------------------------------------------------
    def _build_main_area(self):
        """构建右侧主区域"""
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 聊天显示区
        self._build_chat_area(main_layout)

        # 底部输入区域
        self._build_input_area(main_layout)

        return main_area

    def _build_chat_area(self, parent_layout):
        """构建中央聊天消息显示区"""
        self.chat_display = QTextBrowser()
        self.chat_display.setObjectName("ChatDisplay")
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setReadOnly(True)
        self.chat_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chat_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        parent_layout.addWidget(self.chat_display, stretch=1)

        # 显示欢迎信息（无 emoji）
        welcome_html = (
            '<div style="margin: 32px 0;">'
            '<div style="font-size: 26px; font-weight: bold; color: #58a6ff; text-align: center; '
            'letter-spacing: 0.5px;">Agent Studio</div>'
            '<div style="font-size: 14px; color: #484f58; text-align: center; margin-top: 8px;">'
            'Local Autonomous Agent — 输入指令开始对话</div>'
            '<hr style="border: none; border-top: 1px solid #2d2e31; margin: 24px 0;">'
            '<div style="font-size: 12px; color: #484f58; text-align: center;">'
            'Commands: <b>/clear</b> &nbsp;|&nbsp; <b>/tools</b> &nbsp;|&nbsp; <b>/status</b> &nbsp;|&nbsp; <b>/exit</b>'
            '</div></div>'
        )
        self.chat_display.setHtml(welcome_html)

    def _build_input_area(self, parent_layout):
        """构建底部输入区域"""
        input_container = QWidget()
        input_container.setObjectName("InputContainer")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)

        # 输入框
        self.input_edit = QTextEdit()
        self.input_edit.setObjectName("InputEdit")
        self.input_edit.setPlaceholderText("输入指令（Enter 发送，Shift+Enter 换行）...")
        self.input_edit.setFixedHeight(44)
        self.input_edit.setAcceptRichText(False)
        self.input_edit.installEventFilter(self)
        input_layout.addWidget(self.input_edit, stretch=1)

        # 发送按钮
        self.btn_send = QPushButton("Send")
        self.btn_send.setObjectName("BtnSend")
        self.btn_send.setFixedHeight(40)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self._send_message)
        input_layout.addWidget(self.btn_send)

        parent_layout.addWidget(input_container)

    # ----------------------------------------------------------
    #  ④ 底部状态栏
    # ----------------------------------------------------------
    def _build_footer(self, parent_layout):
        """构建底部状态信息栏"""
        footer = QLabel()
        footer.setObjectName("FooterLabel")
        footer.setText(
            f'<b>Enter</b> to send &nbsp;|&nbsp; <b>Shift+Enter</b> newline'
        )
        footer.setTextFormat(Qt.RichText)
        footer.setFixedHeight(26)
        parent_layout.addWidget(footer)

    # ----------------------------------------------------------
    #  事件过滤
    # ----------------------------------------------------------
    def eventFilter(self, obj, event):
        """拦截输入框键盘事件"""
        if obj == self.input_edit and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Return and not key_event.modifiers() & Qt.ShiftModifier:
                self._send_message()
                return True
            if key_event.key() == Qt.Key_Return and key_event.modifiers() & Qt.ShiftModifier:
                return False
        return super().eventFilter(obj, event)

    # ----------------------------------------------------------
    #  发送消息逻辑
    # ----------------------------------------------------------
    def _send_message(self):
        """发送用户输入的消息"""
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        # ---- 斜杠命令拦截 ----
        if text.startswith("/"):
            self._handle_slash_command(text)
            self.input_edit.clear()
            return

        # ---- 正在处理中，禁止重复发送 ----
        if self.is_waiting:
            return

        # 清空输入框
        self.input_edit.clear()

        # 在聊天区域显示用户消息
        user_html = self._format_user_message(text)
        self._append_to_chat(user_html)

        # 将用户消息加入对话历史
        self.messages.append({"role": "user", "content": text})

        # 锁定输入
        self._set_input_enabled(False)

        # 启动后台线程
        self._start_worker()

    def _set_input_enabled(self, enabled: bool):
        """锁定/解锁输入控件"""
        self.is_waiting = not enabled
        self.input_edit.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)
        if enabled:
            self.input_edit.setPlaceholderText("输入指令（Enter 发送，Shift+Enter 换行）...")
            self.input_edit.setFocus()
        else:
            self.input_edit.setPlaceholderText("Agent 正在处理中，请稍候...")

    # ----------------------------------------------------------
    #  斜杠命令处理
    # ----------------------------------------------------------
    def _handle_slash_command(self, text: str):
        """处理斜杠命令"""
        cmd = text.lower().strip()

        if cmd == "/clear":
            self._clear_chat()

        elif cmd == "/tools":
            self._show_tools()

        elif cmd == "/status":
            self._show_status()

        elif cmd == "/exit":
            self.close()

        else:
            self._append_to_chat(
                f'<div style="color:#d29922;background:#2d2b1b;padding:8px 12px;'
                f'border-radius:6px;margin:4px 0;font-size:13px;">'
                f'Unknown command: <b>{text}</b><br>'
                f'Available: /clear, /tools, /status, /exit'
                f'</div>'
            )

    def _clear_chat(self):
        """清空聊天记录"""
        self.chat_display.clear()
        welcome_html = (
            '<div style="margin: 24px 0;">'
            '<div style="font-size: 24px; font-weight: bold; color: #58a6ff; text-align: center;">'
            'Agent Studio</div>'
            '<div style="font-size: 14px; color: #484f58; text-align: center; margin-top: 6px;">'
            'Chat cleared — 开始新的会话</div>'
            '</div>'
        )
        self.chat_display.setHtml(welcome_html)
        self._init_system_message()

    def _show_tools(self):
        """显示可用工具列表"""
        if not _AVAILABLE_TOOLS:
            self._append_to_chat(
                '<div style="color:#d29922;padding:8px;font-size:13px;">'
                '当前没有加载任何可用工具。</div>'
            )
            return

        tool_list = "".join(
            f'<tr><td style="color:#58a6ff;padding:4px 12px;font-family:Consolas,monospace;">'
            f'{name}</td>'
            f'<td style="color:#8b949e;padding:4px 12px;">{func.__doc__ or "No description"}</td></tr>'
            for name, func in _AVAILABLE_TOOLS.items()
        )

        table_html = (
            '<div style="background:#212226;border:1px solid #343539;border-radius:8px;'
            'padding:12px;margin:8px 0;box-shadow: 0 1px 3px rgba(0,0,0,0.3);">'
            '<div style="color:#58a6ff;font-weight:bold;font-size:14px;margin-bottom:8px;">'
            'Available Tools</div>'
            f'<table style="width:100%;font-size:12px;">{tool_list}</table>'
            '</div>'
        )
        self._append_to_chat(table_html)

    def _show_status(self):
        """显示系统状态"""
        status_lines = [
            ("API Status", "Connected" if self.config_data.get("api_key") else "Disconnected"),
            ("API URL", self.config_data.get("base_url", "Not set")),
            ("Model", self.config_data.get("model", "Not set")),
            ("Max Turns", str(self.config_data.get("max_turns", 30))),
            ("Working Dir", os.getcwd()),
            ("Messages", str(len(self.messages))),
            ("Tools Loaded", str(len(_AVAILABLE_TOOLS))),
        ]

        rows = "".join(
            f'<tr><td style="color:#8b949e;padding:3px 10px;">{k}</td>'
            f'<td style="color:#ffa657;padding:3px 10px;">{v}</td></tr>'
            for k, v in status_lines
        )

        status_html = (
            '<div style="background:#212226;border:1px solid #343539;border-radius:8px;'
            'padding:12px;margin:8px 0;box-shadow: 0 1px 3px rgba(0,0,0,0.3);">'
            '<div style="color:#58a6ff;font-weight:bold;font-size:14px;margin-bottom:8px;">'
            'System Status</div>'
            f'<table style="width:100%;font-size:12px;">{rows}</table>'
            '</div>'
        )
        self._append_to_chat(status_html)

    # ----------------------------------------------------------
    #  设置对话框
    # ----------------------------------------------------------
    def _show_settings_dialog(self):
        """显示设置对话框"""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Settings")
        dialog.setText(
            f"API URL: {self.config_data.get('base_url', 'Not set')}\n"
            f"Model: {self.config_data.get('model', 'Not set')}\n"
            f"Max Turns: {self.config_data.get('max_turns', 30)}\n\n"
            f"To change settings, edit agent_config.json"
        )
        dialog.setIcon(QMessageBox.Information)
        dialog.exec()

    # ----------------------------------------------------------
    #  启动工作线程
    # ----------------------------------------------------------
    def _start_worker(self):
        """启动 LLM 后台工作线程"""
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
            max_turns=self.config_data.get("max_turns", 30)
        )

        # 连接信号
        self.worker.status_update.connect(self._on_status_update)
        self.worker.tool_called.connect(self._on_tool_called)
        self.worker.ai_message.connect(self._on_ai_message)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished_one_round.connect(self._on_finished)

        self.worker.start()

    # ----------------------------------------------------------
    #  信号处理槽函数
    # ----------------------------------------------------------
    def _on_status_update(self, status_text: str):
        """状态更新"""
        color = "#79c0ff"  # 默认蓝色（思考状态）
        if "工具" in status_text or "tool" in status_text.lower():
            color = "#58a6ff"
        elif "完成" in status_text or "成功" in status_text:
            color = "#3fb950"
        elif "错误" in status_text or "熔断" in status_text or "失败" in status_text:
            color = "#f85149"
        elif "达到" in status_text:
            color = "#d29922"

        html = (
            f'<div style="color:{color};font-size:12px;padding:3px 0;'
            f'font-family:Consolas,monospace;">'
            f'{status_text}</div>'
        )
        self._append_to_chat(html)

        # 同步更新系统状态栏
        self.system_status_label.setText(
            f'<span style="color:#79c0ff;">● Working</span>'
            f' &nbsp; &nbsp; {status_text[:60]}'
        )

    def _on_tool_called(self, tool_name: str, params: str, result: str):
        """工具调用反馈"""
        try:
            params_obj = json.loads(params)
            params_str = json.dumps(params_obj, ensure_ascii=False, indent=2)
        except Exception:
            params_str = params

        result_display = result[:300] + "..." if len(result) > 300 else result

        is_success = not ("错误" in result or "failed" in result.lower() or "不可用" in result)
        result_color = "#3fb950" if is_success else "#f85149"
        status_tag = "SUCCESS" if is_success else "FAILED"

        html = (
            f'<div style="background:#212226;border:1px solid #343539;border-radius:8px;'
            f'padding:10px 12px;margin:6px 0;font-family:Consolas,monospace;font-size:12px;'
            f'box-shadow: 0 1px 2px rgba(0,0,0,0.2);">'
            f'<div style="color:#58a6ff;font-weight:bold;">[Tool] {tool_name}</div>'
            f'<div style="color:#484f58;margin:4px 0;">'
            f'  Args: <span style="color:#ffa657;">{params_str}</span></div>'
            f'<div style="color:{result_color};margin:4px 0;">'
            f'  [{status_tag}] <span>{result_display}</span></div>'
            f'</div>'
        )
        self._append_to_chat(html)

    def _on_ai_message(self, message: str):
        """AI 最终文字回复"""
        if "```" in message:
            formatted = self._format_code_blocks(message)
            html = (
                f'<div style="color:#c9d1d9;font-size:14px;line-height:1.7;'
                f'padding:8px 0;">'
                f'<div style="color:#58a6ff;font-weight:bold;margin-bottom:6px;">AI:</div>'
                f'{formatted}</div>'
            )
        else:
            html = (
                f'<div style="color:#c9d1d9;font-size:14px;line-height:1.7;'
                f'padding:8px 0;">'
                f'<div style="color:#58a6ff;font-weight:bold;margin-bottom:6px;">AI:</div>'
                f'{message}</div>'
            )
        self._append_to_chat(html)

    def _format_code_blocks(self, text: str) -> str:
        """将代码块包装为带背景色的 HTML 矩形框"""
        pattern = r'```(\w*)\n(.*?)```'

        def replace_code(match):
            lang = match.group(1) or "code"
            code = match.group(2)
            code = (
                code.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            return (
                f'<div style="background:#161719;border:1px solid #343539;'
                f'border-radius:8px;padding:14px;margin:10px 0;font-family:Consolas,monospace;'
                f'font-size:12px;white-space:pre-wrap;overflow-x:auto;'
                f'box-shadow: 0 2px 4px rgba(0,0,0,0.3);">'
                f'<div style="color:#8b949e;font-size:11px;margin-bottom:6px;">'
                f'{lang}</div>'
                f'<code style="color:#c9d1d9;">{code}</code>'
                f'</div>'
            )

        formatted = re.sub(pattern, replace_code, text, flags=re.DOTALL)
        formatted = formatted.replace("\n", "<br>")
        return formatted

    def _on_error(self, error_text: str):
        """错误信息显示"""
        html = (
            f'<div style="color:#f85149;background:#2d1b1b;border:1px solid #f85149;'
            f'border-radius:8px;padding:10px 12px;margin:6px 0;font-size:13px;'
            f'font-family:Consolas,monospace;">'
            f'{error_text}</div>'
        )
        self._append_to_chat(html)

    def _on_finished(self):
        """对话轮次结束，解锁输入"""
        self._set_input_enabled(True)
        self.system_status_label.setText(self._format_system_status())
        self._update_side_info()
        self.input_edit.setFocus()

    # ----------------------------------------------------------
    #  辅助方法
    # ----------------------------------------------------------
    def _append_to_chat(self, html: str):
        """向聊天显示区追加 HTML 内容"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertHtml(html)
        # 添加分隔线
        self.chat_display.insertHtml(
            '<hr style="border: none; border-top: 1px solid #212226; margin: 4px 0;">'
        )
        # 滚动到底部
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _format_user_message(self, text: str) -> str:
        """格式化用户消息为 HTML"""
        return (
            f'<div style="color:#c9d1d9;font-size:14px;line-height:1.7;padding:8px 0;">'
            f'<div style="color:#ffa657;font-weight:bold;margin-bottom:4px;">You:</div>'
            f'{text}</div>'
        )

    def _update_status_bar(self):
        """更新系统状态栏"""
        self.system_status_label.setText(self._format_system_status())

    def _center_on_screen(self):
        """将窗口居中显示"""
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    # ----------------------------------------------------------
    #  窗口关闭事件
    # ----------------------------------------------------------
    def closeEvent(self, event):
        """关闭窗口时清理线程"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()


# ============================================================
#  程序入口
# ============================================================

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)

    app.setApplicationName("Agent Studio — 本地自主 Agent")
    app.setApplicationDisplayName("Agent Studio")

    window = AgentWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
