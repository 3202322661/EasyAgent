"""
共享工具模块 — 提供所有工具模块共用的辅助函数、常量与安全操作。

功能:
  - 颜色值解析（英文名称 / HEX → RGB 元组）
  - 对齐方式解析
  - 防御性文件保存（临时文件 + 原子替换）
  - 文件大小格式化
  - 工具执行结果状态判断
  - 统一日志记录
"""

import logging
import os
import re
import shutil
import tempfile
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("tools")

# ────────────────────────── 颜色名称映射表 ──────────────────────────
# 返回值统一为 (R, G, B) 整数元组，各工具模块自行转换为对应的 RGBColor 类型

COLOR_NAME_MAP: Dict[str, Tuple[int, int, int]] = {
    "red":        (0xFF, 0x00, 0x00),
    "green":      (0x00, 0x80, 0x00),
    "blue":       (0x00, 0x00, 0xFF),
    "black":      (0x00, 0x00, 0x00),
    "white":      (0xFF, 0xFF, 0xFF),
    "yellow":     (0xFF, 0xFF, 0x00),
    "orange":     (0xFF, 0xA5, 0x00),
    "purple":     (0x80, 0x00, 0x80),
    "gray":       (0x80, 0x80, 0x80),
    "dark_red":   (0x8B, 0x00, 0x00),
    "dark_green": (0x00, 0x64, 0x00),
    "dark_blue":  (0x00, 0x00, 0x8B),
    "light_gray": (0xD3, 0xD3, 0xD3),
    "cyan":       (0x00, 0xFF, 0xFF),
    "magenta":    (0xFF, 0x00, 0xFF),
    "brown":      (0xA5, 0x2A, 0x2A),
    "navy":       (0x00, 0x00, 0x80),
    "teal":       (0x00, 0x80, 0x80),
}

# 支持带空格的别名
COLOR_ALIASES = {
    "dark red":   "dark_red",
    "dark green": "dark_green",
    "dark blue":  "dark_blue",
    "light gray": "light_gray",
    "light grey": "light_gray",
}


def parse_color(color_val: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """解析颜色值，支持英文名称和 HEX 格式。

    Args:
        color_val: 颜色字符串，如 'red', '#FF0000', 'FF0000'

    Returns:
        (R, G, B) 整数元组，解析失败返回 None
    """
    if not color_val or not color_val.strip():
        return None

    raw = color_val.strip()
    if not raw:
        return None

    # 尝试英文名称
    key = raw.lower().replace(" ", "_")
    if key in COLOR_ALIASES:
        key = COLOR_ALIASES[key]
    if key in COLOR_NAME_MAP:
        return COLOR_NAME_MAP[key]

    # 尝试 HEX 格式
    hex_str = raw.lstrip("#")
    if len(hex_str) == 6 and all(c in "0123456789abcdefABCDEF" for c in hex_str):
        try:
            return (
                int(hex_str[0:2], 16),
                int(hex_str[2:4], 16),
                int(hex_str[4:6], 16),
            )
        except ValueError:
            pass

    return None


def parse_alignment(align_str: Optional[str], align_map: Dict[str, Any]) -> Optional[Any]:
    """解析对齐方式字符串到对应的枚举值。

    Args:
        align_str: 对齐字符串，如 'left', 'center', 'right', 'justify'
        align_map: 字符串到枚举值的映射字典

    Returns:
        对应的枚举值，解析失败返回 None
    """
    if not align_str:
        return None
    return align_map.get(align_str.strip().lower())


def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读的文件大小字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def safe_save_to_temp(save_func, file_path: str, suffix: str = ".tmp") -> bool:
    """防御性保存：先写入临时文件，再原子替换目标文件。

    此方法可防止：
      - 保存过程中崩溃导致原文件损坏
      - 跨磁盘移动失败
      - 文件被其他程序占用

    Args:
        save_func: 接受临时路径并执行保存的可调用对象
        file_path: 最终目标文件路径
        suffix: 临时文件后缀

    Returns:
        True 表示保存成功，False 表示失败
    """
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)

        # 执行实际保存
        save_func(tmp_path)

        # 原子替换原文件
        shutil.copy2(tmp_path, file_path)
        return True

    except PermissionError:
        logger.error("保存失败：文件 '%s' 正被其他程序占用。", file_path)
        return False
    except OSError as e:
        logger.error("保存 '%s' 时发生系统错误: %s", file_path, e)
        return False
    except Exception as e:
        logger.error("保存 '%s' 时发生未知异常: %s", file_path, e)
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def is_error_result(result: str) -> bool:
    """判断工具执行结果是否为错误。

    通过检查结果字符串中是否包含 [ERROR] 或 [STATUS: FAILED] 等标记来判断。
    """
    if not result:
        return False
    error_markers = ["[ERROR]", "[STATUS: FAILED]", "[STATUS: SECURITY_DENIED]",
                     "[STATUS: TIMEOUT_ERROR]", "[STATUS: UNRESOLVABLE]"]
    return any(marker in result for marker in error_markers)


def truncate_display(text: str, max_len: int = 300) -> str:
    """截断文本用于显示，过长时添加省略标记。"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def ensure_dir(dir_path: str) -> None:
    """确保目录存在，不存在则自动创建。"""
    if dir_path and not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)


def safe_read_file(file_path: str, encoding: str = "utf-8") -> Optional[str]:
    """安全读取文件内容，出错返回 None。"""
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception:
        return None


# ────────────────────────── 忽略目录列表 ──────────────────────────
IGNORE_DIRS = {".git", "__pycache__", ".venv", ".env", ".idea", ".vscode", ".pytest_cache",
               "node_modules", ".mypy_cache", ".tox", "dist", "build", "*.egg-info"}
