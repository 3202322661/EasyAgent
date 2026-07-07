<p align="center">
  <h1 align="center">🤖 Easy Agents</h1>
  <p align="center">
    大模型智能体工具平台 —— 让 AI 帮你完成真实世界的工作
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=flat&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/LLM-DeepSeek%20%7C%20OpenAI-brightgreen" alt="LLM">
    <img src="https://img.shields.io/badge/Tavily-Search-orange?style=flat" alt="Tavily">
    <img src="https://img.shields.io/badge/OCR-PaddleOCR%20%7C%20Tesseract-blueviolet" alt="OCR">
    <img src="https://img.shields.io/badge/Word-python--docx-green" alt="python-docx">
    <img src="https://img.shields.io/badge/UI-PySide6%20%7C%20PyQt5-brightgreen" alt="UI">
    <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
  </p>
</p>

---

## 📋 项目简介

**Easy Agents** 是一个基于大语言模型（LLM）的轻量级智能体（Agent）框架。用户只需输入**自然语言指令**，系统便会自动理解意图、规划任务、调用工具并返回结果。

提供 **命令行** 和 **图形界面** 两种交互方式，开箱即用。支持天气查询、旅游推荐、代码文件操作、Word 文档自动化、图片 OCR 文字识别、Git 快捷操作、运行脚本与测试等多种功能。

> 💡 **核心理念**：让大模型成为你的"智能助手"，通过工具调用连接真实世界。

---

## 🚀 双模式运行

### 模式一：命令行交互（`main-agent.py`）

轻量级终端交互，适合快速测试和脚本化使用。

```bash
python main-agent.py
```

### 模式二：可视化工作台（`main-window.py`）

基于 **PySide6/PyQt5** 构建的图形界面，提供更直观的操作体验。

```bash
python main-window.py
```

**界面特性：**
- 🎨 现代化 UI 风格（亮色/暗色混合设计）
- 💬 聊天式对话面板，实时展示 AI 回复
- 🔧 右侧面板实时展示工具调用过程（工具名、参数、结果）
- ⚙️ 内嵌配置面板，可视化设置 API Key、模型、地址等
- 📋 工具调用日志树状展示
- 🛑 支持中断（Stop）当前对话

---

## ✨ 核心能力

| 能力 | 说明 | 示例指令 |
|------|------|---------|
| 🌤️ **天气查询** | 实时获取任意城市的天气信息 | _"北京今天天气怎么样？"_ |
| 🗺️ **旅游推荐** | 根据天气情况联网搜索景点与活动推荐 | _"北京下雨了，有什么好玩的？"_ |
| 📂 **文件操作** | 列出目录树、读写代码文件（UTF-8，自动截断过长内容） | _"读取 main-agent.py 的内容"_ |
| 📝 **Word 文档** | 创建/编辑文档，添加段落、标题、表格、分页符，设置字体与段落格式 | _"创建一个项目报告文档"_ |
| 🖼️ **图片 OCR** | 识别图片中的文字（支持中文/英文/数字），读取图片基本信息 | _"识别这张图片中的文字"_ |
| 💻 **终端命令** | 在项目目录下执行 bash 命令，运行 Python 脚本 | _"运行测试用例"_ |
| 🔄 **Git 快捷操作** | 一键完成 git add、commit、push | _"把代码推送到远程仓库"_ |

---

## 🏗️ 项目架构

```
.
├── main-agent.py               # 🧠 主程序入口（命令行版 - LLM对话循环 + 工具调度）
├── main-window.py              # 🖥️ 主程序入口（图形界面版 - PySide6 可视化工作台）
├── agent_config.json           # ⚙️ GUI 配置持久化文件（API Key / 模型 / 地址等）
├── tool_configure.json         # 🔧 工具函数定义（OpenAI Function Calling 格式）
├── EasyAgent.md                # 📄 智能体系统提示词模板（Role / Constraints / Background）
├── ui_guide.txt                # 📋 图形界面操作指南
├── README.md                   # 📖 项目说明
│
└── tools/                      # 📦 工具模块目录（自动加载）
    ├── travel_tool.py          #   ├── 🌤️ 天气查询 & 旅游推荐
    ├── code_tool.py            #   ├── 📂 代码 / 文件操作
    ├── word_tool.py            #   ├── 📝 Word 文档生成与格式编辑
    ├── image_tool.py           #   ├── 🖼️ 图片 OCR 识别与信息提取
    └── bash_tool.py            #   └── 💻 终端命令执行 & Git 快捷操作
```

### 架构亮点

- **自动注册**：`tools/` 目录下的 `.py` 文件会被自动扫描加载，新增工具只需编写函数即可
- **并行执行**：多工具调用使用 `ThreadPoolExecutor` 并发执行，提升响应速度
- **标准协议**：工具定义遵循 OpenAI Function Calling 规范，兼容 DeepSeek / GPT 等模型
- **容错处理**：工具执行失败不会中断主流程，返回错误信息供模型继续决策
- **连续错误熔断**：工具连续失败 3 次后自动终止工具链，强制模型给出最终回复，避免死循环
- **双模式运行**：命令行版适合快速调试，GUI 版提供完整可视化体验

---

## 🛠️ 工具列表

### 🌤️ 旅游工具（`travel_tool.py`）

| 函数名 | 功能 |
|--------|------|
| `get_weather(city)` | 调用 wttr.in API 获取城市实时天气（温度、湿度、风速），支持 HTTP 代理 |
| `get_attraction(city, weather)` | 通过 Tavily 搜索引擎推荐适应当前天气的景点和活动 |

### 📂 代码工具（`code_tool.py`）

| 函数名 | 功能 |
|--------|------|
| `list_project_files(dir_path)` | 递归列出目录树（自动过滤 `.git` / `__pycache__` / `.venv` 等目录，最多显示 150 个文件） |
| `read_code_file(file_path)` | 读取文件内容并显示行号（UTF-8，超过 15000 字符自动截断） |
| `write_code_file(file_path, content)` | 写入内容到文件（自动创建父目录） |

### 🖼️ 图片工具（`image_tool.py`）

| 函数名 | 功能 |
|--------|------|
| `read_image_text(file_path, lang)` | 识别图片中的文字（OCR），支持中英文混合识别，自动切换 pytesseract / PaddleOCR 引擎 |
| `read_image_info(file_path)` | 读取图片基本信息（尺寸、格式、颜色模式、文件大小、EXIF 拍摄信息摘要等） |

### 📝 Word 工具（`word_tool.py`）

| 函数名 | 功能 |
|--------|------|
| `create_word_document(file_path, title)` | 创建空白 Word 文档，可选居中标题 |
| `add_paragraph(file_path, text, ...)` | 添加段落，支持完整的字体格式和段落排版设置（字体、字号、加粗、斜体、颜色、对齐、行距、缩进等） |
| `add_heading(file_path, text, level, ...)` | 添加 1~9 级标题，支持自定义字体、字号、颜色和对齐 |
| `add_table(file_path, data, headers, ...)` | 添加带边框的表格（Table Grid 样式） |
| `add_page_break(file_path)` | 添加分页符 |
| `read_word_text(file_path)` | 读取文档纯文本（带段落编号与样式名称） |
| `read_word_tables(file_path)` | 提取文档中的所有表格数据 |
| `read_word_info(file_path)` | 获取文档概要信息（段落数、表格数、样式列表） |
| `set_paragraph_format(file_path, ...)` | 调整段落排版格式，可指定单个段落或全部段落 |
| `set_run_format(file_path, ...)` | 调整指定段落的字体格式 |
| `set_page_margins(file_path, ...)` | 设置页面边距（单位：英寸） |
| `list_doc_styles(file_path)` | 列出文档中所有可用样式 |

### 💻 Bash 工具（`bash_tool.py`）

| 函数名 | 功能 |
|--------|------|
| `run_bash_command(command, timeout)` | 在项目根目录执行 bash 命令，返回标准输出/错误和返回码，支持超时控制 |
| `git_quick_commit_push(branch, message)` | 一键完成 `git add .` → `git commit` → `git push` |
| `run_python_script(script_path, args)` | 运行指定的 Python 脚本，支持传递命令行参数 |
| `run_tests(test_path, extra_args)` | 运行 pytest 测试，支持指定测试路径和额外参数 |

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 基础依赖：`openai`, `requests`, `tavily-python`, `python-docx`, `Pillow`
- GUI 版本额外依赖：`PySide6`（或 `PyQt5`）

```bash
# 安装基础依赖
pip install openai requests tavily-python python-docx Pillow

# GUI 版本需额外安装
pip install PySide6
# 或使用 PyQt5: pip install PyQt5
```

### OCR 引擎安装（可选，图片识别需要）

```bash
# 方案一：pytesseract（经典稳定，系统级）
pip install pytesseract
# 然后安装 Tesseract OCR 引擎：
#   - Windows: https://github.com/UB-Mannheim/tesseract/wiki
#   - macOS: brew install tesseract
#   - Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim

# 方案二：PaddleOCR（纯 Python，中文效果好）
pip install paddlepaddle paddleocr
```

> 💡 两种 OCR 引擎任选其一即可。系统会自动检测可用引擎，优先使用 pytesseract，失败时自动降级到 PaddleOCR。

### 配置

本项目通过**环境变量**完成核心配置，GUI 版本还支持通过界面面板修改并持久化到 `agent_config.json`：

```bash
# ===== LLM 配置（必填）=====
export DEEPSEEK_API_KEY="your-api-key"        # 大模型 API 密钥

# ===== 搜索引擎配置（旅游推荐功能需要）=====
export TAVILY_API_KEY="your-tavily-api-key"   # Tavily 搜索 API

# ===== 代理配置（可选，适用于受限网络环境）=====
export HTTP_PROXY="http://127.0.0.1:7890"     # HTTP 代理
export HTTPS_PROXY="http://127.0.0.1:7890"    # HTTPS 代理
```

也可以在 `main-agent.py` 中直接修改默认值：

```python
API_KEY = os.environ.get("DEEPSEEK_API_KEY")   # 优先读取环境变量
BASE_URL = "https://api.deepseek.com"           # API 服务地址（可切换为 OpenAI / 其他）
MODEL_ID = "deepseek-v4-flash"                  # 模型名称
```

> 💡 系统支持任何兼容 OpenAI API 格式的大模型（DeepSeek、GPT、Claude 等），只需修改 `BASE_URL` 和 `MODEL_ID` 即可切换。

### 运行

```bash
# 命令行模式
python main-agent.py

# 图形界面模式
python main-window.py
```

#### 命令行交互示例

```
User: 北京今天天气怎么样？
🤖 → 北京天气：多云，温度：12°C，湿度：45%，风速：15 km/h

User: 北京下雨了，推荐一些室内的景点
🤖 → 【搜索中...】推荐故宫博物院、国家博物馆、798艺术区...

User: 创建一个Word文档，标题为"我的旅游计划"
🤖 → ✓ Word 文档已创建: '我的旅游计划.docx'

User: 识别这张图片中的文字
🤖 → ━━━ OCR 识别结果 ━━━
      文件: 会议记录.png
      识别引擎: pytesseract
      识别文本行数: 15
      ...

User: 运行所有的测试用例
🤖 → 命令执行成功！[返回码] 0

User: 把代码推送到远程仓库
🤖 → 命令执行成功！已推送至 origin/main

输入 exit 或 quit 退出程序。
```

---

## 🔧 高级特性

### 工具自动注册

在 `tools/` 目录下新建 `.py` 文件，定义普通函数并添加类型注解，即可被自动发现和注册：

```python
# tools/my_tool.py
def my_custom_function(param1: str, param2: int) -> str:
    """函数 docstring 会作为工具描述传给大模型"""
    return f"处理结果: {param1} x {param2}"
```

### 多工具并行调用

当用户请求需要多个工具协作时（如"查询北京的天气并推荐景点"），系统会自动并发调用，显著提升效率。

### 双引擎 OCR 自动切换

图片文字识别功能支持 **pytesseract** 和 **PaddleOCR** 两种引擎，系统会自动检测并优先使用 pytesseract（失败时自动降级到 PaddleOCR），无需手动配置。

### 多轮对话与熔断机制

- 支持最多 **30 轮** 自动工具调用链，模型会根据工具返回结果自主判断是否需要继续调用
- 当工具**连续失败 3 次**时，系统自动触发熔断机制，强制模型停止工具调用、直接向用户说明任务为何无法完成

### 网络代理支持

在受限网络环境下，可通过设置 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量使天气查询等 HTTP 请求正常通行。

### GUI 配置持久化

图形界面版支持通过设置面板修改 API Key、Base URL、模型名称和最大对话轮数，配置会自动保存到 `agent_config.json` 文件中，下次启动自动加载。

---

## 📦 依赖说明

| 依赖 | 用途 | 必需 |
|------|------|:----:|
| `openai` | 调用 LLM API（兼容 OpenAI / DeepSeek 等） | ✅ |
| `requests` | 发送 HTTP 请求获取天气数据 | ✅ |
| `tavily-python` | 联网搜索旅游景点推荐 | ✅ |
| `python-docx` | 创建和编辑 Word 文档 | ✅ |
| `Pillow` | 图片处理（打开、读取格式/尺寸/EXIF 等） | ✅ |
| `PySide6` 或 `PyQt5` | 图形界面框架（GUI 模式需要） | ⬜ |
| `pytesseract` | OCR 文字识别引擎（方案一） | ⬜ |
| `paddlepaddle` + `paddleocr` | OCR 文字识别引擎（方案二，中文效果更优） | ⬜ |

---

## 📄 开源协议

本项目基于 **MIT License** 开源，仅供学习和参考使用。

---

<p align="center">
  <sub>Made with ❤️ | 如有问题请提交 <a href="#">Issue</a></sub>
</p>
