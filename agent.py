import time
import uuid

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
import os
from langchain.agents.middleware import wrap_tool_call
from langgraph.checkpoint.memory import InMemorySaver 
from functools import partial

from langchain.messages import ToolMessage,AIMessage,HumanMessage
from langchain.messages import AIMessageChunk


class Agent():
    
    def __init__(self, model, tools, system_prompt):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0,
            top_p=0.7,           # Nucleus sampling: lower = faster & more focused
            top_k=40,            # Limit to top 40 tokens: reduces computation
        )
        self.tools = tools
        self.agent = create_agent(model=self.llm, 
                                  tools=tools, 
                                  system_prompt=system_prompt, 
                                  checkpointer=InMemorySaver(),
                                  middleware=[self.handle_tool_errors])
        
    def invoke(self, user_input):
        
                
        response = self.agent.invoke({"messages": [HumanMessage(content=user_input)]},
                                     {"configurable": {"thread_id": str(uuid.uuid4())}})
        
        return response
    
    def stream_invoke(self, user_input):
                
        for token in self.agent.stream({"messages": [HumanMessage(content=user_input)]}, 
                                        {"configurable": {"thread_id": str(uuid.uuid4())}}, 
                                        stream_mode="messages"):
            yield token
            
            
    def stream_llm_benchmark(self, user_input):
        start = time.time()

        for chunk in self.llm.stream(user_input):
            print(chunk)

        print(time.time() - start)
            
    def get_ai_message_token(self, token):
        if (isinstance(token[0], AIMessageChunk)):
            return token[0].content
            
    def get_ai_message(self, response):
        
        for message in response['messages']:
            if isinstance(message, AIMessage):
                if message.content != "":
                    return message.content
        return ""
    
    def get_tool_message(self, response):
        for message in response['messages']:
            if isinstance(message, ToolMessage):
                if message.content != "":
                    return message.content
        return ""
    
    
    def get_human_message(self, response):
        for message in response['messages']:
            if isinstance(message, HumanMessage):
                if message.content != "":
                    return message.content
        return ""
    
    
    #Handle tool errors
    @wrap_tool_call
    def handle_tool_errors(request, handler):
        try:
            return handler(request)
        except Exception as e:
            # Handle both dict and object formats for tool_call
            tool_call_id = request.tool_call.id if hasattr(request.tool_call, 'id') else request.tool_call['id']
            return ToolMessage(content=f"An error occurred while executing the tool: {str(e)}", tool_call_id=tool_call_id)