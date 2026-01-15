from agent import Agent
from tools import CalendarTools, MailTools, TimeTools, FileSystemTools
import os



def load_system_prompt():
    """Load system prompt from separate file."""
    prompt_file = os.path.join(os.path.dirname(__file__), 'system_prompt.txt')
    try:
        with open(prompt_file, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: system_prompt.txt not found at {prompt_file}")
        return "You are a helpful assistant called Eva that can manage calendar events, send emails, and handle file system operations."

if __name__ == "__main__":
    
    calendar_tools = CalendarTools()
    mail_tools  = MailTools()
    time_tools = TimeTools()
    file_system_tools = FileSystemTools()
    
    # Load system prompt from file
    system_prompt = load_system_prompt()
    
    agent = Agent(model="qwen3:8b", 
                  tools=calendar_tools.get_tools() + mail_tools.get_tools() + time_tools.get_tools() + file_system_tools.get_tools(),
                  system_prompt=system_prompt)
    #Welcome message
    print("EVA: ")
    for token in agent.stream_invoke("Hi ! Introduce yourself briefly. Specify i need to say 'bye' to end the chat."):
        print(agent.get_ai_message_token(token), end='', flush=True)
        
    print("\n")
    
    #Chat loop
    while True:

        print("You: ")
        question = input()

        if question.lower() == "bye":
            break

        print ("\n")
        print("EVA: ")
        
        for token in agent.stream_invoke(question):
            message_token = agent.get_ai_message_token(token)
            if (message_token is not None):
                print(message_token, end='', flush=True)
        print("\n")