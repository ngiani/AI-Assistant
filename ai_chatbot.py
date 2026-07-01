from agent import Agent
from tools import CalendarTools, MailTools, TimeTools, FileSystemTools
import os

import asyncio
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosedOK

import time

name = "Eva"
port = 8081
agent = None

def load_system_prompt():
    """Load system prompt from separate file."""
    prompt_file = os.path.join(os.path.dirname(__file__), 'system_prompt.txt')
    try:
        with open(prompt_file, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: system_prompt.txt not found at {prompt_file}")
        return f"You are a helpful assistant called {name} that can manage calendar events, send emails, and handle file system operations."


async def main():
    async with serve(handler, "", port) as server:
        await server.serve_forever()
        
async def handler(websocket):
    #Chat loop
    while True:

        try:
            question = await websocket.recv()

        except ConnectionClosedOK:
            break
        
        print(f"User: {question}")

        print(f"{name}:")
        
        complete_answer= ""

        for token in agent.stream_invoke(question):
            
            message_token = agent.get_ai_message_token(token)

            if message_token is not None:
                complete_answer += message_token
    

        websocket.send(complete_answer)
        

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
    print(f"{name} listening on {port}:")
    
    #Async message loop
    asyncio.run(main())

        
