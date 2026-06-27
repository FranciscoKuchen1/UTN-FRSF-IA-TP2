import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from agent.tools import TOOLS_SCHEMA, ejecutar_tool
from agent.memory import ShortTermMemory, LongTermMemory
from agent.prompts import SYSTEM_PROMPT
from observability.logger import LangfuseLogger

import groq
from groq import AuthenticationError, PermissionDeniedError, RateLimitError

groq_client = groq.Client(api_key=os.getenv("GROQ_API_KEY"))
LLM_MODEL = os.getenv("LLM_MODEL") or "qwen/qwen3-32b"

MAX_ITER = int(os.getenv("MAX_REACT_ITERATIONS", 5))


class ReActAgent:

    def __init__(self, cliente_id: str = "anonimo"):
        self.cliente_id = cliente_id
        self.short_mem = ShortTermMemory()
        self.long_mem = LongTermMemory()
        self.logger = LangfuseLogger(session_id=cliente_id)

    def _build_system(self) -> str:
        perfil = self.long_mem.obtener_perfil(self.cliente_id) or {}
        return SYSTEM_PROMPT.format(
            tipo_contribuyente=perfil.get("tipo_contribuyente", "no informado"),
            fecha_actual=datetime.now().strftime("%d/%m/%Y")
        )

    def _call_llm(self, messages: list[dict]) -> str:
        """Llama al LLM (Groq) y retorna el texto generado."""
        self.logger.log_llm_call(messages)

        try:
            response = groq_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in messages
                ],
                max_tokens=1024,
                temperature=0.2,
                stop=["Final Answer:"]
            )
            choice = response.choices[0] if getattr(response, "choices", None) else None
            text = ""
            if choice is not None and getattr(choice, "message", None) is not None:
                text = getattr(choice.message, "content", "")
            text = text or ""

            self.logger.log_llm_response(text)
            return text
        except RateLimitError:
            raise RuntimeError(
                "Los créditos o cuota de la API de Groq se han agotado. "
                "Verifica tu cuenta y el uso en el portal de Groq."
            )
        except AuthenticationError:
            raise RuntimeError("Credenciales inválidas de Groq. Verifica GROQ_API_KEY.")
        except PermissionDeniedError:
            raise RuntimeError("Permisos insuficientes en la API de Groq.")
        except Exception as e:
            raise RuntimeError(f"Error de API Groq: {e}")

    def _parse_action(self, llm_output: str) -> tuple[str | None, dict | None, str | None]:
        """
        Extrae Action y Action Input del output del LLM.
        Retorna (tool_name, params, final_answer)
        """
        # Detectar respuesta final
        final_match = re.search(r"Final Answer:\s*(.+)", llm_output, re.DOTALL)
        if final_match:
            return None, None, final_match.group(1).strip()

        # Detectar action
        action_match = re.search(r"Action:\s*(\w+)", llm_output)
        input_match = re.search(r"Action Input:\s*(\{.+?\})", llm_output, re.DOTALL)

        if action_match and input_match:
            tool_name = action_match.group(1).strip()
            try:
                params = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                params = {}
            return tool_name, params, None

        # Si el LLM no siguió el formato, forzar respuesta final
        return None, None, llm_output.strip()

    def chat(self, user_message: str) -> str:
        """Punto de entrada principal. Ejecuta el loop ReAct y devuelve la respuesta."""

        # Agregar mensaje del usuario al historial
        self.short_mem.add("user", user_message)

        # Armar contexto completo
        system = self._build_system()
        tools_desc = json.dumps(TOOLS_SCHEMA, ensure_ascii=False, indent=2)

        # Construir lista de mensajes para el LLM
        messages = [
            {"role": "system", "content": f"{system}\n\nHerramientas disponibles (JSON Schema):\n{tools_desc}"},
            *self.short_mem.get_history()
        ]

        final_answer = None
        scratchpad = ""  # acumula el razonamiento de esta vuelta

        for iteration in range(MAX_ITER):
            # Si hay scratchpad de iteraciones anteriores, agregarlo
            if scratchpad:
                messages_with_scratch = messages[:-1] + [
                    {"role": "assistant", "content": scratchpad},
                    messages[-1]
                ]
            else:
                messages_with_scratch = messages

            llm_output = self._call_llm(messages_with_scratch)
            scratchpad += llm_output + "\n"

            tool_name, params, answer = self._parse_action(llm_output)

            if answer:
                # El LLM llegó a una respuesta final
                final_answer = answer
                break

            if tool_name:
                # Ejecutar la tool
                observation = ejecutar_tool(tool_name, params or {})
                scratchpad += f"Observation: {observation}\n"

                # Detectar si el cliente mencionó su tipo de contribuyente
                self._extract_and_save_profile(user_message, observation)

        # Fallback si se agotaron las iteraciones
        if not final_answer:
            if scratchpad:
                final_answer = "No pude completar tu consulta automáticamente. La derivé al contador para que te contacte."
                ejecutar_tool("escalar_consulta", {
                    "motivo": "timeout_react_loop",
                    "datos_cliente": user_message
                })
            else:
                final_answer = "Ocurrió un error inesperado. Por favor, intentá de nuevo."

        # Guardar respuesta en historial
        self.short_mem.add("assistant", final_answer)
        return final_answer

    def _extract_and_save_profile(self, user_msg: str, observation: str):
        """Detecta menciones de tipo de contribuyente y lo guarda en memoria persistente."""
        msg_lower = user_msg.lower()
        if "monotributo" in msg_lower:
            self.long_mem.actualizar_tipo_contribuyente(self.cliente_id, "monotributo")
        elif "responsable inscripto" in msg_lower or "iva" in msg_lower:
            self.long_mem.actualizar_tipo_contribuyente(self.cliente_id, "responsable_inscripto")
