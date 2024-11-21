from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from src.commands.base import Command, CommandContext, ValidationError, ExecutionError, command
import shlex
from src.formatting import Color
from src.commands.base import CommandRegistry
import threading
import time


def prompt_for_permission(cmd_str: str) -> bool:
    """Ask user for permission to execute command"""
    Color.colorize("yellow", bold=True, text="\nWARNING: Attempting to execute potentially unsafe command:")
    Color.colorize("yellow", bold=False, text=cmd_str)
    response = Color.colorize_input("white", bold=True, text="\nAllow execution? (y/n): ").lower()
    return response.startswith('y')

@command("execute", color="yellow",
         required=["target"],
         properties={
             "target": {
                 "type": "string",
                 "description": "The file to execute",
                 "example": "script.py"
             },
             "language": {
                 "type": "string",
                 "enum": ["python", "javascript", "shell"],
                 "description": "Programming language of the target file",
                 "example": "python"
             },
             "arguments": {
                 "type": "array",
                 "items": {"type": "string"},
                 "description": "Command line arguments to pass to the program",
                 "example": ["--input", "data.txt"]
             },
             "workdir": {
                 "type": "string",
                 "description": "Working directory for execution",
                 "example": "/workspace/project"
             }
         })
class ExecuteCommand(Command):
    """
    Execute a file with specified language interpreter.

    Example:
    {
        "action": "execute",
        "target": "main.py",
        "language": "python",
        "arguments": ["--input", "data.txt"],
        "workdir": "/workspace"
    }
    """

    SAFE_COMMANDS = {
        "python": {
            "python",
            "pip",
            "pytest"
        },
        "javascript": {
            "node",
            "npm",
            "yarn"
        },
        "shell": {
            "ls", "cat", "echo", "mkdir", "touch", "cp", "mv",
            "grep", "find", "pwd", "cd", "head", "tail", "wc",
            "sort", "uniq", "diff", "tar", "gzip", "gunzip"
        }
    }

    def is_command_safe(self, cmd_str: str, language: str) -> bool:
        """Check if the command is in the whitelist"""
        # Parse command string to get the base command
        try:
            parsed_cmd = shlex.split(cmd_str)
            if not parsed_cmd:
                return False

            base_cmd = parsed_cmd[0]

            # For shell commands, also check the first actual command
            if language == "shell":
                # Read the script content
                try:
                    with open(parsed_cmd[1], 'r') as f:
                        script_content = f.read()
                        # Get first non-empty, non-comment line
                        for line in script_content.splitlines():
                            line = line.strip()
                            if line and not line.startswith('#'):
                                script_cmd = shlex.split(line)[0]
                                return script_cmd in self.SAFE_COMMANDS[language]
                except:
                    return False

            # For other languages, check if the interpreter is safe
            return base_cmd in self.SAFE_COMMANDS.get(language, set())

        except:
            return False

    def execute(self, context: CommandContext) -> Dict[str, Any]:
        if not context.docker_env:
            raise ExecutionError("Docker environment required for execution")

        target = self.data["target"]
        workdir = self.data.get("workdir", str(context.working_dir))
        language = self.data.get("language", "").lower()
        args = self.data.get("arguments", [])

        cmd_map = {
            "python": ["python", target],
            "javascript": ["node", target],
            "shell": [target],
        }

        cmd = cmd_map.get(language, [target]) + args
        cmd_str = " ".join(cmd)

        if context.dry_run:
            return {"status": "would execute", "command": cmd_str}

        # Check if command is safe
        if not self.is_command_safe(cmd_str, language):
            if not prompt_for_permission(cmd_str):
                raise ExecutionError("Command execution denied by user")


        def spinner():
            while True:
                for frame in ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]:
                    spinner_text = f"\r{frame} Running {cmd_str}..."
                    Color.colorize('yellow', bold=False, text=spinner_text, end='', flush=True)
                    yield

        def spin():
            while not done:
                next(spinner_gen)
                time.sleep(0.1)

        done = False
        spinner_gen = spinner()
        spin_thread = threading.Thread(target=spin)
        spin_thread.start()

        try:
            stdout, stderr = context.docker_env.execute(cmd_str, workdir=workdir)
            done = True
            spin_thread.join()
            print("\r", end='', flush=True)
            return {
                "status": "executed",
                "command": cmd_str,
                "stdout": stdout,
                "stderr": stderr
            }
        except Exception as e:
            raise ExecutionError(f"Failed to execute: {e}")
