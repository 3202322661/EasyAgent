import os.path

def list_project_files(dir_path: str) -> str:
    if not os.path.exists(dir_path):
        return f"[ERROR] 目录 {dir_path} 不存在。"

    ignore_dirs = {".git", "__pycache__", ".venv", ".env", ".idea", ".vscode"}

    tree_lines = [f"工作区目录树 (路径：{dir_path})"]
    file_count = 0
    max_files = 150

    try:
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            level = root.replace(dir_path, '').count(os.sep)
            indent = ' ' * 4 * level

            if root != dir_path:
                tree_lines.append(f"{indent}{os.path.basename(root)}/")

            sub_indent = ' ' * 4 * (level + 1)
            for file in files:
                tree_lines.append(f"{sub_indent}{file}")
                file_count += 1
                if file_count >= max_files:
                    tree_lines.append(f"{sub_indent}... (已显示 {max_files} 个文件，省略其余文件)")
                    return "\n".join(tree_lines)
        return "\n".join(tree_lines)
    except Exception as e:
        return f"[ERROR] 遍历目录 {dir_path} 时发生错误: {str(e)}"

def read_code_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"[ERROR] 文件 {file_path} 不存在。"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if len(content) > 15000:
            content = content[:15000] + "\n\n... (文件内容过长，已截断)"

        lines = content.split('\n')
        numbered_lines = [f"{i + 1:4}: {line}" for i, line in enumerate(lines)]

        return f"文件 '{file_path}'的内容:\n" + "\n".join(numbered_lines)
    except UnicodeDecodeError:
        return f"[ERROR] 文件 {file_path} 不是有效的 UTF-8 编码文本文件。"
    except Exception as e:
        return f"[ERROR] 读取文件 {file_path} 时发生错误: {str(e)}"

def write_code_file(file_path: str, content: str) -> str:
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"文件 '{file_path}' 已成功写入，共写入{len(content.splitlines())}。"
    except Exception as e:
        return f"[ERROR] 写入文件 {file_path} 时发生错误: {str(e)}"