import os
from dotenv import load_dotenv
load_dotenv()

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
        Inicia una nueva observación de tipo generation (llamada a LLM).
        Mantiene el context manager abierto para log_llm_response.
        """
        self._context_manager = langfuse.start_as_current_observation(
            as_type="generation",
            name="llm_call",
            input=messages,
            model=os.getenv("LLM_MODEL", "gemini-2.0-flash")
        )
        # Entrar al context manager para obtener el objeto observación
        self._current_observation = self._context_manager.__enter__()

    def log_llm_response(self, response: str):
        if self._current_observation and self._context_manager:
            # Actualizar output y salir del context manager
            self._current_observation.update(output=response)
            self._context_manager.__exit__(None, None, None)
            self._current_observation = None
            self._context_manager = None

    def log_tool_call(self, tool_name: str, input: dict, output: dict):
        """
        Crea y cierra inmediatamente un span para la llamada a una herramienta.
        Usa context manager con 'with' para asegurar cierre correcto.
        """
        with langfuse.start_as_current_observation(
            as_type="span",
            name=f"tool_{tool_name}",
            input=input,
            output=output
        ) as span:
            span.update(output=output)



# Función a nivel de módulo usada por agent/tools.py (ejecutar_tool).
# Mantiene retrocompatibilidad sin requerir una instancia de LangfuseLogger
# en el contexto de las funciones de tools, que son funciones sueltas.
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
        # La observabilidad nunca debe romper la ejecución del agente.
        print(f"[WARN] No se pudo registrar traza de tool en Langfuse: {e}")
