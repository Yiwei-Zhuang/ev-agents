import os
from pathlib import Path
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from tools.safe_python_execution import execute_python_file

ZHIPU_API_KEY = "hehe"

# skill_path = ["/Users/yiweizhuang/cold/my_skills/"]
skill_path = ["/Users/yiweizhuang/cold/git-Yiwei-Zhuang/ev-agents/my_skills"]


@tool
def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    读取文件内容。

    Args:
        file_path: 要读取的文件路径（支持相对路径和绝对路径）
        encoding: 文件编码，默认 utf-8
    """
    print(f"Tool[read_file]: {file_path}")
    try:
        path = Path(file_path)

        # 检查文件是否存在
        if not path.exists():
            return f"❌ 错误：文件 '{file_path}' 不存在"

        # 检查是否为文件
        if not path.is_file():
            return f"❌ 错误：'{file_path}' 不是一个文件"

        # 读取文件
        with open(path, "r", encoding=encoding) as f:
            content = f.read()

        # 获取文件大小
        file_size = path.stat().st_size

        # 限制返回内容长度，避免超过token限制
        max_length = 5000
        if len(content) > max_length:
            content_preview = content[:max_length]
            return f"✅ 成功读取文件 '{file_path}' (大小: {file_size} 字节)\n\n文件内容预览（前{max_length}字符）：\n{content_preview}\n\n... (内容已截断)"

        return f"✅ 成功读取文件 '{file_path}' (大小: {file_size} 字节)\n\n文件内容：\n{content}"

    except PermissionError:
        return f"❌ 错误：没有权限读取文件 '{file_path}'"
    except UnicodeDecodeError:
        return f"❌ 错误：无法使用 {encoding} 编码读取文件 '{file_path}'"
    except Exception as e:
        return f"❌ 读取文件时发生错误：{str(e)}"


@tool
def write_file(
    file_path: str, content: str, encoding: str = "utf-8", append: bool = False
) -> str:
    """
    写入内容到文件。如果文件不存在会自动创建，如果存在则根据 append 参数决定覆盖或追加。

    Args:
        file_path: 文件路径
        content: 要写入的内容
        encoding: 文件编码，默认 utf-8
        append: 是否追加到文件末尾（True: 追加，False: 覆盖）
    """
    print(f"Tool[write_file]: {file_path}\n{content[:100]}")
    try:
        path = Path(file_path)

        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        # 确定写入模式
        mode = "a" if append else "w"
        action = "追加" if append else "写入"

        # 写入文件
        with open(path, mode, encoding=encoding) as f:
            f.write(content)

        # 计算写入内容大小
        content_size = len(content.encode(encoding))

        return f"✅ 成功{action}到文件 '{file_path}' (写入 {content_size} 字节)"

    except PermissionError:
        return f"❌ 错误：没有权限写入文件 '{file_path}'"
    except Exception as e:
        return f"❌ 写入文件时发生错误：{str(e)}"


@tool
def list_directory(directory_path: str = ".", recursive: bool = False) -> str:
    """
    列出目录中的文件和子目录。

    Args:
        directory_path: 目录路径，默认为当前目录
        recursive: 是否递归列出所有子目录的内容
    """
    print(f"Tool[list_directory]: {directory_path}")
    try:
        path = Path(directory_path)

        if not path.exists():
            return f"❌ 错误：目录 '{directory_path}' 不存在"

        if not path.is_dir():
            return f"❌ 错误：'{directory_path}' 不是一个目录"

        result = [f"📁 目录 '{path.absolute()}' 的内容："]

        if recursive:
            # 递归列出所有文件
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    rel_path = file_path.relative_to(path)
                    file_size = file_path.stat().st_size
                    result.append(f"  📄 {rel_path} ({file_size} 字节)")
                elif file_path.is_dir():
                    rel_path = file_path.relative_to(path)
                    result.append(f"  📁 {rel_path}/")
        else:
            # 只列出直接内容
            items = sorted(path.iterdir())
            for item in items:
                if item.is_file():
                    file_size = item.stat().st_size
                    result.append(f"  📄 {item.name} ({file_size} 字节)")
                elif item.is_dir():
                    result.append(f"  📁 {item.name}/")

        return "\n".join(result)

    except PermissionError:
        return f"❌ 错误：没有权限访问目录 '{directory_path}'"
    except Exception as e:
        return f"❌ 列出目录时发生错误：{str(e)}"


g_tools = [write_file, read_file, list_directory, execute_python_file]
g_tools_key_params = {
    "write_file": ["file_path"],
    "read_file": ["file_path"],
    "list_directory": ["directory_path"],
    "execute_python_file": ["file_path", "command_args"],
}
g_interrupt_on = {
    "write_file": True,
    "read_file": False,
    "list_directory": False,
    "execute_python_file": False,
}


class ZPAgent:
    def __init__(self, id, api_key=ZHIPU_API_KEY):
        self.api_key = api_key
        self.id = id
        self.config = RunnableConfig(configurable={"thread_id": self.id})
        self.model = ChatOpenAI(
            model="glm-4.6",
            temperature=0.3,
            max_tokens=65536,
            api_key=self.api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
        self.agent = create_deep_agent(
            model=self.model,
            backend=FilesystemBackend(root_dir="."),
            skills=skill_path,
            checkpointer=MemorySaver(),
            tools=g_tools,
            interrupt_on=g_interrupt_on,
        )
        self.key_params = g_tools_key_params

    def invoke(self, messages):
        return self.agent.invoke(
            {
                "messages": messages,
            },
            config=self.config,
        )

    def resume(self, decisions):
        return self.agent.invoke(
            Command(resume={"decisions": decisions}),
            config=self.config,
        )

    def get_agent(self):
        return self.agent

    def get_key_params(self, tool_name):
        return self.key_params[tool_name]
