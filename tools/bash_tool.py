import subprocess
import os
import shlex

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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
    if not command or not command.strip():
        return "[ERROR] 命令不能为空。"

    first_token = command.strip().split()[0] if command.strip().split() else ""

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output_parts = []

        if result.stdout:
            output_parts.append(f"[标准输出]\n{result.stdout.rstrip()}")

        if result.stderr:
            output_parts.append(f"[标准错误]\n{result.stderr.rstrip()}")

        output_parts.append(f"[返回码] {result.returncode}")

        if result.returncode == 0:
            output_parts.insert(0, "命令执行成功！")
        else:
            output_parts.insert(0, "命令执行失败，返回码非零。")

        return "\n\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"[ERROR] 命令执行超时（超过 {timeout} 秒）。请尝试缩短命令或增大 timeout 参数。"
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
