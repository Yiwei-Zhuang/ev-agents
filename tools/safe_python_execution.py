import subprocess
import signal
import os
import ast
from pathlib import Path
from typing import Optional, List
from langchain.tools import tool

MAX_EXECUTION_TIME = 30
MAX_OUTPUT_SIZE = 50000

ALLOWED_DIRS = {".", "./", "/"}

# 危险模块列表
DANGEROUS_MODULES = {
    "os",
    "subprocess",
    "sys",
    "shutil",
    "importlib",
    "multiprocessing",
    "threading",
    "concurrent",
    "pty",
    "fcntl",
    "termios",
    "socket",
    "urllib",
    "urllib2",
    "urllib3",
    "requests",
    "http",
    "httplib",
    "ftplib",
    "smtplib",
    "pickle",
    "shelve",
    "marshal",
    "ctypes",
    "ctypes.util",
    "tempfile",
    "pathlib",
    "glob",
    "fnmatch",
}

# 允许的安全模块（用于参数解析等安全用途）
ALLOWED_MODULES = {
    "argparse",
    "json",
    "math",
    "random",
    "datetime",
    "statistics",
    "fractions",
    "decimal",
    "collections",
    "itertools",
    "functools",
    "typing",
    "dataclasses",
}

# 危险函数列表
DANGEROUS_FUNCTIONS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "input",
    "raw_input",
    "globals",
    "locals",
    "vars",
    "reload",
    "exit",
    "quit",
}

# 危险属性列表
DANGEROUS_ATTRIBUTES = {
    "__class__",
    "__bases__",
    "__subclasses__",
    "__reduce__",
    "__reduce_ex__",
    "__builtins__",
    "__globals__",
    "__code__",
    "__closure__",
    "__func__",
    "__self__",
    "__dict__",
    "__doc__",
}

# 高风险模式
HIGH_RISK_PATTERNS = {
    "system",
    "popen",
    "call",
    "check_call",
    "check_output",
    "run",
    "shell",
    "execute",
    "spawn",
    "remove",
    "rmdir",
    "unlink",
    "delete",
}


def validate_file_path(file_path: str) -> tuple[bool, str, str]:
    """
    验证文件路径安全性

    Args:
        file_path: 文件路径

    Returns:
        (是否有效, 绝对路径, 错误信息)
    """
    path = Path(file_path)

    # 尝试解析路径（支持相对路径和绝对路径）
    try:
        abs_path = path.resolve()
    except Exception as e:
        return False, "", f"❌ 路径解析失败: {str(e)}"

    if not abs_path.exists():
        return False, "", f"❌ 文件不存在: {file_path}"

    if not abs_path.is_file():
        return False, "", f"❌ 不是文件: {file_path}"

    if not file_path.endswith(".py"):
        return False, "", f"❌ 不是 Python 文件: {file_path}"

    # 获取当前工作目录和项目根目录
    current_dir = Path.cwd()
    project_root = Path(__file__).parent.parent.resolve()  # ev-agents 目录

    # 检查路径是否在允许的目录范围内
    # 允许当前工作目录、项目根目录或其子目录下的文件
    allowed_dirs = [current_dir, project_root]

    is_allowed = False
    for allowed_dir in allowed_dirs:
        try:
            abs_path.relative_to(allowed_dir)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        return (
            False,
            "",
            f"❌ 文件路径超出允许范围: {file_path}\n允许的目录: {[str(d) for d in allowed_dirs]}",
        )

    return True, str(abs_path), ""


def analyze_code_safety(code: str) -> tuple[bool, List[str], List[str]]:
    """
    分析 Python 代码的安全性

    Args:
        code: Python 代码字符串

    Returns:
        (是否安全, 警告信息列表, 错误信息列表)
    """
    warnings = []
    errors = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        errors.append(f"语法错误: {e}")
        return False, warnings, errors

    for node in ast.walk(tree):
        # 检查危险模块导入
        if isinstance(node, ast.Import):
            for alias in node.names:
                base_module = alias.name.split(".")[0]
                if base_module in DANGEROUS_MODULES:
                    errors.append(f"❌ 禁止导入模块: {base_module}")

        if isinstance(node, ast.ImportFrom):
            if node.module:
                base_module = node.module.split(".")[0]
                if base_module in DANGEROUS_MODULES:
                    errors.append(f"❌ 禁止导入模块: {base_module}")

        # 检查危险函数调用
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_FUNCTIONS:
                    errors.append(f"❌ 禁止使用函数: {node.func.id}")

                # 检查高风险模式
                if node.func.id in HIGH_RISK_PATTERNS:
                    warnings.append(f"⚠️ 检测到高风险函数: {node.func.id}")

            if isinstance(node.func, ast.Attribute):
                if node.func.attr in HIGH_RISK_PATTERNS:
                    func_name = f"{node.func.value.id if isinstance(node.func.value, ast.Name) else 'unknown'}.{node.func.attr}"
                    warnings.append(f"⚠️ 检测到高风险调用: {func_name}")

        # 检查危险属性访问
        if isinstance(node, ast.Attribute):
            if node.attr in DANGEROUS_ATTRIBUTES:
                warnings.append(f"⚠️ 检测到危险属性访问: {node.attr}")

    # 检查代码复杂度（简单启发式）
    if len(code.split("\n")) > 100:
        warnings.append("⚠️ 代码行数较多（超过100行），请确认安全性")

    # 检查文件大小
    if len(code) > 10000:
        warnings.append("⚠️ 代码文件较大（超过10KB），请确认安全性")

    is_safe = len(errors) == 0
    return is_safe, warnings, errors


def read_and_analyze_file(abs_path: str) -> tuple[bool, str]:
    """
    读取文件并执行安全分析

    Args:
        abs_path: 文件的绝对路径

    Returns:
        (是否允许执行, 分析结果信息)
    """
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            code = f.read()

        is_safe, warnings, errors = analyze_code_safety(code)

        if not is_safe:
            error_msg = "❌ 安全检查失败:\n" + "\n".join(errors)
            return False, error_msg

        if warnings:
            warning_msg = "⚠️ 安全警告:\n" + "\n".join(warnings)
            # 有警告但无错误，允许执行但显示警告
            return True, warning_msg

        return True, "✅ 安全检查通过"

    except UnicodeDecodeError:
        return False, "❌ 无法读取文件（编码问题）"
    except Exception as e:
        return False, f"❌ 读取文件时出错: {str(e)}"


@tool
def execute_python_file(
    file_path: str,
    timeout: int = MAX_EXECUTION_TIME,
    skip_security_check: bool = False,
    command_args: list = None,
) -> str:
    """
    安全执行指定的 Python 文件，返回执行结果。

    该工具通过命令行直接执行 Python 文件，具有以下安全限制：
    - 文件必须存在且是 .py 文件
    - 文件路径必须在允许的目录范围内
    - 执行前会进行代码安全分析（可跳过）
    - 默认超时 30 秒
    - 输出大小限制 50000 字符

    安全检查包括：
    - 禁止危险模块导入（os, subprocess, sys 等）
    - 禁止危险函数调用（eval, exec, open 等）
    - 检测高风险操作（文件操作、系统调用等）
    - 警告危险属性访问

    Args:
        file_path: Python 文件的路径
        timeout: 执行超时时间（秒），默认 30 秒
        skip_security_check: 是否跳过安全检查，默认 False
        command_args: 命令行参数列表，例如 ["上海", "--date", "2024-04-09"]

    Returns:
        文件执行的标准输出和标准错误，以及安全检查结果

    示例：
        execute_python_file("weather.py", command_args=["上海", "--date", "2024-04-09"])
        相当于执行: python weather.py 上海 --date 2024-04-09
    """
    print(f"Tool[execute_python_file]: {file_path}")
    print(f"Tool[execute_python_file]: command_args={command_args}")

    is_valid, abs_path, error_msg = validate_file_path(file_path)
    if not is_valid:
        print("error_msg:", error_msg)
        return error_msg

    # 执行安全分析
    result_parts = []

    if not skip_security_check:
        is_safe, security_msg = read_and_analyze_file(abs_path)
        result_parts.append(f"🔒 安全分析结果:\n{security_msg}\n")

        if not is_safe:
            print("not safe:", "\n\n".join(result_parts))
            return "\n\n".join(result_parts)

    # 构建命令参数
    command = ["python", abs_path]

    # 添加参数
    if command_args:
        if isinstance(command_args, list):
            command.extend(command_args)
        else:
            print(f"❌ 参数格式错误: command_args 应该是列表")
            return f"❌ 参数格式错误: command_args 应该是列表"

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd(),
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)

            if process.returncode != 0:
                stderr = stderr or f"进程退出码: {process.returncode}"

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            result_parts.append(
                f"⏰ 执行超时（{timeout}秒），进程已被终止\n\n输出:\n{stdout[:1000]}"
            )
            print("超时：", "\n\n".join(result_parts))
            return "\n\n".join(result_parts)

        if stdout:
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (输出被截断)"
            result_parts.append(f"📤 标准输出:\n{stdout}")

        if stderr:
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (错误输出被截断)"
            result_parts.append(f"⚠️ 标准错误:\n{stderr}")

        if len(result_parts) == 1 and not skip_security_check:
            # 只有安全分析结果，没有执行输出
            result_parts.append("✅ 执行成功，无输出")

        print("result: ", "\n\n".join(result_parts))
        return "\n\n".join(result_parts)

    except Exception as e:
        print(f"❌ 执行失败: {type(e).__name__}: {str(e)}")
        return f"❌ 执行失败: {type(e).__name__}: {str(e)}"
