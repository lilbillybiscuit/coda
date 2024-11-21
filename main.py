import logging
import os
from openai import OpenAI
from src.docker_env import DockerEnvironment, DockerConfig
from typing import List, Dict, Any, Optional, Tuple
import datetime
from src.prompt_manager import PromptManager
from src.formatting import Color
from src.json_executor import JsonExecutor
import json
from src.commands.base import CommandError, CommandRegistry
import threading
import time
from src.commands.execute_commands import prompt_for_permission

client = OpenAI()

logging.basicConfig(level=logging.WARN)


class CODA:
    def __init__(self, docker_config: DockerConfig, prompt_manager: PromptManager, json_executor: JsonExecutor):
        self.docker_config = docker_config
        self.prompt_manager = prompt_manager
        self.json_executor = json_executor

    def call_openai_api(self, callback: Optional[callable] = None):
        messages = self.prompt_manager.get_messages()

        full_response = ""
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            stream=True,
            temperature=0
        )

        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_response += content
                if callback:
                    callback(content)

        self.prompt_manager.add_message("assistant", full_response)
        return full_response

    def i_get_user_input(self):
        """Get task description and working directory from user."""
        task_description = Color.colorize_input("white", bold=True, text="Enter the task description: ").strip()
        working_directory = Color.colorize_input("white", bold=True,
                                                 text="Enter the path to the working directory: ").strip()

        if working_directory == "":
            working_directory = "/workspace"
        return task_description, working_directory

    def c_generate_commands(self, task_description: str, working_directory: str, callback: Optional[callable] = None):
        """Generate commands based on task description."""
        self.prompt_manager.set_system_message(
            "You are an AI assistant that generates commands to accomplish tasks in a Linux environment. "
            "Return a JSON array of command objects. Available commands: create, append, execute, delete, complete. "
            "Use the 'complete' command when you determine the task is finished. Do NOT write complete until you have seen 'PROGRAM RESULT' in the chat history."
            "Each command should include a 'summary' field that briefly describes what the command does. "
            "Each command should be atomic and focused. Format the response as a valid JSON array without explanations or markdown. For execute commands, you can assume that you are running these commands in a shell -- no need to write bash as the main command"
            f"Available commands and their schemas:\n{json.dumps(self.json_executor.get_command_docs(), indent=2)}"
            "Return only a JSON array of commands. Each command should include a 'summary' field."
        )

        prompt = f"""
        Generate commands for the following task:
        {task_description}

        Working directory: {working_directory}
        """

        self.prompt_manager.add_message("user", prompt)
        response = self.call_openai_api(callback=callback)

        if "```" in response[:7]:
            response_split = response.split("\n")[1:-1]
            response = "\n".join(response_split)


        try:
            commands = json.loads(response)
            if not isinstance(commands, list):
                commands = [commands]
            return commands
        except json.JSONDecodeError:
            raise ValueError("Failed to parse commands as JSON")

    def print_command_summary(self, commands: List[Dict[str, Any]]):
        """Print a summary of commands to be executed."""
        Color.colorize("yellow", bold=True, text="\nCommands to execute:")
        for i, cmd in enumerate(commands, 1):
            action = cmd.get('action', 'unknown')
            summary = cmd.get('summary', 'No description provided')

            # Get command color from registry
            command_class = CommandRegistry.get_command(action)
            color = getattr(command_class, 'color', 'white') if command_class else 'white'

            Color.colorize(color, bold=True, text=f"\n{i}. [{action.upper()}]")
            print(f" {summary}")


    def e_execute_commands(self, commands: List[Dict[str, Any]], working_directory: str) -> Tuple[
        List[Dict[str, Any]], Optional[str], bool]:
        """Execute the generated commands. Returns (results, error, is_complete)"""
        results = []
        is_complete = False

        for i, command in enumerate(commands, 1):
            try:
                action = command.get('action', 'unknown')
                summary = command.get('summary', 'No description provided')

                # Get command color from registry
                command_class = CommandRegistry.get_command(action)
                color = getattr(command_class, 'color', 'white') if command_class else 'white'

                Color.colorize(color, bold=True,
                               text=f"\n→ {i}/{len(commands)} [{action.upper()}] {summary}")

                # Show spinner for execute commands
                result = self.json_executor.execute(command)

                results.extend(result)

                # Print immediate result feedback
                for r in result:
                    if r.get("status") == "completed":
                        Color.colorize("green", bold=True, text=f"✓ {r['message']}")
                    elif "stdout" in r and r["stdout"].strip():
                        print("\nOutput:")
                        print(r["stdout"].strip())
                    elif r.get("status"):
                        Color.colorize(color, bold=False, text=f"→ {r['status']}: {r.get('path', '')}")

                    # Check for errors in the result
                    if r.get("stderr") and r["stderr"].strip():
                        error_msg = r["stderr"].strip()
                        Color.colorize("red", bold=True, text=f"\n✗ Command failed:")
                        Color.colorize("red", bold=False, text=error_msg)
                        return results, error_msg, False

                if action == "complete":
                    is_complete = True
                    break

            except CommandError as e:
                error_msg = str(e)
                Color.colorize("red", bold=True, text=f"\n✗ Command failed:")
                Color.colorize("red", bold=False, text=error_msg)

                # Show which command failed in the sequence
                remaining = len(commands) - i
                if remaining > 0:
                    Color.colorize("yellow", bold=True,
                                   text=f"\nSkipping {remaining} remaining command{'s' if remaining > 1 else ''}")

                return results, error_msg, False
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                Color.colorize("red", bold=True, text=f"\n✗ Command failed:")
                Color.colorize("red", bold=False, text=error_msg)
                return results, error_msg, False

        return results, None, is_complete

def main():
    docker_config = DockerConfig()
    prompt_manager = PromptManager()

    Color.colorize(color="green", bold=True, text="Welcome to CODA!")

    with DockerEnvironment(docker_config) as docker_env:
        json_executor = JsonExecutor(working_dir="/workspace", docker_env=docker_env)
        coda = CODA(docker_config, prompt_manager, json_executor)

        task_description, working_directory = coda.i_get_user_input()
        docker_env.execute(f"mkdir -p {working_directory}")

        Color.colorize("green", bold=True, text="Task Description:")
        Color.colorize("green", bold=False, text=task_description)

        while True:
            # Generate commands
            Color.colorize("yellow", bold=True, text="\nGenerating Commands:")
            Color.start_color("grey")
            commands = coda.c_generate_commands(task_description, working_directory, lambda x: print(x, end='', flush=True))
            Color.end_color()

            # Print command summary
            # coda.print_command_summary(commands)

            # # Confirm execution
            # if Color.colorize_input("white", bold=True, text="\nProceed with execution? (y/n): ").lower() != 'y':
            #     Color.colorize("yellow", bold=True, text="Execution cancelled.")
            #     if Color.colorize_input("white", bold=True, text="Generate new commands? (y/n): ").lower() != 'y':
            #         break
            #     continue

            # Execute commands
            Color.colorize("yellow", bold=True, text="\nExecuting Commands:")
            results, error, is_complete = coda.e_execute_commands(commands, working_directory)

            # save results to chat history
            result_prompt = f"\nPROGRAM RESULTS:\n{json.dumps(results, indent=2)}"
            prompt_manager.add_message("user", result_prompt)

            if error:
                Color.colorize("red", bold=True, text=f"\nExecution stopped due to error")
                keep_context = Color.colorize_input("white", bold=True,
                                                    text="Keep context for retry? (y/n): ").lower() == 'y'
                if not keep_context:
                    prompt_manager.clear_history()
                continue

            if is_complete:
                Color.colorize("green", bold=True, text="\nTask completed successfully!")
                follow_up = Color.colorize_input("white", bold=True, text="Enter a follow-up task description (or press Enter to exit): ").strip()
                if not follow_up:
                    save_chat = Color.colorize_input("white", bold=True, text="Save chat history? (y/n): ").lower()=='y'
                    if save_chat:
                        prompt_manager.save_history("coda_data/chat_history.json")
                        print("\nChat history saved.")
                    print("Exiting CODA.")
                    break
                else:
                    task_description = follow_up
                    keep_context = Color.colorize_input("white", bold=True, text="Keep context for next task? (y/n): ").lower()=='y'
                    if not keep_context:
                        prompt_manager.clear_history()
                    print()

if __name__ == "__main__":
    main()