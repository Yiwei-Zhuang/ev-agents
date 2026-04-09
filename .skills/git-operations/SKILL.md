---
name: git-operations
description: Provides Git operations for patch application and conflict resolution. Use this skill when the user needs to apply patches to Git repositories, resolve conflicts, or perform related git operations for patch management.
---

# Git Operations

Tools for applying patches to Git repositories and managing the patch application process.

## Important Constraint

**Before performing any Git operations, you must explicitly specify the path to the Git project.** All Git commands need to be executed within the correct Git repository directory.

When a user requests Git operations:
1. **Ask for the Git project path** if not specified
2. **Use the `working_dir` parameter** for all git commands to ensure they execute in the correct directory
3. **Validate the path** is a valid Git repository before proceeding

Example questions to ask:
- "Please specify the path to the Git repository where you want to apply the patch"
- "Which Git project directory should I use for these operations?"
- "Please provide the working directory for this Git operation"

## Available Tools

### 1. `git_apply_patch`
- **Purpose**: Apply Git patch files with conflict handling
- **Parameters**:
  - `patch_file`: Path to patch file (required)
  - `reject`: Use --reject option (default: True)
  - `working_dir`: Git project directory (recommended)
- **Usage**: `git_apply_patch("feature.patch", reject=True, working_dir="/path/to/project")`
- **Note**: Uses `git am` command which automatically preserves commit information from the patch file

### 2. `git_continue_apply`
- **Purpose**: Continue patch application after resolving conflicts
- **Parameters**:
  - `working_dir`: Git project directory (recommended)
- **Usage**: `git_continue_apply(working_dir="/path/to/project")`
- **Note**: Uses `git am --continue` to resume patch application after manual conflict resolution

### 3. `git_add_files`
- **Purpose**: Add files to Git staging area
- **Parameters**:
  - `files`: List of files to add (optional, default: all files)
  - `working_dir`: Git project directory (recommended)
- **Usage**: `git_add_files(["file1.py", "file2.py"], working_dir="/path/to/project")` or `git_add_files(working_dir="/path/to/project")`

### 4. `git_status`
- **Purpose**: Check current Git repository status
- **Parameters**:
  - `working_dir`: Git project directory (recommended)
- **Usage**: `git_status(working_dir="/path/to/project")`

### 5. `git_diff`
- **Purpose**: View differences between working directory and staging area
- **Parameters**:
  - `working_dir`: Git project directory (recommended)
- **Usage**: `git_diff(working_dir="/path/to/project")`

### 6. `git_log`
- **Purpose**: View commit history
- **Parameters**:
  - `limit`: Number of commits to show (default: 10)
  - `working_dir`: Git project directory (recommended)
- **Usage**: `git_log(5, working_dir="/path/to/project")` or `git_log(working_dir="/path/to/project")`



## Workflow for Patch Application

### 1. Check current status
```python
git_status(working_dir="/path/to/project")
```

### 2. Apply patch with reject option
```python
git_apply_patch("patch_file.patch", reject=True, working_dir="/path/to/project")
```

### 3. If conflicts occur:
- Check conflicts using `git_status(working_dir="/path/to/project")` and `git_diff(working_dir="/path/to/project")`
- Resolve conflicts manually
- Add resolved files using `git_add_files(working_dir="/path/to/project")`
- **Continue patch application using `git_continue_apply(working_dir="/path/to/project")`**

**Note**: When using `git am` with `--reject`, commit information from the patch is automatically preserved. No manual commit is needed - `git am` and `git am --continue` handle commits automatically with original patch information.

## Conflict Resolution Process

When applying patches with conflicts:

1. **Apply patch with reject**:
   ```python
   git_apply_patch("feature.patch", reject=True, working_dir="/path/to/project")
   ```

2. **Check status**:
   ```python
   git_status(working_dir="/path/to/project")
   ```

3. **View conflicts**:
   ```python
   git_diff(working_dir="/path/to/project")
   ```

4. **Resolve conflicts manually** in the affected files

5. **Add resolved files**:
   ```python
   git_add_files(["conflicted_file.py"], working_dir="/path/to/project")
   ```

6. **Continue patch application**:
   ```python
   git_continue_apply(working_dir="/path/to/project")
   ```

**Important**: The commit information from the original patch is automatically preserved. `git am --continue` will create a commit with the original patch's author, date, and commit message. No manual commit needed.

## Common Use Cases

### Applying a Patch
```python
# Apply patch with conflict handling
git_apply_patch("fix-bug.patch", reject=True, working_dir="/path/to/project")

# Check if conflicts occurred
git_status(working_dir="/path/to/project")

# If conflicts, resolve them and add to files
git_add_files(["resolved_file.py"], working_dir="/path/to/project")

# Continue patch application (commit info is preserved)
git_continue_apply(working_dir="/path/to/project")
```

### Successfully Applied Patch
```python
# Apply patch successfully
git_apply_patch("feature.patch", working_dir="/path/to/project")

# Result: Patch applied with original commit information preserved
# No additional commit needed
```

### Managing Files
```python
# Add specific files
git_add_files(["src/main.py", "tests/test_main.py"], working_dir="/path/to/project")

# Add all files
git_add_files(working_dir="/path/to/project")

# Check status
git_status(working_dir="/path/to/project")
```

## Error Handling

The tools include comprehensive error handling:
- File path validation
- Command execution timeouts
- Output size limits
- Detailed error messages
- Conflict detection and resolution support

## Security Features

- File path validation for all operations
- Command execution timeouts (60 seconds)
- Output size limits (10KB)
- Proper error handling and reporting
- Safe Git command execution

## Tips

- **Always specify the `working_dir` parameter** for all Git operations to ensure commands execute in the correct repository
- Always check `git_status(working_dir="/path")` before applying patches
- Use `git_diff(working_dir="/path")` to understand conflicts
- **`git am` automatically preserves commit information** from the patch file - no manual commit needed for successful applications
- **Use `git_continue_apply` after resolving conflicts** to complete patch application with preserved commit info
- Keep commit messages clear and descriptive
- Review changes before applying patches
- Validate the working directory is a valid Git repository before operations
