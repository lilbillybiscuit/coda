# (CPSC 429/529) CODA - Autonomous Coding Assistant

This repository offers an example for building **CODA**, an agentic system that autonomously generates, modifies, and executes code based on user-defined tasks. This example provides a starting point, but we highly encourage you to explore your own design and prompt while adhering to the assignment specifications.

## Project Overview

CODA transforms passive interactions with AI into active collaboration by enabling autonomous control within your development environment. Core features include:

- **Input Handling**: Accepts a task description and a working directory path.
- **Function Calling**: Uses OpenAI's API to generate shell scripts that perform the desired tasks.
- **Execution**: Runs the generated shell scripts and collects execution logs.
- **Feedback Loop**: Analyzes the execution logs to determine success and handles errors accordingly.


## Prerequisites

Ensure the following are installed:

- **Python** (Version 3.10 or higher)
- **OpenAI Python SDK** (`openai` package)
- **OpenAI API Key**

## Installation Guide

1. **Clone the Repository**
   ```bash
   git clone https://github.com/ingim/coda.git
   ```

2. **Change to the CODA Directory**
   ```bash
   cd coda
   ```

3. **Install Required Packages**
   ```bash
   pip install openai
   ```

4. **Configure the OpenAI API Key**
   - Edit `coda.py` to include your API key, replacing `'api_key'` with your actual key.
   - Alternatively, set it as an environment variable:
     ```bash
     export OPENAI_API_KEY='your-api-key'
     ```

## Using CODA

1. **Run CODA**:
   ```bash
   python main.py
   ```

2. **Define Your Task**:
   - Enter a brief description of the code or function you want CODA to create.
   - Specify the working directory where generated files should be saved.

3. **Generated Scripts and Execution Logs**:
   - CODA will display the shell script it generates, followed by real-time logs for each execution.

4. **Feedback Loop**:
   - Upon successful completion, you can define additional tasks or exit.
   - For errors, CODA analyzes the issue and revises the task description as needed.