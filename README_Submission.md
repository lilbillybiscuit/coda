# Lab 3: Building an AI Software Engineer 

I used ChatGPT to plan out the steps for the lab, and then I mostly wrote the code myself.

Approximately ~50% (400 lines) of the code is written using ChatGPT. I generated a lot of the docker code (with a lot of special prompting to fit my environment), and some of the prompt manager code. I wrote the rest of the code, or used ChatGPT to refactor the starter code.

## Part 1
When I set out to do this assignment, in addition to the requirements, I also kept a focus on security, reliability, and reproducibility. I worked towards these goals because this is what I believe that an AI programmer should be, it should be explainable, reproducible, and if something goes wrong, then it should be easy to fix.

To fit the three goals, I made the following decisions:
- Used Docker to containerize the environment. This makes it very easy to reproduce the environment, with minimal setup. By using Docker, we can limit the blast radius in case anything goes wrong, so if (most) insecure code is generated and run, it will not affect the system, and it will at max only affect the mounted folder. 
- A new Docker container is created every time the program is run. The model would have to install the dependencies in the environment every time, but this is a small price to pay for reliability and reproducibility.

This resulted in a few hundred lines of extra code, but I think it's worth it. It makes my code very portable and democratized, which is important in the context of AI programming and the software engineering community.

My results are in the coda_output directory, organized into the following structure:
```
coda_output
├── 1_image_processing
│   ├── chat_history.json
│   ├── chat_log.txt
│   └── output.png
├── 2_markdown_html
│   ├── README.html
│   ├── chat_history.json
│   └── chat_log.txt
└── 3_status_checker
    ├── chat_history.json
    ├── chat_log.txt
    └── status_report.txt
```

For the most part, I followed the structure of the starter code, but I significantly altered the prompts as I prompt engineered my way. I settled on an agent-based system, where we modify the system prompt to give each AI call a "role" (for example, script writing, analyzing, etc). The prompts are as follows:

Coding Agent System Prompt:
```
You are an AI assistant that generates shell scripts that run on a fresh Ubuntu 22.04 environment.
Provide only the script code WITHOUT any markdown formatting or explanations. This means no backticks.
Ensure the script is compatible with bash and handles errors appropriately.
Scripts that you have written before have already been executed in the environment (although they may not have run to completion, as according to the output).
```
Direct prompt:
```
Generate a shell script for the following task:
{task_description}

Working directory: {working_directory}
Directory contents:
{directory_listing}
```

Analysis/Revision Agent System Prompt:
```
You are an AI assistant that analyzes script execution logs.
Provide only the revised task description without explanations.
```

Direct prompt:
```
Analyze these execution logs for the task:
{task_description}

STDOUT:
{stdout}

STDERR:
{stderr}

Provide a revised task description that would lead to successful execution.
```

These prompts were optimized to code like a human would. The instructions are direct, and I modified them a bit to reduce edge cases (troubles with environment, etc)

I made sure to include the execution logs in the chat histories so that the agents could communicate and know what the previous task was. This somewhat mimics a real-life coding environment, where feedback is gradually given and received and iterated over. This might explain why the system I created is so reliable, even on more complex tasks that I tested.