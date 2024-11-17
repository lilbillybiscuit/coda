import os
from openai import OpenAI
from src.docker_env import DockerEnvironment, DockerConfig
from typing import List, Dict, Any, Optional
import datetime
from src.prompt_manager import PromptManager
from src.formatting import Color
import threading
import time
# Set up your OpenAI API key
client = OpenAI()

# i = user interaction
# c = computer generation
# e = computer execution
class CODA:
    def __init__(self, docker_config: DockerConfig, prompt_manager: PromptManager):
        self.docker_config = docker_config
        self.prompt_manager = prompt_manager

    def call_openai_api(self, callback: Optional[callable]=None):
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
        """
        Function to get the task description and working directory from the user.
        """
        task_description = Color.colorize_input("white", bold=True, text="Enter the task description: ").strip()
        working_directory = Color.colorize_input("white", bold=True, text="Enter the path to the working directory: ").strip()

        # Convert to absolute path if relative
        # working_directory = os.path.abspath(working_directory)

        if working_directory == "":
            working_directory = "/workspace"
        return task_description, working_directory

    def c_generate_shell_script(self, task_description, working_directory, docker_env, callback: Optional[callable] = None):
        stdout, stderr = docker_env.execute(f"ls -la {working_directory}")
        directory_listing = stdout if stdout else "The directory is empty."

        # Set task-specific system message
        self.prompt_manager.set_system_message(
            "You are an AI assistant that generates shell scripts that run on a fresh Ubuntu 22.04 environment."
            "Provide only the script code WITHOUT any markdown formatting or explanations. This means no backticks."
            "Ensure the script is compatible with bash and handles errors appropriately. "
            "Scripts that you have written before have already been executed in the environment (although they may not have run to completion, as according to the output)."
        )

        prompt = f"""
        Generate a shell script for the following task:
        {task_description}

        Working directory: {working_directory}
        Directory contents:
        {directory_listing}
        """
        self.prompt_manager.add_message("user", prompt)
        shell_script = self.call_openai_api(callback=callback)
        return shell_script

    def e_save_shell_script(self, shell_script, docker_env, script_path):
        """
        Function to save the generated shell script to the container and make it executable.
        """
        # Copy script content to container
        docker_env.copy_to_container(shell_script, script_path)
        # Make script executable
        docker_env.execute(f"chmod +x {script_path}")

    def e_execute_shell_script(self, script_path, working_directory, docker_env):
        """
        Function to execute the shell script in the container and collect logs.
        """

        def spinner():
            while True:
                for frame in ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]:
                    print(f"\r{frame} Running script...", end='', flush=True)
                    yield

        def spin():
            while not done:
                next(spinner)
                time.sleep(0.1)

        done = False
        spinner = spinner()
        spin_thread = threading.Thread(target=spin)
        spin_thread.start()
        try:
            stdout, stderr = docker_env.execute(
                f"bash {script_path}",
                workdir=working_directory
            )
        finally:
            done = True
            spin_thread.join()
            print("\r", end='', flush=True)
        return stdout, stderr

    def c_analyze_logs(self, stdout: str, stderr: str, task_description: str, callback: Optional[callable] = None) -> str:
        self.prompt_manager.set_system_message(
            "You are an AI assistant that analyzes script execution logs. "
            "Provide only the revised task description without explanations."
        )

        prompt = f"""
        Analyze these execution logs for the task:
        {task_description}

        STDOUT:
        {stdout}

        STDERR:
        {stderr}

        Provide a revised task description that would lead to successful execution.
        """

        self.prompt_manager.add_message("user", prompt)
        analysis = self.call_openai_api(callback=callback)

        # Remove the analysis exchange but keep execution logs
        self.prompt_manager.pop_message()
        self.prompt_manager.pop_message()

        # Add execution logs as a user message
        self.prompt_manager.add_message("user",
        f"""Results of last execution:
        STDOUT:
        {stdout}
        
        STDERR:
        {stderr}
        """)

        return analysis

def main():
    docker_config = DockerConfig()
    prompt_manager = PromptManager()

    Color.colorize(color="green", bold=True, text="Welcome to CODA!")

    coda = CODA(docker_config, prompt_manager)

    with DockerEnvironment(docker_config) as docker_env:
        task_description, working_directory = coda.i_get_user_input()
        docker_env.execute(f"mkdir -p {working_directory}")

        Color.colorize("green", bold=True, text="Task Description:")
        Color.colorize("green", bold=False, text=task_description)

        while True:
            # generate script
            Color.colorize("yellow", bold=True, text="Generating Shell Script:")
            Color.start_color("grey")
            shell_script = coda.c_generate_shell_script(task_description, working_directory, docker_env, lambda x: print(x, end='', flush=True))
            Color.end_color()

            # save script and execute
            script_path = os.path.join(working_directory, 'coda_script.sh')
            coda.e_save_shell_script(shell_script, docker_env, script_path)

            stdout, stderr = coda.e_execute_shell_script(script_path, working_directory, docker_env)
            print()
            Color.colorize("yellow", bold=True, text="Execution Logs:")
            print("STDOUT:")
            print(stdout)

            # if error
            if len(stderr.strip()) > 0:
                print("STDERR:")
                print(stderr)

                Color.colorize("yellow", bold=True, text="Revised Description:")
                task_description = coda.c_analyze_logs(stdout, stderr, task_description, lambda x: print(x, end='', flush=True))
                print()
            else:
                Color.colorize("green", bold=True, text="Task completed successfully.\n")
                follow_up = Color.colorize_input("white", bold=True, text="Enter a follow-up task description (or press Enter to exit):").strip()
                if not follow_up:
                    save_chat = Color.colorize_input("white", bold=True, text="Save chat history? (y/n):").lower()=='y'
                    if save_chat:
                        prompt_manager.save_history("coda_data/chat_history.json")
                        print("\nChat history saved.")
                    print("Exiting CODA.")
                    break
                else:
                    task_description = follow_up
                    print()


            keep_context = Color.colorize_input("white", bold=True, text="Keep context for next iteration? (y/n):").lower()=='y'
            if not keep_context:
                prompt_manager.clear_history()


if __name__ == "__main__":
    main()
