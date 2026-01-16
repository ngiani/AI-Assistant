# EVA AI Assistant

A personal AI assistant that intelligently manages your calendar events and emails using advanced language models and Google APIs integration.

## Purpose

EVA is designed to streamline your productivity by providing natural language interaction for:
- **Calendar Management**: Create one-time and recurring events with intelligent date parsing
- **Email Management**: Send emails directly from natural language commands
- **Smart Scheduling**: Understand relative dates like "next Tuesday" or "tomorrow" and convert them to proper calendar entries

The assistant uses an agentic architecture with LangChain and LangGraph to process user commands and execute tools intelligently, making your scheduling and communication effortless.

## The Agent

EVA is built using **LangChain** and **LangGraph**, which enables:
- **Agentic workflow**: The AI agent can decide which tools to use based on user input
- **Tool calling**: Seamlessly integrates with Google Calendar and Gmail APIs
- **In-memory checkpointing**: Maintains conversation state across interactions
- **Error handling**: Gracefully manages tool execution failures

The agent uses **Ollama** for running the language model locally, ensuring privacy and eliminating the need for API keys to external LLM providers.

## Tools & Features Available

### Calendar Tools
- **add_event_to_calendar**: Create single events with customizable reminders
  - Parameters: event name, location, description, start/end times, timezone, email/popup reminders
  - Example: "Add a meeting tomorrow at 3 PM"

- **add_recurrent_event_to_calendar**: Create recurring events (daily, weekly, monthly)
  - Supports complex recurrence rules (e.g., "every Tuesday and Thursday")
  - Example: "Create a weekly standup every Monday at 10 AM"

- **get_calendar_events**: Retrieve upcoming events
  - Useful for checking availability before scheduling

### Email Tools
- **send_email**: Send emails with customizable subject and body
  - Parameters: recipient email, subject, body
  - Example: "Send an email to john@example.com about the project deadline"

### File System Tools
- **list_directory**: Browse files and folders in a directory
  - Example: "List files in my documents folder"

- **read_file**: Read and display file contents
  - Example: "Read my notes from the latest meeting"

- **write_file**: Create or overwrite files with content
  - Example: "Save this document as my_file.txt"

- **delete_file**: Remove files from the system
  - Example: "Delete the old backup file"

**⚠️ Administrator Rights Required**: To access protected system files and directories, EVA must be run with administrator privileges. On Windows, right-click on your terminal/PowerShell and select "Run as administrator" before launching the application.


### Utility Tools
- **get_current_time**: Retrieve the current date and time for accurate scheduling

## Installation Guide

### Prerequisites
- Python 3.8 or higher
- Git
- Administrator access (for Ollama installation on Windows)

### 1. Install Ollama

Ollama allows you to run large language models locally on your machine.

**Windows:**
1. Download the installer from [ollama.ai](https://ollama.ai)
2. Run the installer and follow the setup wizard
3. Ollama will install and start automatically

**macOS:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Pull the Language Model

This project uses **Qwen3:8b**, a lightweight yet powerful language model that offers excellent performance with minimal resource requirements:

```bash
ollama pull qwen3:8b
```

**Why Qwen3:8b**
- **Low weight**: Only 5GB, suitable for most systems
- **Fast inference**: Quick response times for an interactive assistant
- **Strong performance**: Excellent understanding of instructions and context
- **Open source**: No external API dependency

**Note**: You're free to use any other Ollama-supported model. Simply replace `qwen3:8b` with your preferred model (e.g., `neural-chat`, `llama2`, `dolphin-mixtral`) in the `ai_chatbot.py` configuration.

### 3. Clone and Setup the Repository

```bash
# Clone the repository
git clone https://github.com/ngiani/EVA-AI-Assistant.git
cd EVA-AI-Assistant

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Setup Google Authentication

EVA integrates with Google Calendar and Gmail. You need to authorize it:

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (e.g., "EVA Assistant")
   - Enable the following APIs:
     - Google Calendar API
     - Gmail API

2. **Create OAuth 2.0 Credentials:**
   - In the Cloud Console, go to "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Desktop application"
   - Download the credentials as JSON

3. **Add credentials.json:**
   - Place the downloaded `credentials.json` file in the project root directory
   - The app will automatically use it for authentication

4. **Setup Environment Variables:**
   - Create a `.env` file in the project root
   - Add your email address:
     ```
     EMAIL_ADDRESS=your.email@gmail.com
     ```
   - This file is automatically ignored by git to protect your privacy

### 5. Run the Application

```bash
# Make sure Ollama is running
ollama serve

# In another terminal, activate venv and run:
python ai_chatbot.py
```

## Configuration Files

- **credentials.json**: Your Google OAuth credentials (created in setup step 4)
- **.env**: Environment variables including your email address for sending emails (to be added by the user)
- **system_prompt.txt**: System instructions for EVA's behavior
- **requirements.txt**: Python package dependencies

## Google API

The application automatically handles Google API tokens:
- `calendar_token.json`: Auto-generated after first calendar access
- `gmail_token.json`: Auto-generated after first email access

These files are in `.gitignore` to protect your privacy.

## Usage Examples

```
"Add an event called 'Team Meeting' next Tuesday at 2 PM"
"Create a weekly standup every Monday and Wednesday at 10 AM with a 1-day reminder"
"Send an email to alice@example.com with subject 'Project Update' and the latest status"
"What events do I have next week?"
"Remind me about the conference in 3 days"
```

## Project Structure

```
EVA-AI-Assistant/
├── agent.py              # Agent implementation using LangChain
├── tools.py              # Calendar and email tools
├── ai_chatbot.py         # Main chatbot interface
├── system_prompt.txt     # Instructions for the AI agent
├── requirements.txt      # Python dependencies
├── credentials.json      # Google OAuth credentials (user-added)
├── .env                  # Environment variables including EMAIL_ADDRESS (user-added)
└── README.md             # This file
```

## Troubleshooting

**Ollama not connecting:**
- Ensure Ollama is running: `ollama serve`
- Check if port 11434 is accessible

**Google API errors:**
- Delete the token files (`calendar_token.json`, `gmail_token.json`) and re-authenticate
- Ensure `credentials.json` is in the project root

**Email not sending:**
- Verify that the `.env` file exists and contains `EMAIL_ADDRESS=your.email@gmail.com`
- Ensure the email address is authorized in Google account settings

**Model not found:**
- Run `ollama pull <model>` to download the model
- Check available models with `ollama list`

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to fork, modify, and improve EVA for your needs!
