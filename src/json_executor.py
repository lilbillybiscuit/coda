from typing import Dict, Any, List, Callable, Optional, Type, ClassVar
from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
import logging
from abc import ABC, abstractmethod
from functools import wraps
import jsonschema
from typing_extensions import get_type_hints
from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from src.commands.base import CommandContext, ValidationError, ExecutionError, CommandRegistry, CommandResult
from src.docker_env import DockerEnvironment
from src.formatting import Color

from src.commands.file_commands import CreateFileCommand, AppendFileCommand, DeleteFileCommand
from src.commands.execute_commands import ExecuteCommand
from src.commands.status_commands import CompleteCommand
# Set up logging
logger = logging.getLogger(__name__)


class JsonExecutor:
    """Simplified executor that uses the command registry"""

    def __init__(self, working_dir: str = ".", docker_env: Optional[DockerEnvironment] = None):
        self.working_dir = Path(working_dir).resolve()
        self.docker_env = docker_env

    def execute(self, json_data: Union[str, Dict, List], dry_run: bool = False) -> List[CommandResult]:
        try:
            if isinstance(json_data, str):
                commands = json.loads(json_data)
            else:
                commands = json_data

            if isinstance(commands, dict):
                commands = [commands]

            context = CommandContext(
                working_dir=self.working_dir,
                docker_env=self.docker_env,
                dry_run=dry_run
            )

            results = []
            for cmd_data in commands:
                action = cmd_data.get("action")
                command_class = CommandRegistry.get_command(action)
                if not command_class:
                    raise ValidationError(f"Unknown action: {action}")

                command = command_class(cmd_data)
                result = command.execute(context)

                result.set_summary(cmd_data.get("summary", ""))
                results.append(result)

            return results

        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")
        except Exception as e:
            raise ExecutionError(f"Execution failed: {e}")

    @staticmethod
    def get_schema(action: Optional[str] = None) -> Dict[str, Any]:
        """Get JSON schema for specific action or all actions"""
        if action:
            command_class = CommandRegistry.get_command(action)
            if not command_class:
                raise ValueError(f"Unknown action: {action}")
            return command_class.schema

        return {
            "type": "array",
            "items": {
                "oneOf": [cmd.schema for cmd in CommandRegistry.get_all_commands().values()]
            }
        }

    @staticmethod
    def get_command_docs(action: Optional[str] = None) -> Dict[str, Any]:
        """Get documentation for commands including descriptions and examples"""
        if action:
            command_class = CommandRegistry.get_command(action)
            if not command_class:
                raise ValueError(f"Unknown action: {action}")
            return {
                "action": action,
                "description": command_class.__doc__,
                "schema": command_class.schema,
                "example": next((
                    example.strip()
                    for example in (command_class.__doc__ or "").split("Example:")
                    if "Example:" in command_class.__doc__
                ), None)
            }

        docs = {}
        for action, cmd_class in CommandRegistry.get_all_commands().items():
            docs[action] = {
                "description": cmd_class.__doc__,
                "schema": cmd_class.schema,
                "example": next((
                    example.strip()
                    for example in (cmd_class.__doc__ or "").split("Example:")
                    if "Example:" in cmd_class.__doc__
                ), None)
            }
        return docs

    @staticmethod
    def print_command_help(action: Optional[str] = None):
        """Print formatted help for commands"""
        docs = JsonExecutor.get_command_docs(action)

        if action:
            docs = {action: docs}

        for cmd_name, cmd_docs in docs.items():
            print(f"\n{Color.colorize('cyan', bold=True, text=f'Command: {cmd_name}')}")
            if cmd_docs.get("description"):
                print(f"\nDescription:")
                print(cmd_docs["description"].strip())

            print("\nParameters:")
            for param, details in cmd_docs["schema"]["properties"].items():
                if param == "action":
                    continue
                print(f"\n  {Color.colorize('yellow', bold=True, text=param)}:")
                print(f"    Type: {details['type']}")
                if "description" in details:
                    print(f"    Description: {details['description']}")
                if "example" in details:
                    print(f"    Example: {details['example']}")
                if "enum" in details:
                    print(f"    Allowed values: {', '.join(details['enum'])}")

            if cmd_docs.get("example"):
                print("\nExample:")
                print(cmd_docs["example"])

    @staticmethod
    def get_schema_string(action: Optional[str] = None, pretty: bool = True) -> str:
        """Get JSON schema as a formatted string"""
        schema = JsonExecutor.get_schema(action)
        return json.dumps(schema, indent=2 if pretty else None)