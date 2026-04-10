# ev-agents

Deepagents-based AI agent using LangChain/LangGraph with Zhipu AI API.

## Setup

Requires Python 3.14+. Uses UV for dependency management.

```bash
uv sync
```

## Running

```bash
python main.py
```

## Architecture

- **Entry Point**: `main.py` - Interactive agent loop with interrupt handling
- **Agent**: `agent.py` - Wraps deepagents with FilesystemBackend and configurable settings
- **Tools**:
  - `file_system_execution.py`: File operations (read/write/list)
  - `safe_python_execution.py`: Python execution with AST-level security checks
  - `git_operations.py`: Git patch application and cleanup
- **Skills**: `.skills/` - SKILL.md files with YAML frontmatter

## Git Tools

7 tools optimized for patch application:
- `git_apply_patch` - Apply patch with `git am --reject`
- `git_continue_apply` - Continue after conflict resolution
- `git_add_files` - Add resolved files
- `git_delete_rej_files` - Clean up `.rej` conflict files
- `git_status` - Check repository status
- `git_diff` - View changes
- `git_log` - View commit history

**Workflow**: Apply patch → Resolve conflicts → `git add` → `git am --continue` → Clean up `.rej` files (commit info preserved)

## API Configuration

- Base URL: `https://open.bigmodel.cn/api/paas/v4/`
- Model: `glm-4.6`
- API key: Load from `key.json`

### Custom Configuration

Use `AgentConfig` to customize model parameters:

```python
from agent import ZPAgent, AgentConfig

config = AgentConfig(
    model="glm-4.6",
    temperature=0.3,
    max_tokens=65536,
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    skills_path=[".skills"],
    backend_root_dir="."
)

agent = ZPAgent("thread_id", api_key="your_key", config=config)
```

## Security

- File path validation
- Command execution timeouts
- Python execution security checks (AST-level blocking of dangerous modules/functions)
- Interrupt handling for risky operations
- Path restrictions (CWD or project root only)
- `.rej` file deletion safety (only `.rej` files, within allowed directories)

## Recent Improvements

- **Modular Code**: Extracted functions in `main.py` for better maintainability
- **Configurable Agent**: Added `AgentConfig` for easy model and behavior customization
- **Relative Paths**: Skills and other paths now use project-relative paths
- **Enhanced Git Workflow**: Added `git_delete_rej_files` for clean patch application
- **Better Error Handling**: Improved API key loading with specific error messages

## License

GPL v3

## Support

For issues and feature requests, please report at [GitHub Issues](https://github.com/anomalyco/opencode/issues)
