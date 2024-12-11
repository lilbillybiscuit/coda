from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from src.commands.base import Command, CommandContext, ValidationError, ExecutionError, command, CommandResult
from pathlib import Path
import os

@command("create", color="blue",
         required=["target", "content"],
         properties={
             "target": {
                 "type": "string",
                 "description": "Path where the file should be created",
                 "example": "path/to/new_file.txt"
             },
             "content": {
                 "type": "string",
                 "description": "Content to write to the file",
                 "example": "Hello, World!"
             },
             "mode": {
                 "type": "string",
                 "pattern": "^[0-7]{3,4}$",
                 "description": "File permissions in octal format (e.g., 755 for executable)",
                 "example": "644"
             },
             "in_container": {
                 "type": "boolean",
                 "description": "Whether to create the file inside the container",
                 "example": True
             }
         })
class CreateFileCommand(Command):
    """
    Create a new file with specified content and permissions.

    Example:
    {
        "action": "create",
        "target": "hello.py",
        "content": "print('Hello, World!')",
        "mode": "755",
        "in_container": true
    }
    """
    def execute(self, context: CommandContext) -> CommandResult:
        target_path = context.working_dir / self.data["target"]
        in_container = self.data.get("in_container", False)

        if context.dry_run:
            return CommandResult.success("would create", path=str(target_path))


        try:
            if context.docker_env:
                # Create parent directory in container
                parent_dir = str(target_path.parent)
                context.docker_env.execute(f"mkdir -p {parent_dir}")

                # Copy content to file in container
                context.docker_env.copy_to_container(self.data["content"], str(target_path))

                # Set permissions if specified
                if "mode" in self.data:
                    context.docker_env.execute(f"chmod {self.data['mode']} {target_path}")
            else:
                # Local filesystem operations
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(self.data["content"])
                if "mode" in self.data:
                    target_path.chmod(int(self.data["mode"], 8))

            return CommandResult.success("created", path=str(target_path))
        except Exception as e:
            raise ExecutionError(f"Failed to create file: {e}")

@command("append",
         required=["target", "content"],
         properties={
             "target": {"type": "string"},
             "content": {"type": "string"},
             "newline": {"type": "boolean"}
         })
class AppendFileCommand(Command):
    """
    Append content to an existing file.

    Example:
    {
        "action": "append",
        "target": "log.txt",
        "content": "New log entry",
        "newline": true
    }
    """

    def execute(self, context: CommandContext) -> CommandResult:
        target_path = context.working_dir / self.data["target"]
        content = self.data["content"]
        if self.data.get("newline", True):
            content = f"\n{content}"

        if context.dry_run:
            return CommandResult.success("would append", path=str(target_path))

        try:
            if context.docker_env:
                current, stderr, exit_code = context.docker_env.execute(f"cat {target_path}")
                new_content = current + content
                context.docker_env.copy_to_container(new_content, str(target_path))
            else:
                with open(target_path, 'a') as f:
                    f.write(content)
            return CommandResult.success(
                "appended",
                path=str(target_path),
                stdout="",
                stderr=""
            )
        except Exception as e:
            return CommandResult.error(
                str(e),
                path=str(target_path)
            )
@command("delete", color="red",
         required=["target"],
         properties={
             "target": {"type": "string"},
             "force": {"type": "boolean"}  # Optional force flag
         })
class DeleteFileCommand(Command):
    """
    Delete a file or directory.

    Example:
    {
        "action": "delete",
        "target": "old_file.txt",
        "force": true
    }
    """
    def execute(self, context: CommandContext) -> CommandResult:
        target_path = context.working_dir / self.data["target"]
        force = self.data.get("force", False)

        if context.dry_run:
            # return {"status": "would delete", "path": str(target_path)}
            return CommandResult.success("would delete", path=str(target_path))

        try:
            if context.docker_env:
                # Use force remove (-f) if specified
                force_flag = "-f" if force else ""
                stdout, stderr, exit_code = context.docker_env.execute(f"rm {force_flag} {target_path}")

                if stderr:
                    raise ExecutionError(stderr)
            else:
                # Local filesystem operations
                if target_path.exists():
                    target_path.unlink()
                elif not force:
                    raise ExecutionError(f"File not found: {target_path}")

            # return {"status": "deleted", "path": str(target_path)}
            return CommandResult.success("deleted", path=str(target_path))
        except Exception as e:
            raise ExecutionError(f"Failed to delete file: {e}")

def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary by trying to read it as text."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            file.read(1024)  # Try reading the first 1024 bytes
        return False
    except (UnicodeDecodeError, IOError):
        return True


@command("read", color="cyan",
         required=["target"],
         properties={
             "target": {
                 "type": "string",
                 "description": "Path to the file to read",
                 "example": "path/to/file.txt"
             },
             "line_start": {
                 "type": "integer",
                 "description": "Line number to start reading from",
                 "example": 0
             },
             "line_end": {
                 "type": "integer",
                 "description": "Line number to end reading at",
                 "example": 30
             }
         })
class ReadFileCommand(Command):
    """
    Read lines from a text file, abort if the file is binary.

    Example:
    {
        "action": "read",
        "target": "example.txt",
        "line_start": 0,
        "line_end": 30
    }
    """

    def execute(self, context: CommandContext) -> CommandResult:
        if not context.docker_env:
            return CommandResult.error(
                "Docker environment required for file operations",
                path=str(self.data["target"])
            )

        # Get workspace path from Docker environment
        workspace_path = context.docker_env.get_workspace_path()
        target_path = self.data["target"]
        local_path = workspace_path / target_path

        line_start = self.data.get("line_start", 0)
        line_end = self.data.get("line_end", 30)

        if context.dry_run:
            return CommandResult.success("would read", path=str(target_path))

        try:
            if not local_path.exists():
                return CommandResult.error(
                    f"File not found: {target_path}",
                    path=str(target_path)
                )

            with open(local_path, 'r') as file:
                lines = file.readlines()

            if line_start < 0 or line_start >= len(lines):
                line_start = 0
            if line_end <= 0 or line_end > len(lines):
                line_end = min(line_start + 30, len(lines))

            selected_lines = lines[line_start:line_end]
            file_continues = line_end < len(lines)

            result = CommandResult.success(
                "read",
                path=str(target_path),
                stdout=''.join(selected_lines),
                other={
                    "line_start": line_start,
                    "line_end": line_end,
                    "file_continues": file_continues
                }
            )

            if file_continues:
                result.message = f"File continues beyond line {line_end}."

            return result

        except UnicodeDecodeError:
            return CommandResult.error(
                "Cannot read binary file",
                path=str(target_path)
            )
        except Exception as e:
            return CommandResult.error(
                str(e),
                path=str(target_path)
            )


@command("list_dir", color="cyan",
         properties={
             "path": {
                 "type": "string",
                 "description": "Path to list (defaults to current directory)",
                 "example": "path/to/dir"
             }
         })
class ListDirectoryCommand(Command):
    """
    List files and folders in the specified directory.

    Example:
    {
        "action": "list_dir",
        "path": "path/to/dir"
    }
    """

    def execute(self, context: CommandContext) -> CommandResult:
        path = self.data.get("path", ".")
        target_path = context.working_dir / path

        if context.dry_run:
            # return {"status": "would list", "path": str(target_path)}
            return CommandResult.success("would list", path=str(target_path))
        try:
            if context.docker_env:
                stdout, stderr, exit_code = context.docker_env.execute(f"ls -al {target_path}")
                if stderr:
                    raise ExecutionError(stderr)
                items = stdout.splitlines()
            else:
                items = []
                for item in os.listdir(target_path):
                    item_path = os.path.join(target_path, item)
                    if os.path.isfile(item_path):
                        items.append(f"- {item}")
                    elif os.path.isdir(item_path):
                        items.append(f"d {item}")

            # return {
            #     "success": True,
            #     "status": "listed",
            #     "path": str(target_path),
            #     "output": items
            # }
            return CommandResult.success(
                "listed",
                path=str(target_path),
                output=items,
            )
        except Exception as e:
            raise ExecutionError(f"Failed to list directory: {e}")
