import os
from dataclasses import dataclass, field
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from tools.file_system_execution import write_file, read_file, list_directory
from tools.safe_python_execution import execute_python_file
from tools.git_operations import (
    git_apply_patch,
    git_continue_apply,
    git_add_files,
    git_status,
    git_diff,
    git_log,
)

ZHIPU_API_KEY = "hehe"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


@dataclass
class AgentConfig:
    model: str = "glm-4.6"
    temperature: float = 0.3
    max_tokens: int = 65536
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    skills_path: list = field(
        default_factory=lambda: [os.path.join(PROJECT_ROOT, ".skills")]
    )
    backend_root_dir: str = "."


g_tools = [
    write_file,
    read_file,
    list_directory,
    execute_python_file,
    git_apply_patch,
    git_continue_apply,
    git_add_files,
    git_status,
    git_diff,
    git_log,
]
g_tools_key_params = {
    "write_file": ["file_path"],
    "read_file": ["file_path"],
    "list_directory": ["directory_path"],
    "execute_python_file": ["file_path", "command_args"],
    "git_apply_patch": ["patch_file"],
    "git_continue_apply": [],
    "git_add_files": ["files"],
    "git_status": [],
    "git_diff": [],
    "git_log": ["limit"],
}

# 当工具的操作存在较高风险时，需要置True让人工二次确认。
g_interrupt_on = {
    "write_file": True,
    "read_file": False,
    "list_directory": False,
    "execute_python_file": True,
    "git_apply_patch": True,
    "git_continue_apply": False,
    "git_add_files": True,
    "git_status": False,
    "git_diff": False,
    "git_log": False,
}


class ZPAgent:
    def __init__(self, id, api_key=ZHIPU_API_KEY, config: AgentConfig | None = None):
        self.api_key = api_key
        self.id = id
        self.config = RunnableConfig(configurable={"thread_id": self.id})
        self.agent_config = config or AgentConfig()
        self.model = ChatOpenAI(
            model=self.agent_config.model,
            temperature=self.agent_config.temperature,
            max_tokens=self.agent_config.max_tokens,
            api_key=self.api_key,
            base_url=self.agent_config.base_url,
        )
        self.agent = create_deep_agent(
            model=self.model,
            backend=FilesystemBackend(root_dir=self.agent_config.backend_root_dir),
            skills=self.agent_config.skills_path,
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
