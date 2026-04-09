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
- **Agent**: `agent.py` - Wraps deepagents with FilesystemBackend
- **Tools**: 
  - `file_system_execution.py`: File operations
  - `safe_python_execution.py`: Python execution with security checks
  - `git_operations.py`: Git patch application
- **Skills**: `.skills/` - SKILL.md files with frontmatter metadata

## Git Tools

6 tools optimized for patch application:
- `git_apply_patch` - Apply patch with `git am --reject`
- `git_continue_apply` - Continue after conflict resolution
- `git_add_files` - Add resolved files
- `git_status` - Check repository status
- `git_diff` - View changes
- `git_log` - View commit history

**Workflow**: Apply patch → Resolve conflicts → `git add` → `git am --continue` (commit info preserved)

## API Configuration

- Base URL: `https://open.bigmodel.cn/api/paas/v4/`
- Model: `glm-4.6`
- API key: Load from `key.json`

## Security

- File path validation
- Command execution timeouts
- Python execution security checks
- Interrupt handling for risky operations
