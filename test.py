from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from abc import ABC, abstractmethod
import jsonschema
from functools import wraps
from src.docker_env import DockerEnvironment, DockerConfig
from src.commands.base import CommandContext, ValidationError, ExecutionError, CommandRegistry, Command, command, CommandError

from src.json_executor import JsonExecutor
from src.prompt_manager import PromptManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@command("append",
         required=["target", "content"],
         properties={
             "target": {"type": "string"},
             "content": {"type": "string"},
             "newline": {"type": "boolean"}
         })
class AppendFileCommand(Command):
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


# Using in main.py:
def main():
    docker_config = DockerConfig()
    prompt_manager = PromptManager()

    with DockerEnvironment(docker_config) as docker_env:
        executor = JsonExecutor(working_dir="/workspace", docker_env=docker_env)

        # Execute commands
        commands = [
            {
                "action": "create",
                "target": "test.py",
                "content": "print('Hello')"
            },
            {
                "action": "append",
                "target": "test.py",
                "content": "print('World')",
                "newline": True
            },
            {
                "action": "execute",
                "target": "test.py",
                "language": "python"
            }
        ]

        try:
            results = executor.execute(commands)
            for result in results:
                print(result)
        except CommandError as e:
            print(f"Error: {e}")


# Get schema for documentation
# print(JsonExecutor.get_schema_string("create"))
# print(JsonExecutor.get_schema_string())

if __name__ == "__main__":
    main()