import os
import subprocess
from openai import OpenAI

# Set up your OpenAI API key
client = OpenAI(
    #api_key='$OPENAI_API_KEY',
    #organization='org-mETM9MxGgjBXBjKmv4nbS6uJ',
    #project='proj_v8JiNLSbdCBK3AIO2psnuDQX',
)


def call_openai_api(prompt):
    """
    Function to call OpenAI's API and generate a response based on the prompt.
    """
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        stream=False
    )
    
    return completion.choices[0].message.content

def get_user_input():
    """
    Function to get the task description and working directory from the user.
    """
    task_description = input("Enter the task description: ").strip()
    working_directory = input("Enter the path to the working directory: ").strip()
    
    if not os.path.exists(working_directory):
        os.makedirs(working_directory)
        print(f"Created new working directory at {working_directory}")
    else:
        print(f"Using existing working directory at {working_directory}")
    
    return task_description, working_directory

def generate_shell_script(task_description, working_directory):
    """
    Function to generate a shell script using OpenAI's API based on the task description.
    """
    # List the contents of the working directory to inform ChatGPT
    directory_contents = os.listdir(working_directory)
    if directory_contents:
        directory_listing = '\n'.join(directory_contents)
    else:
        directory_listing = 'The directory is empty.'
    
    # Prepare the prompt
    prompt = f"""
    You are to write a shell script that performs the following task:
    {task_description}
    
    The script should work in the directory: {working_directory}
    The current contents of the directory are:
    {directory_listing}
    
    Please provide only the shell script code without any additional explanations.
    """
    
    shell_script = call_openai_api(prompt)
    return shell_script

def save_shell_script(shell_script, script_path):
    """
    Function to save the generated shell script to a file and make it executable.
    """
    with open(script_path, 'w') as file:
        file.write(shell_script)
    os.chmod(script_path, 0o755)  # Make the script executable

def execute_shell_script(script_path, working_directory):
    """
    Function to execute the shell script and collect logs.
    """
    process = subprocess.Popen(
        [script_path],
        cwd=working_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True
    )
    stdout, stderr = process.communicate()
    return stdout, stderr

def analyze_logs(stdout, stderr, task_description):
    """
    Function to analyze the execution logs using OpenAI's API to determine success.
    """
    # Prepare the prompt for analysis
    prompt = f"""
    The following execution logs are from a shell script intended to perform the task:
    {task_description}
    
    Standard Output (STDOUT):
    {stdout}
    
    Standard Error (STDERR):
    {stderr}
    
    Based on these logs, did the script complete the task successfully? If not, what errors occurred, and how can they be fixed?
    
    Revise the original task description so that it would lead to a successful execution.
    
    Only provide the revised task description without any additional explanations.
    """
    
    # Call OpenAI API to analyze the logs
    
    analysis = call_openai_api(prompt)
    return analysis

def main():
    """
    Main function to run the CODA workflow.
    """
    task_description, working_directory = get_user_input()
    while True:
        # Generate the shell script
        shell_script = generate_shell_script(task_description, working_directory)
        
        # if it starts with ```, remove the first and the last line.
        if shell_script.startswith("```"):
            shell_script = shell_script.split("\n")[1:-1]
            shell_script = "\n".join(shell_script)
        
        print("\nGenerated Shell Script:\n")
        print(shell_script)
        
        # Save the shell script to a file
        script_path = os.path.join(working_directory, 'coda_script.sh')
        save_shell_script(shell_script, script_path)
        
        # Execute the shell script and collect logs
        stdout, stderr = execute_shell_script(script_path, working_directory)
        print("\nExecution Logs:\n")
        print("STDOUT:\n", stdout)
        
        # Analyze the execution logs
        
        if len(stderr.strip()) > 0:
            print("STDERR:\n", stderr)

            task_description = analyze_logs(stdout, stderr, task_description)
            print("\nRevised description:\n")
            print(task_description)
        
        # Determine if the task was completed successfully
        else:
            print("\nTask completed successfully.")
            # Ask for a follow-up task
            follow_up = input("\nEnter a follow-up task description (or press Enter to exit): ").strip()
            if not follow_up:
                print("Exiting CODA.")
                break
            else:
                task_description = follow_up
            

if __name__ == "__main__":
    main()
