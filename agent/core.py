import json
import os
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
    override=True,
)

import groq
from groq import AuthenticationError, PermissionDeniedError, RateLimitError

from agent.memory import LongTermMemory, ShortTermMemory
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOLS_SCHEMA, execute_tool
from observability.logger import LangfuseLogger


LLM_MODEL = os.getenv("LLM_MODEL") or "qwen/qwen3-32b"
MAX_ITER = int(os.getenv("MAX_REACT_ITERATIONS", "5"))

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_PROTOCOL_ONLY_RE = re.compile(
    r"^\s*(?:thought|observation)\s*:", re.IGNORECASE
)


class ReActAgent:
    """ReAct agent with textual tool calls and a safe escalation fallback."""

    def __init__(
        self,
        client_id: str = "anonymous",
        *,
        taxpayer_type: str | None = None,
        llm_callable: Callable[[list[dict]], str] | None = None,
        tool_executor: Callable[[str, dict], str] = execute_tool,
        short_memory: ShortTermMemory | None = None,
        long_memory: LongTermMemory | None = None,
        logger: LangfuseLogger | None = None,
    ):
        self.client_id = client_id
        self.short_mem = short_memory or ShortTermMemory()
        self.long_mem = long_memory or LongTermMemory()
        self.logger = logger or LangfuseLogger(session_id=client_id)
        self._llm_callable = llm_callable
        self._tool_executor = tool_executor
        self._groq_client = None

        if taxpayer_type:
            self.long_mem.update_taxpayer_type(client_id, taxpayer_type)

    def _get_groq_client(self):
        if self._groq_client is not None:
            return self._groq_client

        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY no esta configurada.")

        self._groq_client = groq.Client(api_key=api_key)
        return self._groq_client

    def _build_system(self) -> str:
        profile = self.long_mem.get_profile(self.client_id) or {}
        return SYSTEM_PROMPT.format(
            taxpayer_type=profile.get("taxpayer_type", "no informado"),
            current_date=datetime.now().strftime("%d/%m/%Y"),
        )

    def _call_llm(self, messages: list[dict]) -> str:
        """Call the configured LLM and return its textual ReAct output."""
        self.logger.log_llm_call(messages)

        try:
            if self._llm_callable is not None:
                text = self._llm_callable(messages) or ""
            else:
                response = self._get_groq_client().chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.2,
                )
                choice = response.choices[0] if response.choices else None
                text = (
                    getattr(getattr(choice, "message", None), "content", "")
                    if choice is not None
                    else ""
                )
                text = text or ""

            self.logger.log_llm_response(text)
            return text
        except RateLimitError as exc:
            raise RuntimeError(
                "La API de Groq alcanzo su limite de uso o no tiene creditos disponibles."
            ) from exc
        except AuthenticationError as exc:
            raise RuntimeError("Las credenciales de Groq no son validas.") from exc
        except PermissionDeniedError as exc:
            raise RuntimeError("La API de Groq rechazo la solicitud por permisos.") from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Error al consultar Groq: {exc}") from exc

    @staticmethod
    def _visible_output(llm_output: str) -> str:
        """Remove model reasoning blocks so they are never returned to the user."""
        visible = _THINK_BLOCK_RE.sub("", llm_output or "")
        if re.search(r"<think>", visible, re.IGNORECASE):
            visible = re.split(r"<think>", visible, maxsplit=1, flags=re.IGNORECASE)[0]
        return visible.strip()

    @staticmethod
    def _decode_action_input(text: str) -> dict | None:
        input_match = re.search(r"action input\s*:\s*", text, re.IGNORECASE)
        if not input_match:
            return None

        raw_params = text[input_match.end():].lstrip()
        try:
            params, _ = json.JSONDecoder().raw_decode(raw_params)
        except json.JSONDecodeError:
            return None
        return params if isinstance(params, dict) else None

    def _parse_action(
        self, llm_output: str
    ) -> tuple[str | None, dict | None, str | None]:
        """Parse a tool action or a user-facing final answer from model output."""
        visible = self._visible_output(llm_output)
        if not visible:
            return None, None, None

        final_match = re.search(
            r"final answer\s*:\s*(.+)", visible, re.IGNORECASE | re.DOTALL
        )
        if final_match:
            answer = final_match.group(1).strip()
            return (None, None, answer) if answer else (None, None, None)

        action_match = re.search(
            r"(?:^|\n)\s*action\s*:\s*([A-Za-z_]\w*)",
            visible,
            re.IGNORECASE,
        )
        if action_match:
            params = self._decode_action_input(visible)
            if params is None:
                return None, None, None
            return action_match.group(1), params, None

        # Some models answer directly even when a protocol marker was requested.
        # Accept that answer, but never expose a raw Thought/Observation block.
        if not _PROTOCOL_ONLY_RE.match(visible):
            return None, None, visible

        return None, None, None

    @staticmethod
    def _decode_tool_result(raw_result: Any) -> dict:
        if isinstance(raw_result, dict):
            return raw_result
        if isinstance(raw_result, str):
            try:
                parsed = json.loads(raw_result)
                return parsed if isinstance(parsed, dict) else {"result": parsed}
            except json.JSONDecodeError:
                return {"result": raw_result}
        return {"result": raw_result}

    def _execute_tool_safely(self, name: str, params: dict) -> str:
        try:
            result = self._tool_executor(name, params)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            return json.dumps(
                {
                    "error": f"La herramienta {name} no pudo ejecutarse.",
                    "error_type": type(exc).__name__,
                },
                ensure_ascii=False,
            )

    def _escalate(self, reason: str, user_message: str) -> str:
        result = self._execute_tool_safely(
            "escalate_query",
            {"reason": reason, "client_data": user_message},
        )
        payload = self._decode_tool_result(result)
        return payload.get("message") or (
            "No pude completar tu consulta automaticamente. "
            "Por favor, comunicate con el estudio contable."
        )

    def chat(self, user_message: str) -> str:
        """Run the ReAct loop and return one safe, user-facing response."""
        user_message = (user_message or "").strip()
        if not user_message:
            return "Escribi una consulta para que pueda ayudarte."

        self._extract_and_save_profile(user_message)
        self.short_mem.add("user", user_message)

        tools_desc = json.dumps(TOOLS_SCHEMA, ensure_ascii=False, indent=2)
        messages = [
            {
                "role": "system",
                "content": f"{self._build_system()}\n\nHerramientas (JSON Schema):\n{tools_desc}",
            },
            *self.short_mem.get_history(),
        ]

        final_answer = None
        had_progress = False

        for iteration in range(MAX_ITER):
            try:
                llm_output = self._call_llm(messages)
            except RuntimeError as exc:
                final_answer = self._escalate(
                    f"llm_error:{type(exc).__name__}", user_message
                )
                break

            print(f"[REACT][iteration {iteration + 1}] {llm_output.strip()}")
            tool_name, params, answer = self._parse_action(llm_output)

            if answer:
                final_answer = answer
                break

            if tool_name:
                had_progress = True
                observation = self._execute_tool_safely(tool_name, params or {})
                print(f"[REACT][observation] {observation}")

                if tool_name == "escalate_query":
                    payload = self._decode_tool_result(observation)
                    final_answer = payload.get("message") or (
                        "La consulta fue derivada para revision profesional."
                    )
                    break

                action_text = self._visible_output(llm_output)
                messages.extend(
                    [
                        {"role": "assistant", "content": action_text},
                        {
                            "role": "user",
                            "content": (
                                f"Observation: {observation}\n"
                                "Continua el ciclo ReAct. Usa otra herramienta o responde "
                                "con 'Final Answer:'."
                            ),
                        },
                    ]
                )
                continue

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "La salida anterior no respeto el protocolo. Responde unicamente con "
                        "'Action:' y 'Action Input:' o con 'Final Answer:'."
                    ),
                }
            )

        if not final_answer:
            reason = "react_loop_exhausted" if had_progress else "invalid_llm_format"
            final_answer = self._escalate(reason, user_message)

        self.short_mem.add("assistant", final_answer)
        return final_answer

    def _extract_and_save_profile(self, user_msg: str):
        """Persist an explicitly stated or unambiguous taxpayer type."""
        msg_lower = user_msg.lower()
        taxpayer_type = None

        if "monotribut" in msg_lower:
            taxpayer_type = "monotributo"
        elif "responsable inscripto" in msg_lower:
            taxpayer_type = "responsable_inscripto"
        elif "empleado en relacion de dependencia" in msg_lower:
            taxpayer_type = "empleado_relacion_dependencia"
        elif re.search(r"\b(?:declaracion|declaraci[oó]n)\s+(?:mensual\s+)?de\s+iva\b", msg_lower):
            taxpayer_type = "responsable_inscripto"

        if taxpayer_type:
            self.long_mem.update_taxpayer_type(self.client_id, taxpayer_type)
