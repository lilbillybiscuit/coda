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
from src.commands.base import CommandError, CommandRegistry, CommandResult
import threading
import copy
import time
from src.commands.execute_commands import prompt_for_permission
from src.timer import Timer
client = OpenAI(
    base_url="https://gptapi.lilbillbiscuit.com/",
    api_key="sk-7XSRngxn8CIfEMROtsr3Qw"
)

logging.basicConfig(level=logging.WARN)

current_prompt="""Write an efficient matrix multiplication program in Rust. 
Read Two Matrices from Input Files:
matrix_a.txt: Contains the first matrix.
matrix_b.txt: Contains the second matrix.
Each file represents a matrix with one row per line, and elements in each row separated by spaces. It is guaranteed that the number of columns in matrix_a.txt equals the number of rows in matrix_b.txt.
Perform Matrix Multiplication:
Compute the product of Matrix A and Matrix B.
Exclude computations involving zero elements where possible to enhance performance.
Write the Resulting Matrix to an Output File:
output.txt: Contains the resulting product matrix.
Format the output similarly to the input files (one row per line, elements separated by spaces).
You are only allowed to use built-in Rust functions and functions Rust standard library. External dependencies are unallowed.
"""


class CODA:
    def __init__(self, docker_config: DockerConfig, prompt_manager: PromptManager, json_executor: JsonExecutor):
        self.docker_config = docker_config
        self.prompt_manager = prompt_manager
        self.json_executor = json_executor
        self.prompt_manager_snapshot = None
        self.previous_suggestions = []

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
        # task_description = Color.colorize_input("white", bold=True, text="Enter the task description: ", multiline=True).strip()
        # working_directory = Color.colorize_input("white", bold=True,
        #                                          text="Enter the path to the working directory: ").strip()
        #
        # if working_directory == "":
        #     working_directory = "/workspace"
        # return task_description, working_directory
        return current_prompt, "/workspace"

    def c_generate_commands(self, task_description: str, working_directory: str, callback: Optional[callable] = None):
        """Generate commands based on task description."""
        self.prompt_manager.set_system_message(
            f"""You are an AI programmer tasked with generating a sequence of Linux commands to accomplish a specific programming task.

**Objective:** Generate a JSON array of commands to fulfill the user's task description.

**Constraints:**

*   Output only a valid JSON array (no extra text, newlines, or markdown).
*   Each command in the array must be atomic and focused.
*   Each command must include an "action" and a "summary" field.
*   Refer to the available command schemas:
    ```json
    {json.dumps(self.json_executor.get_command_docs(), indent=2)}
    ```
*   Use the "complete" command only when the task is fully solved and you have seen "PROGRAM RESULT" in the chat history.
*   Prioritize code correctness and efficiency. Consider compiler optimization flags like `-C opt-level=3`.
*   If you encounter an error, use debugging techniques to identify the cause.
*   If a command fails repeatedly or you are stuck, use the "giveup" command.
*   Do not re-run the same command if it has already been executed without changes to its parameters.
*   If dependencies or tools are missing, install them using appropriate commands.
*   Focus on iterative development: run one or two commands at a time and check the results before proceeding."""
        )

        prompt = f"""Accomplish the task described below.
When you are done, and before you complete, check correctness and print the time to run in ms with known good libraries (eg. python libraries like numpy).
**Original Prompt:**
{current_prompt}

**Task Description:**

{task_description}

**Working Directory:**

{working_directory}

**Execution Context:**

Assume commands with output results in the chat history have already been executed."""

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
    def c_generate_optimization_task(self, task_description: str, working_directory: str, callback: Optional[callable] = None):
        """Generate commands based on task description."""
        self.prompt_manager.set_system_message(f"""
You are an AI assistant specializing in code optimization. Your goal is to suggest strategies to improve the performance of code generated by the programming agent.

**Objective:** Analyze the provided task description, chat history (including code and execution results), and working directory contents to generate a JSON array of commands. These commands will be used to gather information about the code and its execution environment. Use this information to provide a single optimization suggestion to the programmer.
**Constraints:**

*   Output only a valid JSON array (no extra text or markdown).
*   Each command must include an "action" and a "summary" field.
*   Refer to the available command schemas:
    ```json
    {json.dumps(self.json_executor.get_command_docs(), indent=2)}
    ```
*   Focus on providing ONE concrete optimization suggestion at a time.
*   Your optimization suggestion should be concise and start with phrases like "Alter your code so that..." or "Change the code to...".
*   Consider factors like:
    *   Cache sizes (use `lscpu` or similar commands)
    *   CPU architecture details
    *   SIMD instructions
    *   Memory access patterns
    *   Parallelism
    *   Algorithmic improvements
    *   Input data types (e.g., integer vs. floating-point, 8-bit, 16-bit, etc.)
*   Hint: Optimizations can be made by gathering necessary information about the environment, task, and current implementation.
*   Once you have formulated a suggestion and are ready to present it, use the "complete" command. The content of the "complete" command's message will be your optimization suggestion.
*   DO NOT use the "complete" command until you have all necessary details. It should be the final command in your sequence.
**  FOCUS on iterative development: run one or two commands at a time and check the results before proceeding.**

System info:
- CPU: Apple M1 Max 10-Core CPU
- RAM: 64 GB
- Architecture: arm64
"""
        )

        prompt = f"""
Read the rust file that was generated by the programming agent. Then, run the code to determine correctness and benchmark the time to run. 
Then, make a suggestion on to improve the performance of the code via the completion command. Do not violate conditions in the original prompt.
Note the running time of the last command. If the time got worse, tell the agent to revert the changes.
**Original Prompt**
{current_prompt}

**Task Description:**

{task_description}

**Working Directory:**

{working_directory}

**Previous Suggestions (Do not reuse)**

{self.get_previous_suggestions()}
**Execution Context:**

Assume commands with output results in the chat history have already been executed. You are providing suggestions to the programmer; you are not writing the code yourself.
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
            color = getattr(command_class, 'color', 'none') if command_class else 'none'

            Color.colorize(color, bold=True, text=f"\n{i}. [{action.upper()}]")
            print(f" {summary}")

    def e_execute_commands(self, commands: List[Dict[str, Any]], working_directory: str) -> Tuple[
        List[CommandResult], Optional[str], bool]:
        """Execute the generated commands. Returns (results, error, is_complete)"""
        results = []
        is_complete = False

        for i, command in enumerate(commands, 1):
            try:
                action = command.get('action', 'unknown')
                summary = command.get('summary', 'No description provided')

                command_class = CommandRegistry.get_command(action)
                color = getattr(command_class, 'color', 'white') if command_class else 'white'

                Color.colorize(color, bold=True,
                               text=f"\n→ {i}/{len(commands)} [{action.upper()}] {summary}")

                result = self.json_executor.execute(command)

                results.extend(result)

                # Print immediate result feedback
                for r in result:
                    if r.status == "completed":
                        Color.colorize("green", bold=True, text=f"✓ {r.summary}")
                    elif r.status == "giveup":
                        Color.colorize("red", bold=True, text=f"✗ {r.summary}")
                        response = Color.colorize_input("white", bold=True,
                                                        text="Do you want to end the current task? (y/n): ").lower()
                        if response.startswith('y'):
                            return results, None, True
                    if r.stdout.strip() != "":
                        Color.colorize(color, bold=False, text=f"→ {r.status}: {r.path}")
                        print("\nOutput:")
                        print(r.stdout.strip())
                    elif r.status:
                        Color.colorize(color, bold=False, text=f"→ {r.status}: {r.path}")

                    if not r.success:
                        raise CommandError(f"Command failed: {r.stderr}")

                if action == "complete":
                    is_complete = True
                    break

            except CommandError as e:
                error_msg = f"Command Error: {str(e)}"
                Color.colorize("red", bold=True, text=f"\n✗ Command failed:")
                Color.colorize("red", bold=False, text=error_msg)

                remaining = len(commands) - i
                if remaining > 0:
                    Color.colorize("yellow", bold=True,
                                   text=f"\nSkipping {remaining} remaining command{'s' if remaining > 1 else ''}")

                return results, error_msg, False

            except Exception as e:
                error_msg = f"Unexpected Error: {str(e)}"
                Color.colorize("red", bold=True, text=f"\n✗ Command failed:")
                Color.colorize("red", bold=False, text=error_msg)
                return results, error_msg, False

        return results, None, is_complete


    def snapshot_prompt_manager(self):
        """Snapshot the prompt manager for debugging."""
        self.prompt_manager_snapshot = copy.deepcopy(self.prompt_manager)

    def restore_prompt_manager(self):
        """Restore the prompt manager from the snapshot."""
        if self.prompt_manager_snapshot:
            self.prompt_manager = self.prompt_manager_snapshot
            self.prompt_manager_snapshot = None
        else:
            Color.colorize("yellow", bold=True, text="No prompt manager snapshot to restore")
            raise ValueError("No prompt manager snapshot to restore")
    def save_suggestion(self, suggestion: str):
        """Save the suggestion to the list of previous suggestions."""
        self.previous_suggestions.append(suggestion)

    def get_previous_suggestions(self):
        """Get the list of previous suggestions."""
        return self.previous_suggestions

def run_standard_agent(coda: CODA, task_description,working_directory: str) -> bool:
    prompt_manager = coda.prompt_manager
    Color.colorize("none", bold=True, text="\nStarting Coding Agent...")
    while True:
        try:
            with Timer("Command Generation Loop"):
                # Generate commands
                Color.colorize("none", bold=True, text="\nGenerating Commands:")
                Color.start_color("grey")
                commands = coda.c_generate_commands(task_description, working_directory,
                                                    lambda x: print(x, end='', flush=True))
                Color.end_color()

            with Timer("Command Execution Loop"):
                # Execute commands
                Color.colorize("blue", bold=True, text="\nExecuting Commands:")
                results, error, is_complete = coda.e_execute_commands(commands, working_directory)

                # save results to chat history including any errors
                prompt_manager.add_message("user", make_output_prompt(results, error))

                if error:
                    Color.colorize("red", bold=True, text=f"\nExecution stopped due to error")
                    continue

                if is_complete:
                    Color.colorize("green", bold=True, text="\nTask completed successfully!")
                    return True

        except Exception as e:
            error_msg = f"Unexpected error during execution: {str(e)}"
            Color.colorize("red", bold=True, text=f"\n✗ {error_msg}")
            # Add the error to the chat history
            prompt_manager.add_message("user", make_output_prompt([], error_msg))
            continue

def run_optimization_agent(coda: CODA, task_description,working_directory: str) -> str:
    coda.snapshot_prompt_manager()
    prompt_manager = coda.prompt_manager
    Color.colorize("none", bold=True, text="\nStarting Optimization Agent...")
    while True:
        try:
            with Timer("Command Generation Loop"):
                # Generate commands
                Color.colorize("none", bold=True, text="\nGenerating Commands for Optimization:")
                Color.start_color("grey")
                commands = coda.c_generate_optimization_task(task_description, working_directory,
                                                    lambda x: print(x, end='', flush=True))
                Color.end_color()

            with Timer("Command Execution Loop"):
                # Execute commands
                Color.colorize("blue", bold=True, text="\nExecuting Commands:")
                results, error, is_complete = coda.e_execute_commands(commands, working_directory)

                # save results to chat history including any errors
                prompt_manager.add_message("user", make_output_prompt(results, error))

                if error:
                    Color.colorize("red", bold=True, text=f"\nExecution stopped due to error")
                    continue

                if is_complete:
                    completion_message = next((r.message for r in results if r.status == "completed"), None)
                    coda.restore_prompt_manager()
                    if completion_message:
                        Color.colorize("yellow", bold=True, text="\nOptimization suggestion:")
                        Color.colorize("yellow", bold=False, text=completion_message)
                        coda.save_suggestion(completion_message)
                        return completion_message
                    else:
                        Color.colorize("red", bold=True, text="\nNo completion message found")
                        return ""

        except Exception as e:
            error_msg = f"Unexpected error during execution: {str(e)}"
            Color.colorize("red", bold=True, text=f"\n✗ {error_msg}")
            # Add the error to the chat history
            prompt_manager.add_message("user", make_output_prompt([], error_msg))
            continue

def make_output_prompt(results: List[CommandResult], error: Optional[str] = None):
    output_prompt = "PROGRAM RESULT:"
    for result in results:
        output_prompt += f"\n{result}\n"

    if error:
        output_prompt += f"\nERROR OCCURRED:\n{error}\n"

    return output_prompt

def main():
    docker_config = DockerConfig()
    prompt_manager = PromptManager()

    Color.colorize(color="green", bold=True, text="Welcome to CODA!")

    with DockerEnvironment(docker_config) as docker_env:
        json_executor = JsonExecutor(working_dir="/workspace", docker_env=docker_env)
        coda = CODA(docker_config, prompt_manager, json_executor)

        try:
            task_description, working_directory = coda.i_get_user_input()
            docker_env.execute(f"mkdir -p {working_directory}")

            Color.colorize("green", bold=True, text="Task Description:")
            Color.colorize("green", bold=False, text=task_description)

            with Timer("Total Session"):
                while True:
                    res = run_standard_agent(coda, task_description, working_directory)
                    task_description = run_optimization_agent(coda, task_description, working_directory)
                    should_continue = Color.colorize_input("none", bold=True, text="Continue? (y/n)").strip()
                    if should_continue.lower() != 'y':
                        break

        except KeyboardInterrupt:
            Color.colorize("yellow", bold=True, text="\nReceived keyboard interrupt, shutting down...")
        except Exception as e:
            error_msg = f"Critical error: {str(e)}"
            Color.colorize("red", bold=True, text=f"\n✗ {error_msg}")
            # Add the error to the chat history
            prompt_manager.add_message("user", make_output_prompt([], error_msg))
        finally:
            save_prompt = Color.colorize_input("none", bold=True,
                                              text="Save chat history before exit? (y/n): ").lower()
            if save_prompt == 'y':
                prompt_manager.save_history("coda_data/chat_history.json")
                print("\nChat history saved.")

if __name__ == "__main__":
    main()