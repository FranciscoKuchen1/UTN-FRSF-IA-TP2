import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from agent.tools import TOOLS_SCHEMA, execute_tool
from agent.memory import ShortTermMemory, LongTermMemory
from agent.prompts import SYSTEM_PROMPT
from observability.logger import LangfuseLogger

import groq
from groq import AuthenticationError, PermissionDeniedError, RateLimitError

groq_client = groq.Client(api_key=os.getenv("GROQ_API_KEY"))
LLM_MODEL = os.getenv("LLM_MODEL") or "qwen/qwen3-32b"

MAX_ITER = int(os.getenv("MAX_REACT_ITERATIONS", 5))


class ReActAgent:

    def __init__(self, client_id: str = "anonymous"):
        self.client_id = client_id
        self.short_mem = ShortTermMemory()
        self.long_mem = LongTermMemory()
        self.logger = LangfuseLogger(session_id=client_id)

    def _build_system(self) -> str:
        profile = self.long_mem.get_profile(self.client_id) or {}
        return SYSTEM_PROMPT.format(
            taxpayer_type=profile.get("taxpayer_type", "not provided"),
            current_date=datetime.now().strftime("%d/%m/%Y"),
        )

    def _call_llm(self, messages: list[dict]) -> str:
        """Call the LLM (Groq) and return the generated text."""
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
                "Groq API rate limit exceeded or credits depleted. Check your Groq account."
            )
        except AuthenticationError:
            raise RuntimeError("Invalid Groq credentials. Check GROQ_API_KEY.")
        except PermissionDeniedError:
            raise RuntimeError("Insufficient permissions for Groq API.")
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")

    def _parse_action(self, llm_output: str) -> tuple[str | None, dict | None, str | None]:
        """
        Extract Action and Action Input from the LLM output.
        Returns (tool_name, params, final_answer).
        """
        # Detect final answer (case-insensitive)
        final_match = re.search(r"final answer:\s*(.+)", llm_output, re.IGNORECASE | re.DOTALL)
        if final_match:
            return None, None, final_match.group(1).strip()

        # Detect action
        action_match = re.search(r"action:\s*(\w+)", llm_output, re.IGNORECASE)
        input_match = re.search(r"action input:\s*(\{.+?\})", llm_output, re.IGNORECASE | re.DOTALL)

        if action_match and input_match:
            tool_name = action_match.group(1).strip()
            try:
                params = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                params = {}
            return tool_name, params, None

        # If the LLM did not follow the expected format, do not expose the raw reasoning as a user answer.
        return None, None, None

    def chat(self, user_message: str) -> str:
        """Main entry point. Runs the ReAct loop and returns the response."""

        # Add the user message to the history
        self.short_mem.add("user", user_message)

        # Build the full context
        system = self._build_system()
        tools_desc = json.dumps(TOOLS_SCHEMA, ensure_ascii=False, indent=2)

        # Build message list for the LLM
        messages = [
            {"role": "system", "content": f"{system}\n\nAvailable tools (JSON Schema):\n{tools_desc}"},
            *self.short_mem.get_history(),
        ]

        final_answer = None
        scratchpad = ""  # accumulates the reasoning for this turn

        for iteration in range(MAX_ITER):
            # If there is scratchpad from previous iterations, append it
            if scratchpad:
                messages_with_scratch = messages[:-1] + [
                    {"role": "assistant", "content": scratchpad},
                    messages[-1]
                ]
            else:
                messages_with_scratch = messages

            llm_output = self._call_llm(messages_with_scratch)
            print(f"[REACT][iteration {iteration + 1}] {llm_output.strip()}")
            scratchpad += llm_output + "\n"

            tool_name, params, answer = self._parse_action(llm_output)

            if answer:
                # The LLM produced a final answer
                final_answer = answer
                break

            if tool_name:
                # Execute the tool
                observation = execute_tool(tool_name, params or {})
                print(f"[REACT][observation] {observation}")
                scratchpad += f"Observation: {observation}\n"

                # Detect and save taxpayer type if mentioned
                self._extract_and_save_profile(user_message, observation)

        # Fallback if iterations are exhausted
        if not final_answer:
            if scratchpad:
                final_answer = "No pude completar tu consulta automáticamente. La derivé al contador."
                execute_tool("escalate_query", {"reason": "timeout_react_loop", "client_data": user_message})
            else:
                final_answer = "Ocurrió un error inesperado. Intentá nuevamente."

        # Save the answer in history
        self.short_mem.add("assistant", final_answer)
        return final_answer

    def _extract_and_save_profile(self, user_msg: str, observation: str):
        """Detect mentions of taxpayer type in the user message and save to long-term memory."""
        msg_lower = user_msg.lower()
        if "monotributo" in msg_lower:
            self.long_mem.update_taxpayer_type(self.client_id, "monotributo")
        elif "responsable inscripto" in msg_lower or "iva" in msg_lower:
            self.long_mem.update_taxpayer_type(self.client_id, "responsable_inscripto")
