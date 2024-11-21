from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from src.commands.base import Command, CommandContext, ValidationError, ExecutionError, command


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
    def execute(self, context: CommandContext) -> Dict[str, Any]:
        target_path = context.working_dir / self.data["target"]
        in_container = self.data.get("in_container", False)

        if context.dry_run:
            return {"status": "would create", "path": str(target_path)}

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

            return {"status": "created", "path": str(target_path)}
        except Exception as e:
            raise ExecutionError(f"Failed to create file: {e}")


@command("append", color="blue",
         required=["target", "content"],
         properties={
             "target": {
                 "type": "string",
                 "description": "File to append content to",
                 "example": "log.txt"
             },
             "content": {
                 "type": "string",
                 "description": "Content to append to the file",
                 "example": "New log entry"
             },
             "newline": {
                 "type": "boolean",
                 "description": "Whether to add a newline before the content",
                 "example": True
             }
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

    def execute(self, context: CommandContext) -> Dict[str, Any]:
        target_path = context.working_dir / self.data["target"]
        content = self.data["content"]
        if self.data.get("newline", True):
            content = f"\n{content}"

        if context.dry_run:
            return {"status": "would append", "path": str(target_path)}

        try:
            if context.docker_env:
                current, _ = context.docker_env.execute(f"cat {target_path}")
                new_content = current + content
                context.docker_env.copy_to_container(new_content, str(target_path))
            else:
                with open(target_path, 'a') as f:
                    f.write(content)
            return {"status": "appended", "path": str(target_path)}
        except Exception as e:
            raise ExecutionError(f"Failed to append: {e}")


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
    def execute(self, context: CommandContext) -> Dict[str, Any]:
        target_path = context.working_dir / self.data["target"]
        force = self.data.get("force", False)

        if context.dry_run:
            return {"status": "would delete", "path": str(target_path)}

        try:
            if context.docker_env:
                # Use force remove (-f) if specified
                force_flag = "-f" if force else ""
                stdout, stderr = context.docker_env.execute(f"rm {force_flag} {target_path}")

                if stderr:
                    raise ExecutionError(stderr)
            else:
                # Local filesystem operations
                if target_path.exists():
                    target_path.unlink()
                elif not force:
                    raise ExecutionError(f"File not found: {target_path}")

            return {"status": "deleted", "path": str(target_path)}
        except Exception as e:
            raise ExecutionError(f"Failed to delete file: {e}")

