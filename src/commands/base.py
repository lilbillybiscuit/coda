from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from dataclasses import dataclass, field
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
@dataclass
class CommandResult:
    """Standardized output format for command execution results"""
    path: str    # Required path parameter must come first
    status: str  # e.g., "created", "executed", "failed", "completed"
    success: bool
    message: str = ""  # Optional message with default
    stdout: str = ""  # Standard output (optional with default)
    stderr: str = ""  # Standard error/error messages (optional with default)
    summary: Optional[str] = None  # Optional summary
    other: Dict[str, Any] = field(default_factory=dict)  # For additional properties

    def set_summary(self, summary: str) -> 'CommandResult':
        """Set or update the summary after creation"""
        self.summary = summary
        return self  # Allow method chaining

    def __str__(self) -> str:
        """Convert to formatted string similar to make_output_prompt"""
        output = []
        if self.summary:
            output.append(f"Summary: {self.summary}")
        output.append(f"Status: {self.status}")
        output.append(f"Success: {self.success}")
        if self.stdout.strip() != "":
            output.append(f"Standard output:\n{self.stdout}")
        if self.stderr.strip() != "":
            output.append(f"Standard error:\n{self.stderr}")

        # Create other_details dict excluding standard fields
        output.append(f"Other details: {json.dumps(self.other)}")
        return "\n".join(output)

    @classmethod
    def success(cls, status: str, path: str, stdout: str = "", stderr: str = "", **kwargs) -> 'CommandResult':
        """Factory method for successful command outputs"""
        return cls(
            path=path,
            status=status,
            success=True,
            stdout=stdout,
            stderr=stderr,
            other=kwargs
        )

    @classmethod
    def error(cls, error_message: str, path: str, stdout: str = "", **kwargs) -> 'CommandResult':
        """Factory method for failed command outputs"""
        return cls(
            path=path,
            status="failed",
            success=False,
            message=error_message,
            stdout=stdout,
            stderr=error_message,
            other=kwargs
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        result = {
            "path": self.path,
            "status": self.status,
            "success": self.success
        }
        if self.message:
            result["message"] = self.message
        if self.summary is not None:
            result["summary"] = self.summary
        if self.stdout:
            result["stdout"] = self.stdout
        if self.stderr:
            result["stderr"] = self.stderr
        result.update(self.other)
        return result

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
    def execute(self, context: CommandContext) -> CommandResult:
        pass
