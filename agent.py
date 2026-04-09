import os
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from tools.file_system_execution import write_file, read_file, list_directory
from tools.safe_python_execution import execute_python_file

ZHIPU_API_KEY = "hehe"

skill_path = ["/Users/yiweizhuang/cold/git-Yiwei-Zhuang/ev-agents/.skills"]

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
    "execute_python_file": True,
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
