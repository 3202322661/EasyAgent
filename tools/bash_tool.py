import re
import subprocess
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CURRENT_WDIR = PROJECT_ROOT

ALLOWED_PREFIXES = [
    "git",
    "python",
    "python3",
    "pytest",
    "bash",
    "sh",
    "ls",
    "cat",
    "echo",
    "cd",
    "mkdir",
    "rm",
    "cp",
    "mv",
    "touch",
    "chmod",
    "make",
    "npm",
    "node",
    "pip",
    "pip3",
    "poetry",
    "uv",
    "pdm",
    "tox",
    "flake8",
    "black",
    "mypy",
    "ruff",
    "pre-commit",
]

def run_bash_command(command: str, timeout: int = 120) -> str:
    global CURRENT_WDIR

    if not command or not command.strip():
        return "[ERROR] 命令不能为空。"

    raw_command = command.strip()

    tokens = re.split(r'[&&|;\n]+', raw_command)

    for token in tokens:
        sub_cmd = token.strip().split()
        if sub_cmd:
            first_word = sub_cmd[0]
            if first_word not in ALLOWED_PREFIXES:
                return (
                    f"[STATUS: SECURITY_DENIED]\n"
                    f"拒绝执行原因: 检测到未授权的指令或敏感操作 '{first_word}'。\n"
                    f"安全准则: 仅允许调用以下工具链: {', '.join(ALLOWED_PREFIXES)}。\n"
                    f"请修正你的行为，停止尝试危险命令。"
                )

    if raw_command.startswith("cd "):
        target_dir = raw_command[3:].strip().strip('"').strip("'")

        new_path = os.path.abspath(os.path.join(CURRENT_WDIR, target_dir))
        if os.path.isdir(new_path):
            CURRENT_WDIR = new_path
            return f"[STATUS: SUCCESS]\n成功切换目录！当前工作目录已变更为: {CURRENT_WDIR}"
        else:
            return f"[STATUS: FAILED]\n切换目录失败：路径不存在或不是一个有效的目录 -> {new_path}"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=CURRENT_WDIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output_parts = []
        if result.returncode == 0:
            output_parts.append("[STATUS: SUCCESS] 命令顺利执行完毕。\n")
        else:
            output_parts.append(
                f"[STATUS: FAILED] 命令执行结束，但系统返回了非零错误码 ({result.returncode})。\n"
                f"指导建议: 请检查下方 [标准错误] 中的提示，并修正你的参数或代码逻辑后重试。\n"
            )

        if result.stdout and result.stdout.strip():
            output_parts.append(f"--- [标准输出 (STDOUT)] ---\n{result.stdout.rstrip()}")

        if result.stderr and result.stderr.strip():
            output_parts.append(f"--- [标准错误 (STDERR)] ---\n{result.stderr.rstrip()}")

        output_parts.append(f"\n--- [当前环境上下文] ---\n当前目录位置: {CURRENT_WDIR}")

        return "\n\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return (
            f"[STATUS: TIMEOUT_ERROR]\n"
            f"命令执行由于超时被系统强制掐断（限时 {timeout} 秒）。\n"
            f"大模型排查建议: 该命令可能触发了交互式卡住（如等待用户输入 Y/N）、或者是耗时超长的全量编译。请尝试增加参数跳过交互（如 -y），或缩短执行范围。"
        )
    except FileNotFoundError as e:
        return f"[ERROR] 未找到可执行文件或目录不存在: {str(e)}"
    except PermissionError as e:
        return f"[ERROR] 权限不足: {str(e)}"
    except OSError as e:
        return f"[ERROR] 系统调用错误: {str(e)}"
    except Exception as e:
        return f"[ERROR] 执行命令时发生未知错误: {str(e)}"

def git_quick_commit_push(branch: str = "main", message: str = "auto commit") -> str:
    command = f'git add . && git commit -m "{message}" && git push origin {branch}'
    return run_bash_command(command, timeout=300)

def run_python_script(script_path: str, args: str = "") -> str:
    command = f"python3 {script_path} {args}".strip()
    return run_bash_command(command, timeout=300)

def run_tests(test_path: str = "tests/", extra_args: str = "") -> str:
    command = f"python3 -m pytest {test_path} {extra_args}".strip()
    return run_bash_command(command, timeout=600)
