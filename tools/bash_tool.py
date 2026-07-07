"""
Bash 命令执行工具模块。

提供安全的本地终端命令执行能力，包括：
  - run_bash_command: 执行单条或短链 Bash 命令
  - git_quick_commit_push: Git 一键提交推送
  - run_python_script: 运行 Python 脚本
  - run_tests: 运行 pytest 测试

安全机制：
  - 命令白名单校验，拒绝未授权的危险指令
  - 超时控制，防止命令挂死
  - 工作目录线程本地化，避免并发冲突
"""

import logging
import os
import re
import subprocess
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# ────────────────────────── 常量 ──────────────────────────

PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 线程本地存储 —— 每个线程维护独立的工作目录，避免并发冲突
_thread_local = threading.local()

# 允许执行的命令前缀白名单（仅首词）
ALLOWED_PREFIXES: set[str] = {
    "git", "python", "python3", "pytest", "bash", "sh",
    "ls", "cat", "echo", "cd", "mkdir", "rm", "cp", "mv",
    "touch", "chmod", "make", "npm", "node", "npx",
    "pip", "pip3", "poetry", "uv", "pdm", "tox",
    "flake8", "black", "mypy", "ruff", "pre-commit",
    "pylint", "isort", "bandit", "coverage",
    "dir", "type", "find", "grep", "awk", "sed",
    "sort", "uniq", "wc", "head", "tail", "diff",
    "tar", "gzip", "unzip", "zip", "curl", "wget",
    "ssh", "scp", "docker", "kubectl", "helm",
}

# 用于分割复合命令的正则 —— 匹配 &&、;、|| 和换行符
# 注意：不将 | (管道) 视为分隔符，因为管道前后的命令应统一审查
COMMAND_SPLIT_PATTERN = re.compile(r'(?:&&|\|\||;|\n|\r\n)+')


def _get_cwd() -> str:
    """获取当前线程的工作目录。"""
    if not hasattr(_thread_local, "cwd"):
        _thread_local.cwd = PROJECT_ROOT
    return _thread_local.cwd


def _set_cwd(path: str) -> None:
    """设置当前线程的工作目录。"""
    _thread_local.cwd = path


def _validate_command(command: str) -> Optional[str]:
    """验证命令安全性。

    检查复合命令中的每个子命令是否以允许的前缀开头。

    Returns:
        错误消息字符串，None 表示验证通过
    """
    if not command or not command.strip():
        return "[ERROR] 命令不能为空。"

    raw = command.strip()
    # 分割复合命令
    sub_commands = COMMAND_SPLIT_PATTERN.split(raw)

    for sub in sub_commands:
        tokens = sub.strip().split()
        if not tokens:
            continue
        first_word = tokens[0]
        # 跳过环境变量赋值前缀 (如 VAR=value command)
        if "=" in first_word:
            continue
        if first_word not in ALLOWED_PREFIXES:
            return (
                f"[STATUS: SECURITY_DENIED]\n"
                f"拒绝执行原因: 检测到未授权的指令 '{first_word}'。\n"
                f"允许的命令前缀: {', '.join(sorted(ALLOWED_PREFIXES))}\n"
                f"请修正指令后重试。"
            )

    return None  # 验证通过


def run_bash_command(command: str, timeout: int = 120) -> str:
    """在本地终端安全执行 Bash 命令。

    执行前会对命令进行白名单校验。支持 cd 切换当前线程的工作目录。
    返回结果的头部始终包含状态标记 [STATUS: SUCCESS] 或 [STATUS: FAILED]。

    Args:
        command: 要执行的 Bash 命令（支持 &&、||、; 连接）
        timeout: 超时时间（秒），默认 120

    Returns:
        格式化的执行结果字符串
    """
    # 空命令检查
    validation_error = _validate_command(command)
    if validation_error:
        return validation_error

    raw = command.strip()
    cwd = _get_cwd()

    # ── 处理 cd 命令 ──
    if raw.startswith("cd "):
        target_dir = raw[3:].strip().strip('"').strip("'")
        if not target_dir:
            return "[STATUS: FAILED]\ncd 命令需要指定目标目录。"

        new_path = os.path.abspath(os.path.join(cwd, target_dir))
        if os.path.isdir(new_path):
            _set_cwd(new_path)
            return f"[STATUS: SUCCESS]\n工作目录已切换至: {new_path}"
        else:
            return f"[STATUS: FAILED]\n目录不存在或不是有效目录: {new_path}"

    # ── 执行命令 ──
    try:
        result = subprocess.run(
            raw,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        parts: list[str] = []

        # 状态头
        if result.returncode == 0:
            parts.append("[STATUS: SUCCESS] 命令执行完毕。")
        else:
            parts.append(
                f"[STATUS: FAILED] 命令返回非零退出码 ({result.returncode})。\n"
                f"请检查下方 STDERR 信息并修正后重试。"
            )

        # 标准输出
        if result.stdout and result.stdout.strip():
            parts.append(f"--- STDOUT ---\n{result.stdout.rstrip()}")

        # 标准错误
        if result.stderr and result.stderr.strip():
            parts.append(f"--- STDERR ---\n{result.stderr.rstrip()}")

        parts.append(f"--- 当前目录: {cwd} ---")

        return "\n\n".join(parts)

    except subprocess.TimeoutExpired:
        return (
            f"[STATUS: TIMEOUT_ERROR]\n"
            f"命令执行超时（{timeout} 秒）被强制终止。\n"
            f"建议：跳过交互式提示（如添加 -y 参数）、或缩小执行范围。"
        )
    except FileNotFoundError as e:
        return f"[ERROR] 未找到可执行文件: {e}"
    except PermissionError as e:
        return f"[ERROR] 权限不足: {e}"
    except OSError as e:
        return f"[ERROR] 系统调用错误: {e}"
    except Exception as e:
        logger.exception("执行命令时发生未知错误")
        return f"[ERROR] 执行命令时发生未知错误: {e}"


def git_quick_commit_push(branch: str = "main", message: str = "auto commit") -> str:
    """一键 Git 操作：add → commit → push。

    Args:
        branch: 目标分支名称，默认 'main'
        message: 提交信息，默认 'auto commit'
    """
    # 对提交信息进行基础转义
    safe_message = message.replace('"', '\\"')
    command = f'git add . && git commit -m "{safe_message}" && git push origin {branch}'
    return run_bash_command(command, timeout=300)


def run_python_script(script_path: str, args: str = "") -> str:
    """运行指定的 Python 脚本。

    Args:
        script_path: 脚本路径（相对或绝对）
        args: 传递给脚本的命令行参数
    """
    command = f"python {script_path} {args}".strip()
    return run_bash_command(command, timeout=300)


def run_tests(test_path: str = "tests/", extra_args: str = "") -> str:
    """运行 pytest 测试。

    Args:
        test_path: 测试文件或目录路径，默认 'tests/'
        extra_args: 额外 pytest 参数，如 '-v', '-x', '--cov'
    """
    command = f"python -m pytest {test_path} {extra_args}".strip()
    return run_bash_command(command, timeout=600)
