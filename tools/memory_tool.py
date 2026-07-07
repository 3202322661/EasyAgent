"""
用户记忆系统工具模块。

提供智能体的个性化记忆管理能力：
  - read_user_memory: 读取用户记忆
  - update_user_memory: 追加/更新用户记忆
  - list_memory_categories: 列出记忆分类与状态
  - consolidate_memory_summary: 生成记忆摘要（用于注入系统提示词）

记忆存储：所有记忆以 Markdown 文件形式存放在项目根目录的 memory/ 目录下。
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ────────────────────────── 常量 ──────────────────────────

MEMORY_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory"
)

MAX_CATEGORY_SIZE: int = 5000       # 每个分类文件最大字符数
SUMMARY_MAX_LENGTH: int = 1000      # 记忆摘要最大长度

CATEGORY_FILE_MAP: Dict[str, str] = {
    "profile":     "user_profile.md",
    "preferences": "preferences.md",
    "history":     "interaction_history.md",
    "knowledge":   "knowledge_base.md",
}

CATEGORY_LABELS: Dict[str, str] = {
    "user_profile.md":         "👤 用户档案",
    "preferences.md":          "⚙️ 偏好设置",
    "interaction_history.md":  "📜 交互历史",
    "knowledge_base.md":       "📚 知识库",
}


# ────────────────────────── 内部辅助 ──────────────────────────

def _ensure_memory_dir() -> None:
    """确保 memory 目录存在。"""
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _get_memory_files() -> List[str]:
    """获取 memory 目录下所有 .md 文件（排序）。"""
    _ensure_memory_dir()
    files: List[str] = []
    try:
        for f in os.listdir(MEMORY_DIR):
            if f.endswith(".md") and f != "README.md":
                files.append(f)
    except OSError:
        pass
    return sorted(files)


def _read_file_safe(filepath: str) -> str:
    """安全读取文件，出错返回空字符串。"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _write_file_safe(filepath: str, content: str) -> bool:
    """安全写入文件。"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error("写入文件 '%s' 失败: %s", filepath, e)
        return False


# ────────────────────────── 公开接口 ──────────────────────────

def read_user_memory(category: str = "") -> str:
    """读取用户记忆文档。

    Args:
        category: 记忆分类。可选值: 'profile', 'preferences', 'history', 'knowledge'
                  传空字符串则读取全部记忆。

    Returns:
        格式化的记忆内容
    """
    _ensure_memory_dir()

    # 读取单个分类
    if category and category in CATEGORY_FILE_MAP:
        filepath = os.path.join(MEMORY_DIR, CATEGORY_FILE_MAP[category])
        if not os.path.exists(filepath):
            return f"[INFO] 记忆分类 '{category}' 暂无记录，将在使用中自动生成。"
        content = _read_file_safe(filepath)
        if not content.strip():
            return f"[INFO] 记忆分类 '{category}' 当前为空。"
        return f"## {category}\n\n{content}"

    # 读取全部记忆
    memory_files = _get_memory_files()
    if not memory_files:
        return "[INFO] 暂无用户记忆数据。开始使用后将自动积累。"

    parts: List[str] = []
    for fname in memory_files:
        filepath = os.path.join(MEMORY_DIR, fname)
        content = _read_file_safe(filepath)
        if content.strip():
            display_name = fname.replace("_", " ").replace(".md", "").title()
            parts.append(f"--- {display_name} ---\n{content.strip()}")

    if not parts:
        return "[INFO] 所有记忆文件均为空，等待用户使用后生成。"

    return "\n\n".join(parts)


def list_memory_categories() -> str:
    """列出所有记忆分类及其当前状态。

    Returns:
        格式化的分类列表
    """
    _ensure_memory_dir()
    memory_files = _get_memory_files()

    if not memory_files:
        return "[INFO] 暂无记忆文件。系统支持以下分类: profile, preferences, history, knowledge"

    lines = ["## 记忆分类状态\n"]
    for fname in memory_files:
        filepath = os.path.join(MEMORY_DIR, fname)
        try:
            size = os.path.getsize(filepath)
        except OSError:
            size = 0
        status = "有数据" if size > 50 else "待填充"
        display = fname.replace("_", " ").replace(".md", "").title()
        lines.append(f"- **{display}** ({fname}) — {status} ({size} 字节)")

    return "\n".join(lines)


def update_user_memory(category: str, content: str) -> str:
    """更新用户记忆（增量追加模式）。

    新内容追加到已有内容之后，不会覆盖。每个分类文件有容量上限（{MAX_CATEGORY_SIZE} 字符），
    超出时自动截断保留最新内容。

    Args:
        category: 记忆分类: 'profile', 'preferences', 'history', 'knowledge'
        content: 要记录的内容（Markdown 格式）

    Returns:
        操作结果
    """
    _ensure_memory_dir()

    if category not in CATEGORY_FILE_MAP:
        valid = ", ".join(CATEGORY_FILE_MAP.keys())
        return f"[ERROR] 无效的记忆分类 '{category}'。有效分类: {valid}"

    fname = CATEGORY_FILE_MAP[category]
    filepath = os.path.join(MEMORY_DIR, fname)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        existing = _read_file_safe(filepath)

        if not existing.strip():
            # 新建文件
            new_content = content.strip()
            new_content += f"\n\n---\n*最后更新: {timestamp}*"
            if not _write_file_safe(filepath, new_content):
                return f"[ERROR] 写入记忆文件失败。"

        else:
            # 追加内容（先移除旧的时间戳行）
            lines = [l for l in existing.split("\n")
                     if not l.strip().startswith("*最后更新:")]
            existing_clean = "\n".join(lines).rstrip()

            appended = (
                f"{existing_clean}\n\n"
                f"### 更新于 {timestamp}\n"
                f"{content.strip()}\n\n"
                f"---\n"
                f"*最后更新: {timestamp}*"
            )

            # 容量控制：超过上限时截断
            if len(appended) > MAX_CATEGORY_SIZE:
                truncated = appended[-4500:]
                # 尝试从最近的标题处截断以保持格式整洁
                header_pos = truncated.find("\n##")
                if header_pos > 0:
                    truncated = truncated[header_pos:].strip()
                appended = (
                    f"*(历史记录过长已截断，仅保留最新内容)*\n\n"
                    f"{truncated}\n\n"
                    f"---\n"
                    f"*最后更新: {timestamp}*"
                )

            if not _write_file_safe(filepath, appended):
                return f"[ERROR] 写入记忆文件失败。"

        return f"[SUCCESS] 记忆 '{category}' 已更新 ({timestamp})"

    except Exception as e:
        logger.exception("更新记忆失败")
        return f"[ERROR] 更新记忆失败: {e}"


def consolidate_memory_summary() -> str:
    """生成精炼的用户记忆摘要。

    从所有记忆文件中提取关键信息并压缩，用于注入系统提示词上下文。

    Returns:
        记忆摘要（不超过 {SUMMARY_MAX_LENGTH} 字符）
    """
    _ensure_memory_dir()
    memory_files = _get_memory_files()

    summary_parts: List[str] = []

    for fname in memory_files:
        filepath = os.path.join(MEMORY_DIR, fname)
        content = _read_file_safe(filepath)
        if not content.strip():
            continue

        label = CATEGORY_LABELS.get(fname, fname.replace(".md", ""))

        # 提取关键行
        key_lines: List[str] = []
        for line in content.split("\n"):
            stripped = line.strip()
            if (stripped
                    and not stripped.startswith("#")
                    and not stripped.startswith("---")
                    and not stripped.startswith("*最后更新")
                    and not stripped.startswith("###")):
                key_lines.append(stripped)

        if key_lines:
            # 每分类最多取 10 条
            text = "; ".join(key_lines[:10])
            summary_parts.append(f"[{label}] {text}")

    if not summary_parts:
        return "[记忆系统] 暂无用户记忆数据。"

    full_summary = " | ".join(summary_parts)

    # 控制长度
    if len(full_summary) > SUMMARY_MAX_LENGTH:
        full_summary = full_summary[:SUMMARY_MAX_LENGTH - 3] + "..."

    return full_summary
