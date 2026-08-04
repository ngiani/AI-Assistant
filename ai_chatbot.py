from agent import Agent
from tools import CalendarTools, MailTools, TimeTools, FileSystemTools
import os
import uuid

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
    # Longer ping timeout so slow (blocking) agent responses don't get treated as a dead connection
    async with serve(handler, "", port, ping_interval=30, ping_timeout=120) as server:
        await server.serve_forever()
        
async def handler(websocket):
    # One thread_id per connection so the agent keeps conversation history across turns
    # (e.g. remembers the event being discussed when the user replies to a follow-up question).
    thread_id = str(uuid.uuid4())

    #Chat loop
    while True:

        try:
            question = await websocket.recv()

        except ConnectionClosedOK:
            break
        
        print(f"User: {question}")

        print(f"{name}:")

        # Run the blocking generation in a thread so the event loop stays free to answer keepalive pings
        try:
            complete_answer = await asyncio.to_thread(_collect_agent_response, question, thread_id)
        except Exception as e:
            # Don't let a single failed turn (bad tool call, parse error, etc.) kill the whole connection
            print(f"Error while generating response: {e}")
            complete_answer = "Sorry, something went wrong while processing that request. Please try again."

        await websocket.send(complete_answer)


def _collect_agent_response(question, thread_id):
    complete_answer = ""
    for token in agent.stream_invoke(question, thread_id=thread_id):
        message_token = agent.get_ai_message_token(token)
        if message_token is not None:
            complete_answer += message_token
    return complete_answer
        

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

        
