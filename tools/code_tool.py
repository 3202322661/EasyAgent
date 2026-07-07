"""
代码文件操作工具模块。

提供项目文件浏览、读取与写入能力：
  - list_project_files: 递归列出目录树
  - read_code_file: 读取文件内容并标注行号
  - write_code_file: 写入内容到文件（自动创建父目录）
"""

import logging
import os
from typing import Optional

from tools._utils import IGNORE_DIRS, ensure_dir

logger = logging.getLogger(__name__)

# ────────────────────────── 常量 ──────────────────────────

MAX_DISPLAY_FILES: int = 150        # 单次列出文件数量上限
MAX_READ_SIZE: int = 15000          # 单次读取文件字符数上限


def list_project_files(dir_path: str) -> str:
    """递归列出指定目录的文件与子目录结构。

    自动过滤 .git、__pycache__、.venv 等无关目录。
    最多显示 {MAX_DISPLAY_FILES} 个文件，超出部分省略。

    Args:
        dir_path: 要遍历的目录路径

    Returns:
        格式化的目录树字符串
    """
    if not os.path.exists(dir_path):
        return f"[ERROR] 目录 '{dir_path}' 不存在。"
    if not os.path.isdir(dir_path):
        return f"[ERROR] '{dir_path}' 不是一个目录。"

    lines: list[str] = [f"目录树: {dir_path}"]
    file_count: int = 0
    truncated = False

    try:
        for root, dirs, files in os.walk(dir_path):
            # 原地过滤忽略目录
            dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)

            level = root.replace(dir_path, '').count(os.sep)
            indent = ' ' * 4 * level

            # 非根目录显示目录名
            if root != dir_path:
                lines.append(f"{indent}{os.path.basename(root)}/")

            sub_indent = ' ' * 4 * (level + 1)
            for filename in sorted(files):
                lines.append(f"{sub_indent}{filename}")
                file_count += 1

                if file_count >= MAX_DISPLAY_FILES:
                    truncated = True
                    break

            if truncated:
                lines.append(f"{sub_indent}... (已显示 {MAX_DISPLAY_FILES} 个文件，后续省略)")
                break

        return "\n".join(lines)

    except PermissionError as e:
        return f"[ERROR] 遍历目录 '{dir_path}' 时权限不足: {e}"
    except Exception as e:
        logger.exception("遍历目录时发生错误")
        return f"[ERROR] 遍历目录 '{dir_path}' 时发生错误: {e}"


def read_code_file(file_path: str) -> str:
    """读取文件内容，自动添加行号。

    超过 {MAX_READ_SIZE} 字符时自动截断。
    仅支持 UTF-8 编码的文本文件。

    Args:
        file_path: 文件路径

    Returns:
        带行号标注的文件内容
    """
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 '{file_path}' 不存在。"

    if not os.path.isfile(file_path):
        return f"[ERROR] '{file_path}' 不是一个文件。"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return f"[ERROR] 文件 '{file_path}' 不是有效的 UTF-8 文本文件，无法读取。"
    except PermissionError:
        return f"[ERROR] 没有权限读取文件 '{file_path}'。"
    except Exception as e:
        logger.exception("读取文件时发生错误")
        return f"[ERROR] 读取文件 '{file_path}' 时发生错误: {e}"

    # 截断过长内容
    truncated = False
    if len(content) > MAX_READ_SIZE:
        content = content[:MAX_READ_SIZE]
        truncated = True

    # 添加行号
    lines = content.split('\n')
    numbered = [f"{i + 1:4d}: {line}" for i, line in enumerate(lines)]

    header = f"文件 '{file_path}' 的内容 ({len(lines)} 行):\n"
    if truncated:
        header = f"文件 '{file_path}' 的内容 (已截断至 {MAX_READ_SIZE} 字符):\n"

    return header + "\n".join(numbered)


def write_code_file(file_path: str, content: str) -> str:
    """写入内容到文件。父目录不存在时自动创建。

    Args:
        file_path: 目标文件路径
        content: 要写入的文本内容

    Returns:
        操作结果说明
    """
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            ensure_dir(dir_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        line_count = content.count('\n') + 1
        return f"[SUCCESS] 文件 '{file_path}' 已写入，共 {line_count} 行。"

    except PermissionError:
        return f"[ERROR] 没有权限写入文件 '{file_path}'。"
    except OSError as e:
        return f"[ERROR] 写入文件 '{file_path}' 时发生系统错误: {e}"
    except Exception as e:
        logger.exception("写入文件时发生错误")
        return f"[ERROR] 写入文件 '{file_path}' 时发生错误: {e}"
