import subprocess
import signal
import os
from pathlib import Path
from typing import Optional, List, Dict
from langchain.tools import tool

MAX_EXECUTION_TIME = 60
MAX_OUTPUT_SIZE = 10000
ALLOWED_DIRS = {".", "./", "/"}


def validate_file_path(file_path: str) -> tuple[bool, str, str]:
    """
    验证文件路径安全性

    Args:
        file_path: 文件路径

    Returns:
        (是否有效, 绝对路径, 错误信息)
    """
    path = Path(file_path)

    try:
        abs_path = path.resolve()
    except Exception as e:
        return False, "", f"❌ 路径解析失败: {str(e)}"

    if not abs_path.exists():
        return False, "", f"❌ 文件不存在: {file_path}"

    if not abs_path.is_file():
        return False, "", f"❌ 不是文件: {file_path}"

    if abs_path.stat().st_size > 1048576:  # 1MB limit
        return False, "", f"❌ 文件过大（超过 1MB）"

    return True, str(abs_path), ""


def validate_directory_path(dir_path: str) -> tuple[bool, str, str]:
    """
    验证目录路径安全性

    Args:
        dir_path: 目录路径

    Returns:
        (是否有效, 绝对路径, 错误信息)
    """
    path = Path(dir_path)

    try:
        abs_path = path.resolve()
    except Exception as e:
        return False, "", f"❌ 路径解析失败: {str(e)}"

    if not abs_path.exists():
        return False, "", f"❌ 目录不存在: {dir_path}"

    if not abs_path.is_dir():
        return False, "", f"❌ 不是目录: {dir_path}"

    return True, str(abs_path), ""


def validate_rej_file(
    file_path: str, base_dir: Path | None = None
) -> tuple[bool, Path, str]:
    """
    验证 .rej 文件路径安全性和合法性

    只允许删除 .rej 扩展名的文件，且必须在允许的目录内

    Args:
        file_path: 文件路径
        base_dir: 允许的基础目录（默认为当前工作目录）

    Returns:
        (是否有效, 绝对路径对象, 错误信息)
    """
    path = Path(file_path)

    if not path.suffix == ".rej":
        return False, Path(), "❌ 只能删除 .rej 文件"

    try:
        abs_path = path.resolve()
    except Exception as e:
        return False, Path(), f"❌ 路径解析失败: {str(e)}"

    if not abs_path.exists():
        return False, Path(), f"❌ 文件不存在: {file_path}"

    if not abs_path.is_file():
        return False, Path(), f"❌ 不是文件: {file_path}"

    allowed_dir = (base_dir or Path.cwd()).resolve()
    try:
        abs_path.relative_to(allowed_dir)
        return True, abs_path, ""
    except ValueError:
        return False, Path(), f"❌ 文件不在允许的目录内"


@tool
def git_apply_patch(
    patch_file: str, reject: bool = True, working_dir: str = None
) -> str:
    """
    应用 Git patch 文件，支持 reject 模式处理冲突。

    该工具通过 git am 命令安全地应用 patch 文件，具有以下安全限制：
    - 文件必须存在且是有效的 patch 文件
    - 默认使用 --reject 选项处理冲突
    - 自动保留 patch 中的 commit 信息
    - 支持在指定目录下执行

    Args:
        patch_file: Patch 文件的路径
        reject: 是否使用 --reject 选项（默认 True）
        working_dir: 执行命令的工作目录（可选）

    Returns:
        应用结果信息，包括成功或错误信息

    示例：
        git_apply_patch("feature.patch")
        git_apply_patch("fix.patch", reject=True, working_dir="/path/to/project")
    """
    print(f"Tool[git_apply_patch]: {patch_file}")

    is_valid, abs_path, error_msg = validate_file_path(patch_file)
    if not is_valid:
        print("error_msg:", error_msg)
        return error_msg

    result_parts = []

    try:
        command = ["git", "am"]

        if reject:
            command.append("--reject")

        command.append(abs_path)

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir or os.getcwd(),
        )

        try:
            stdout, stderr = process.communicate(timeout=MAX_EXECUTION_TIME)

            if process.returncode != 0:
                stderr = stderr or f"进程退出码: {process.returncode}"
                result_parts.append(f"❌ Git am 失败:\n{stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            result_parts.append(
                f"⏰ 执行超时（{MAX_EXECUTION_TIME}秒），进程已被终止\n\n输出:\n{stdout[:1000]}"
            )

        if stdout:
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (输出被截断)"
            result_parts.append(f"📤 Git am 输出:\n{stdout}")

        if stderr:
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (错误输出被截断)"
            result_parts.append(f"⚠️ Git am 错误/警告:\n{stderr}")

        if len(result_parts) == 1:
            result_parts.append("✅ Git am 执行完成")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"


@tool
def git_continue_apply(working_dir: str = None) -> str:
    """
    继续完成之前中断的 patch 应用。

    该工具通过 git am --continue 命令继续完成 patch 应用过程。
    支持在指定目录下执行。

    Args:
        working_dir: 执行命令的工作目录（可选）

    Returns:
        继续操作结果信息

    示例：
        git_continue_apply()
        git_continue_apply(working_dir="/path/to/project")
    """
    print("Tool[git_continue_apply]:")

    result_parts = []

    try:
        command = ["git", "am", "--continue"]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir or os.getcwd(),
        )

        try:
            stdout, stderr = process.communicate(timeout=MAX_EXECUTION_TIME)

            if process.returncode != 0:
                stderr = stderr or f"进程退出码: {process.returncode}"
                result_parts.append(f"❌ Git am --continue 失败:\n{stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            result_parts.append(
                f"⏰ 执行超时（{MAX_EXECUTION_TIME}秒），进程已被终止\n\n输出:\n{stdout[:1000]}"
            )

        if stdout:
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (输出被截断)"
            result_parts.append(f"📤 Git am --continue 输出:\n{stdout}")

        if stderr:
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (错误输出被截断)"
            result_parts.append(f"⚠️ Git am --continue 错误:\n{stderr}")

        if len(result_parts) == 1:
            result_parts.append("✅ Git am --continue 执行完成")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"


@tool
def git_add_files(files: List[str] = None, working_dir: str = None) -> str:
    """
    添加文件到 Git 暂存区。

    该工具通过 git add 命令添加文件到暂存区，支持单个文件或多个文件。
    支持在指定目录下执行。

    Args:
        files: 要添加的文件列表（可选，默认为 None 则添加所有文件）
        working_dir: 执行命令的工作目录（可选）

    Returns:
        添加结果信息

    示例：
        git_add_files(["file1.py", "file2.py"])
        git_add_files()  # 添加所有文件
        git_add_files(working_dir="/path/to/project")
    """
    print(f"Tool[git_add_files]: files={files}")

    result_parts = []

    try:
        command = ["git", "add"]

        if files:
            command.extend(files)
        else:
            command.append(".")  # 添加所有文件

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir or os.getcwd(),
        )

        try:
            stdout, stderr = process.communicate(timeout=MAX_EXECUTION_TIME)

            if process.returncode != 0:
                stderr = stderr or f"进程退出码: {process.returncode}"
                result_parts.append(f"❌ Git add 失败:\n{stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            result_parts.append(
                f"⏰ 执行超时（{MAX_EXECUTION_TIME}秒），进程已被终止\n\n输出:\n{stdout[:1000]}"
            )

        if stdout:
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (输出被截断)"
            result_parts.append(f"📤 Git add 输出:\n{stdout}")

        if stderr:
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (错误输出被截断)"
            result_parts.append(f"⚠️ Git add 错误:\n{stderr}")

        if len(result_parts) == 1:
            result_parts.append("✅ Git add 执行完成")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"


@tool
def git_status(working_dir: str = None) -> str:
    """
    查看 Git 状态。

    该工具通过 git status 命令查看当前仓库状态。
    支持在指定目录下执行。

    Args:
        working_dir: 执行命令的工作目录（可选）

    Returns:
        Git 状态信息

    示例：
        git_status()
        git_status(working_dir="/path/to/project")
    """
    print("Tool[git_status]:")

    result_parts = []

    try:
        command = ["git", "status"]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir or os.getcwd(),
        )

        try:
            stdout, stderr = process.communicate(timeout=MAX_EXECUTION_TIME)

            if process.returncode != 0:
                stderr = stderr or f"进程退出码: {process.returncode}"
                result_parts.append(f"❌ Git status 失败:\n{stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            result_parts.append(
                f"⏰ 执行超时（{MAX_EXECUTION_TIME}秒），进程已被终止\n\n输出:\n{stdout[:1000]}"
            )

        if stdout:
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (输出被截断)"
            result_parts.append(f"📤 Git status 输出:\n{stdout}")

        if stderr:
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (错误输出被截断)"
            result_parts.append(f"⚠️ Git status 错误:\n{stderr}")

        if len(result_parts) == 1:
            result_parts.append("✅ Git status 执行完成")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"


@tool
def git_diff(working_dir: str = None) -> str:
    """
    查看 Git 差异。

    该工具通过 git diff 命令查看工作目录与暂存区的差异。
    支持在指定目录下执行。

    Args:
        working_dir: 执行命令的工作目录（可选）

    Returns:
        Git 差异信息

    示例：
        git_diff()
        git_diff(working_dir="/path/to/project")
    """
    print("Tool[git_diff]:")

    result_parts = []

    try:
        command = ["git", "diff"]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir or os.getcwd(),
        )

        try:
            stdout, stderr = process.communicate(timeout=MAX_EXECUTION_TIME)

            if process.returncode != 0:
                stderr = stderr or f"进程退出码: {process.returncode}"
                result_parts.append(f"❌ Git diff 失败:\n{stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            result_parts.append(
                f"⏰ 执行超时（{MAX_EXECUTION_TIME}秒），进程已被终止\n\n输出:\n{stdout[:1000]}"
            )

        if stdout:
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (输出被截断)"
            result_parts.append(f"📤 Git diff 输出:\n{stdout}")

        if stderr:
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (错误输出被截断)"
            result_parts.append(f"⚠️ Git diff 错误:\n{stderr}")

        if len(result_parts) == 1:
            result_parts.append("✅ Git diff 执行完成")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"


@tool
def git_log(limit: int = 10, working_dir: str = None) -> str:
    """
    查看 Git 提交历史。

    该工具通过 git log 命令查看最近的提交历史。
    支持在指定目录下执行。

    Args:
        limit: 显示的提交数量（默认 10）
        working_dir: 执行命令的工作目录（可选）

    Returns:
        Git 提交历史信息

    示例：
        git_log()
        git_log(5)
        git_log(working_dir="/path/to/project")
    """
    print(f"Tool[git_log]: limit={limit}")

    result_parts = []

    try:
        command = ["git", "log", f"-{limit}", "--oneline"]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir or os.getcwd(),
        )

        try:
            stdout, stderr = process.communicate(timeout=MAX_EXECUTION_TIME)

            if process.returncode != 0:
                stderr = stderr or f"进程退出码: {process.returncode}"
                result_parts.append(f"❌ Git log 失败:\n{stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            result_parts.append(
                f"⏰ 执行超时（{MAX_EXECUTION_TIME}秒），进程已被终止\n\n输出:\n{stdout[:1000]}"
            )

        if stdout:
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (输出被截断)"
            result_parts.append(f"📤 Git log 输出:\n{stdout}")

        if stderr:
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (错误输出被截断)"
            result_parts.append(f"⚠️ Git log 错误:\n{stderr}")

        if len(result_parts) == 1:
            result_parts.append("✅ Git log 执行完成")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"


@tool
def git_delete_rej_files(working_dir: str = None) -> str:
    """
    删除 git am --reject 产生的所有 .rej 文件。

    该工具用于清理代码仓库，删除 git am --reject 过程中产生的 .rej 冲突文件。
    具有以下安全限制：
    - 只能删除 .rej 扩展名的文件
    - 文件必须在允许的目录内（当前工作目录）
    - 支持在指定目录下执行
    - 会列出所有被删除的文件

    Args:
        working_dir: 执行命令的工作目录（可选）

    Returns:
        删除结果信息，包括被删除的文件列表或错误信息

    示例：
        git_delete_rej_files()
        git_delete_rej_files(working_dir="/path/to/project")
    """
    print(f"Tool[git_delete_rej_files]: working_dir={working_dir}")

    result_parts = []
    base_dir = Path(working_dir or os.getcwd())

    if not base_dir.exists() or not base_dir.is_dir():
        return f"❌ 目录不存在或不是目录: {base_dir}"

    try:
        rej_files = list(base_dir.rglob("*.rej"))

        if not rej_files:
            result_parts.append("ℹ️ 没有找到 .rej 文件")
            print("result: ", "\n\n".join(result_parts))
            return "\n\n".join(result_parts)

        deleted_files = []
        failed_files = []

        for rej_file in rej_files:
            is_valid, abs_path, error_msg = validate_rej_file(str(rej_file), base_dir)
            if not is_valid:
                failed_files.append(f"{rej_file}: {error_msg}")
                continue

            try:
                abs_path.unlink()
                deleted_files.append(str(abs_path))
            except Exception as e:
                failed_files.append(f"{abs_path}: 删除失败 - {str(e)}")

        if deleted_files:
            result_parts.append(f"✅ 成功删除 {len(deleted_files)} 个 .rej 文件:")
            for f in deleted_files:
                result_parts.append(f"  - {f}")

        if failed_files:
            result_parts.append(f"⚠️ {len(failed_files)} 个文件删除失败:")
            for f in failed_files:
                result_parts.append(f"  - {f}")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"
