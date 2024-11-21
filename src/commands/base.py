from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from abc import ABC, abstractmethod
import jsonschema
from functools import wraps
from src.docker_env import DockerEnvironment


logger = logging.getLogger(__name__)


class CommandError(Exception): pass


class ValidationError(CommandError): pass


class ExecutionError(CommandError): pass


@dataclass
class CommandContext:
    working_dir: Path
    docker_env: Optional[DockerEnvironment] = None
    dry_run: bool = False


class CommandRegistry:
    """Global registry for commands"""
    commands: Dict[str, Type['Command']] = {}

    @classmethod
    def register(cls, action: str, command_class: Type['Command']) -> None:
        cls.commands[action] = command_class

    @classmethod
    def get_command(cls, action: str) -> Optional[Type['Command']]:
        return cls.commands.get(action)

    @classmethod
    def get_all_commands(cls) -> Dict[str, Type['Command']]:
        return cls.commands.copy()


def command(action: str, color: str = "white", **schema_props):
    """
    Decorator that automatically registers commands with simplified schema creation.

    Args:
        action: Command name
        color: Color to use when displaying this command (default: white)
        **schema_props: Additional schema properties
    """

    def decorator(cls):
        # Add summary to properties
        properties = {
            "action": {"type": "string", "enum": [action]},
            "summary": {
                "type": "string",
                "description": "Brief description of what the command does"
            },
            **schema_props.get("properties", {})
        }

        # Build the schema automatically
        schema = {
            "type": "object",
            "required": ["action"] + schema_props.get("required", []),
            "properties": properties,
            "additionalProperties": schema_props.get("additionalProperties", False)
        }

        # Add action, color, and schema to class
        cls.action = action
        cls.color = color
        cls.schema = schema

        # Register the command
        CommandRegistry.register(action, cls)
        return cls

    return decorator


class Command(ABC):
    """Abstract base class for commands"""
    action: ClassVar[str]
    schema: ClassVar[Dict[str, Any]]

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.validate()

    def validate(self) -> None:
        try:
            jsonschema.validate(instance=self.data, schema=self.schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationError(f"Schema validation failed: {e.message}")

    @abstractmethod
    def execute(self, context: CommandContext) -> Dict[str, Any]:
        pass

