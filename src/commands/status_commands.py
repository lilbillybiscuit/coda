from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from src.commands.base import Command, CommandContext, ValidationError, ExecutionError, command, CommandResult
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

    def execute(self, context: CommandContext) -> CommandResult:
        return CommandResult(
            status="completed",
            success=self.data.get("success", True),
            path="",
            stdout="",
            stderr="",
            summary=self.data["message"]
        )

@command("giveup", color="red",
         properties={
             "message": {
                 "type": "string",
                 "description": "Message explaining why giving up",
                 "example": "Unable to complete task due to permission issues"
             }
         })
class GiveUpCommand(Command):
    """
    End the current task loop with a give up message.

    Example:
    {
        "action": "giveup",
        "message": "Unable to complete task due to permission issues"
    }
    """

    def execute(self, context: CommandContext) -> CommandResult:
        return CommandResult(
            status="giveup",
            success=False,
            path="",
            stdout="",
            stderr="",
            summary=self.data.get("message", "Task abandoned")
        )
