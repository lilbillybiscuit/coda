from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from src.commands.base import Command, CommandContext, ValidationError, ExecutionError, command
import shlex
from src.formatting import Color

@command("complete", color="green",
         required=["message"],
         properties={
             "message": {
                 "type": "string",
                 "description": "Completion message or summary",
                 "example": "Successfully created and configured the Python project"
             },
             "success": {
                 "type": "boolean",
                 "description": "Whether the task was completed successfully",
                 "example": True
             }
         })
class CompleteCommand(Command):
    """
    Mark a task as complete with a summary message.

    Example:
    {
        "action": "complete",
        "message": "Successfully created and configured the Python project",
        "success": true
    }
    """
    def execute(self, context: CommandContext) -> Dict[str, Any]:
        return {
            "status": "completed",
            "message": self.data["message"],
            "success": self.data.get("success", True)
        }
