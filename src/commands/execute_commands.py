from typing import Dict, Any, List, Callable, Optional, Type, ClassVar, Union
from src.commands.base import Command, CommandContext, ValidationError, ExecutionError, command
import shlex
from src.formatting import Color
from src.commands.base import CommandRegistry, CommandResult
import threading
import time
import logging

logger = logging.getLogger(__name__)


def prompt_for_permission(cmd_str: str) -> bool:
    """Ask user for permission to execute command"""
    Color.colorize("yellow", bold=True, text="\nWARNING: Attempting to execute potentially unsafe command:")
    Color.colorize("yellow", bold=False, text=cmd_str)
    response = Color.colorize_input("white", bold=True, text="\nAllow execution? (y/n): ").lower()
    return response.startswith('y')

@command("execute", color="yellow",
         properties={
             "command": {
                 "type": "string",
                 "description": "The file or program to execute",
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
             },
             "environment": {
                "type": "object",
                "description": "Environment variables to set for the execution",
                "example": {"PYTHONPATH": "/workspace/project"}
            }
         })
class ExecuteCommand(Command):
    """
    Execute a file or program with specified arguments and environment.
    Note that there is a runtime limit of 30 seconds, so if anything is over that, then your program or command is likely too inefficient

    Example:
    {
        "action": "execute",
        "command": "python",
        "arguments": ["--input", "data.txt"],
        "workdir": "/workspace/project",
        "environment": {"PYTHONPATH": "/workspace/project"}
    }
    """

    SAFE_COMMANDS = {
        "ls", "cat", "echo", "mkdir", "touch", "cp", "mv",
        "grep", "find", "pwd", "cd", "head", "tail", "wc",
        "sort", "uniq", "diff", "tar", "gzip", "gunzip"
    }

    TIMEOUT_SECONDS = 30

    def is_command_safe(self, cmd_str: str) -> bool:
        """Check if the shell command is in the whitelist"""
        try:
            # Parse command string to get the base command
            parsed_cmd = shlex.split(cmd_str)
            if not parsed_cmd:
                return False

            # Get the base command
            base_cmd = parsed_cmd[0]

            # Check if the base command is in the safe list
            return base_cmd in self.SAFE_COMMANDS

        except Exception as e:
            logger.warning(f"Error parsing command '{cmd_str}': {e}")
            return False

    def execute(self, context: CommandContext) -> CommandResult:
        if not context.docker_env:
            return CommandResult(
                path="",
                status="error",
                success=False,
                message="Docker environment required for execution"
            )

        command = self.data["command"]
        workdir = self.data.get("workdir", str(context.working_dir))
        args = self.data.get("arguments", [])
        env = self.data.get("environment", {})

        cmd = [command] + args
        cmd_str = " ".join(cmd)

        timeout_cmd = f"timeout {self.TIMEOUT_SECONDS}s {cmd_str}"

        if context.dry_run:
            return CommandResult(
                path=workdir,
                status="would execute",
                success=True,
                message=f"Would execute: {cmd_str}"
            )
        # if not self.is_command_safe(cmd_str): #FIXME: Disabling this check for now
        #     if not prompt_for_permission(cmd_str):
        #         raise ExecutionError("Command execution denied by user")
        start_time = time.time()
        execution_completed = False
        command_result = None

        def format_time(seconds):
            """Format seconds into mm:ss format"""
            minutes = int(seconds // 60)
            seconds = int(seconds % 60)
            return f"{minutes:02d}:{seconds:02d}"

        def format_time_remaining(elapsed):
            """Format remaining time with countdown"""
            remaining = max(0, self.TIMEOUT_SECONDS - elapsed)
            return format_time(remaining)

        def spinner():
            while True:
                for frame in ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]:
                    elapsed = time.time() - start_time
                    remaining = format_time_remaining(elapsed)
                    spinner_text = f"\r{frame} Running {cmd_str} ({format_time(elapsed)} / timeout in {remaining})..."
                    print("\r" + " " * 100 + "\r", end="", flush=True)
                    Color.colorize('yellow', bold=False, text=spinner_text, end='', flush=True)
                    yield

        def spin():
            while not done:
                next(spinner_gen)
                time.sleep(0.1)

        def execute_with_timeout():
            nonlocal execution_completed, command_result
            try:
                # Execute with the timeout command
                stdout, stderr, exit_code = context.docker_env.execute(
                    timeout_cmd,
                    workdir=workdir,
                    environment=env
                )
                execution_completed = True
                elapsed_time = time.time() - start_time

                # Check if the command was terminated by timeout
                if exit_code == 124:  # timeout command exit code for timeout
                    command_result = CommandResult(
                        path=cmd_str,
                        status="timeout",
                        success=False,
                        message=f"Command timed out after {format_time(elapsed_time)}",
                        stderr=f"Command execution exceeded timeout of {self.TIMEOUT_SECONDS} seconds",
                        other={
                            "command": cmd_str,
                            "execution_time": f"{format_time(elapsed_time)}",
                            "timeout": self.TIMEOUT_SECONDS
                        }
                    )
                else:
                    success = exit_code == 0
                    status = "executed" if success else "failed"
                    message = f"Command executed with exit code {exit_code}"

                    command_result = CommandResult(
                        path=cmd_str,
                        status=status,
                        success=success,
                        message=message,
                        stdout=stdout,
                        stderr=stderr,
                        other={
                            "exit_code": exit_code,
                            "command": cmd_str,
                            "execution_time": f"{format_time(elapsed_time)}"
                        }
                    )
            except Exception as e:
                execution_completed = True
                command_result = CommandResult(
                    path=cmd_str,
                    status="error",
                    success=False,
                    message=str(e),
                    stderr=str(e)
                )

        done = False
        spinner_gen = spinner()
        spin_thread = threading.Thread(target=spin)
        spin_thread.daemon = True
        spin_thread.start()

        try:
            # Execute in a separate thread
            execution_thread = threading.Thread(target=execute_with_timeout)
            execution_thread.daemon = True
            execution_thread.start()

            # Wait a bit longer than the timeout to allow for cleanup
            execution_thread.join(timeout=self.TIMEOUT_SECONDS + 2)

            if not execution_completed:
                # If we get here, something went wrong with the timeout command itself
                elapsed_time = time.time() - start_time
                # Try to kill any remaining processes
                context.docker_env.execute(f"pkill -9 -f '{cmd_str}'")

                return CommandResult(
                    path=cmd_str,
                    status="timeout",
                    success=False,
                    message=f"Command timed out after {format_time(elapsed_time)}",
                    stderr=f"Command execution exceeded timeout of {self.TIMEOUT_SECONDS} seconds",
                    other={
                        "command": cmd_str,
                        "execution_time": f"{format_time(elapsed_time)}",
                        "timeout": self.TIMEOUT_SECONDS
                    }
                )

            return command_result

        except Exception as e:
            return CommandResult(
                path=cmd_str,
                status="error",
                success=False,
                message=str(e),
                stderr=str(e)
            )
        finally:
            done = True
            spin_thread.join(timeout=0.1)
            # Ensure spinner line is completely cleared
            print("\r" + " " * 100 + "\r", end="", flush=True)