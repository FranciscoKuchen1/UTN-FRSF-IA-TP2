import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from langfuse import get_client

langfuse = get_client()


class LangfuseLogger:

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.trace_name = "agent_chat"
        self.metadata = {"version": "0.3.0"}
        self._current_observation = None
        self._context_manager = None

    def log_llm_call(self, messages: list[dict]):
        """
        Start a new generation observation for an LLM call.
        Keep the context manager open for log_llm_response.
        """
        self._context_manager = langfuse.start_as_current_observation(
            as_type="generation",
            name="llm_call",
            input=messages,
            model=os.getenv("LLM_MODEL", "qwen/qwen3-32b")
        )
        # Enter the context manager to obtain the observation object
        self._current_observation = self._context_manager.__enter__()

    def log_llm_response(self, response: str):
        if self._current_observation and self._context_manager:
            # Update the output and exit the context manager
            self._current_observation.update(output=response)
            self._context_manager.__exit__(None, None, None)
            self._current_observation = None
            self._context_manager = None

    def log_tool_call(self, tool_name: str, input: dict, output: dict):
        """
        Create and immediately close a span for a tool call.
        Use a context manager with 'with' to ensure it is closed correctly.
        """
        with langfuse.start_as_current_observation(
            as_type="span",
            name=f"tool_{tool_name}",
            input=input,
            output=output
        ) as span:
            span.update(output=output)



# Module-level function used by agent/tools.py (execute_tool).
# Keeps backward compatibility without requiring a LangfuseLogger instance
# in the context of standalone tool functions.
def log_tool_call(tool_name: str, input: dict, output: dict):
    try:
        with langfuse.start_as_current_observation(
            as_type="span",
            name=f"tool_{tool_name}",
            input=input,
            output=output
        ) as span:
            span.update(output=output)
    except Exception as e:
        # Observability should never break agent execution.
        print(f"[WARN] Could not register tool trace in Langfuse: {e}")