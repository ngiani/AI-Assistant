import time
import uuid

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
import ollama
import os
from langchain.agents.middleware import wrap_tool_call
from langgraph.checkpoint.memory import InMemorySaver 
from functools import partial

from langchain.messages import ToolMessage,AIMessage,HumanMessage
from langchain.messages import AIMessageChunk


class Agent():
    
    def __init__(self, model, tools, system_prompt):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.ollama_client = ollama.Client(host=base_url)
        self._ensure_model_available(model)

        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0,
            top_p=0.2,           # Nucleus sampling: lower = faster & more focused
            top_k=40,            # Limit to top 40 tokens: reduces computation
            num_ctx=4096,        # Trimmed system prompt + tool docstrings now use ~1.7k tokens, leaving plenty of headroom
            keep_alive=-1,       # Keep the model resident in GPU memory, avoids paying the ~2min reload cost again
            repeat_penalty=1.15, # Greedy decoding (temp=0) with no repeat penalty can loop forever generating the same tokens
            num_predict=1024,    # Hard cap on output length so a runaway generation can't hang the request indefinitely
            reasoning=False,     # Qwen3 is a hybrid thinking model; its <think> reasoning was never terminating and
                                 # ate the whole num_predict budget with nothing surfaced in content/tool_calls
        )
        self.tools = tools
        self.agent = create_agent(model=self.llm, 
                                  tools=tools, 
                                  system_prompt=system_prompt, 
                                  checkpointer=InMemorySaver(),
                                  middleware=[self.handle_tool_errors])
        self._warm_up()

    def _warm_up(self):
        """Force Ollama to load the model into GPU memory now, so the first user message isn't stuck behind a ~2min load."""
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                print(f"Warming up model... (attempt {attempt}/{attempts})")
                self.llm.invoke("Hi")
                print("Model warmed up and ready.")
                return
            except Exception as e:
                print(f"Warm-up attempt {attempt}/{attempts} failed: {e}")
                if attempt < attempts:
                    time.sleep(5)
        print("Warm-up failed after all retries (will load on first request instead).")

    def _ensure_model_available(self, model: str):
        auto_pull = os.getenv("OLLAMA_AUTO_PULL_MODEL", "true").lower() in ("1", "true", "yes")

        try:
            installed = self.ollama_client.list()
            installed_models = {
                item.model for item in getattr(installed, "models", []) if getattr(item, "model", None)
            }

            if model in installed_models:
                print(f"Model '{model}' already available in Ollama.")
                return

            if not auto_pull:
                raise RuntimeError(
                    f"Model '{model}' is missing from Ollama. Set OLLAMA_AUTO_PULL_MODEL=true or pre-pull the model manually."
                )

            print(f"Model '{model}' not present in Ollama. Pulling...")
            result = self.ollama_client.pull(model, stream=True)

            if hasattr(result, "__iter__"):
                for progress in result:
                    if hasattr(progress, "message") and progress.message:
                        print(progress.message)

            print(f"Model '{model}' successfully pulled.")

            installed = self.ollama_client.list()
            installed_models = {
                item.model for item in getattr(installed, "models", []) if getattr(item, "model", None)
            }
            if model not in installed_models:
                raise RuntimeError(f"Model '{model}' did not appear in Ollama after pull.")
        except Exception as e:
            raise RuntimeError(f"Failed to verify or pull Ollama model '{model}': {e}") from e
        
    def invoke(self, user_input, thread_id=None):
        
        thread_id = thread_id or str(uuid.uuid4())
        response = self.agent.invoke({"messages": [HumanMessage(content=user_input)]},
                                     {"configurable": {"thread_id": thread_id}})
        
        return response
    
    def stream_invoke(self, user_input, thread_id=None):
        # Reuse the same thread_id across a conversation (e.g. one per websocket connection) so the
        # checkpointer keeps prior turns in context; otherwise every call starts a blank, isolated conversation.
        thread_id = thread_id or str(uuid.uuid4())
        for token in self.agent.stream({"messages": [HumanMessage(content=user_input)]}, 
                                        {"configurable": {"thread_id": thread_id}}, 
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