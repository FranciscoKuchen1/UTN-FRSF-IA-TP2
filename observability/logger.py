import os
from langfuse import Langfuse

langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

class LangfuseLogger:
    
    def __init__(self, session_id: str):
        self.trace = langfuse.trace(
            name="agent_chat",
            session_id=session_id,
            metadata={"version": "0.2.0"}
        )
        self._current_span = None
    
    def log_llm_call(self, messages: list[dict]):
        self._current_span = self.trace.generation(
            name="llm_call",
            input=messages,
            model="gemini-2.0-flash"
        )
    
    def log_llm_response(self, response: str):
        if self._current_span:
            self._current_span.end(output=response)
    
    def log_tool_call(self, tool_name: str, input: dict, output: dict):
        self.trace.span(
            name=f"tool_{tool_name}",
            input=input,
            output=output
        )
