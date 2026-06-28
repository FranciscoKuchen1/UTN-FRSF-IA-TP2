import json

import agent.core as core_module
from agent.core import ReActAgent


class FakeLongMemory:
    def __init__(self):
        self.profiles = {}

    def get_profile(self, client_id):
        return self.profiles.get(client_id)

    def update_taxpayer_type(self, client_id, taxpayer_type):
        self.profiles.setdefault(client_id, {})["taxpayer_type"] = taxpayer_type


class NullLogger:
    def log_llm_call(self, messages):
        pass

    def log_llm_response(self, response):
        pass


def make_agent(outputs, tool_executor):
    iterator = iter(outputs)
    return ReActAgent(
        client_id="client-1",
        llm_callable=lambda _messages: next(iterator),
        tool_executor=tool_executor,
        long_memory=FakeLongMemory(),
        logger=NullLogger(),
    )


def test_parse_action_extracts_final_answer_from_lowercase_marker():
    agent = ReActAgent.__new__(ReActAgent)
    output = "Final answer: La respuesta final para el cliente."

    tool_name, params, final_answer = agent._parse_action(output)

    assert tool_name is None
    assert params is None
    assert final_answer == "La respuesta final para el cliente."


def test_parse_action_accepts_direct_answer_and_removes_think_block():
    agent = ReActAgent.__new__(ReActAgent)
    output = "<think>razonamiento privado</think>\nEl vencimiento es el 18/06/2026."

    tool_name, params, final_answer = agent._parse_action(output)

    assert tool_name is None
    assert params is None
    assert final_answer == "El vencimiento es el 18/06/2026."
    assert "razonamiento" not in final_answer


def test_parse_action_decodes_nested_json():
    agent = ReActAgent.__new__(ReActAgent)
    output = (
        "Action: search_documents\n"
        'Action Input: {"query": "IVA", "filters": {"year": 2026}}'
    )

    tool_name, params, final_answer = agent._parse_action(output)

    assert tool_name == "search_documents"
    assert params == {"query": "IVA", "filters": {"year": 2026}}
    assert final_answer is None


def test_chat_runs_react_tool_then_returns_final_answer():
    calls = []

    def tool_executor(name, params):
        calls.append((name, params))
        return json.dumps(
            {
                "taxpayer_type": "responsable_inscripto",
                "month": 6,
                "due_dates": [
                    {"obligation": "Declaracion mensual de IVA", "due_date": "18/06/2026"}
                ],
            }
        )

    agent = make_agent(
        [
            "Action: get_due_dates\n"
            'Action Input: {"taxpayer_type": "responsable_inscripto", "month": 6}',
            "Final Answer: Tu declaracion mensual de IVA vencio el 18/06/2026.",
        ],
        tool_executor,
    )

    answer = agent.chat("Cuando vence mi declaracion de IVA este mes?")

    assert answer == "Tu declaracion mensual de IVA vencio el 18/06/2026."
    assert calls == [
        ("get_due_dates", {"taxpayer_type": "responsable_inscripto", "month": 6})
    ]
    assert agent.long_mem.get_profile("client-1")["taxpayer_type"] == "responsable_inscripto"


def test_chat_stops_after_explicit_escalation():
    calls = []

    def tool_executor(name, params):
        calls.append((name, params))
        return json.dumps(
            {"escalated": True, "message": "Consulta registrada para revision."}
        )

    agent = make_agent(
        [
            "Action: escalate_query\n"
            'Action Input: {"reason": "requiere criterio profesional", "client_data": "caso"}'
        ],
        tool_executor,
    )

    answer = agent.chat("Analiza mi caso particular")

    assert answer == "Consulta registrada para revision."
    assert len(calls) == 1
    assert calls[0][0] == "escalate_query"


def test_chat_escalates_after_invalid_model_format(monkeypatch):
    monkeypatch.setattr(core_module, "MAX_ITER", 2)
    calls = []

    def tool_executor(name, params):
        calls.append((name, params))
        return json.dumps({"message": "Consulta registrada para revision."})

    agent = make_agent(
        ["Thought: sigo pensando", "<think>sin respuesta final</think>"],
        tool_executor,
    )

    answer = agent.chat("consulta")

    assert answer == "Consulta registrada para revision."
    assert calls[0][0] == "escalate_query"
    assert calls[0][1]["reason"] == "invalid_llm_format"


def test_chat_escalates_when_llm_fails():
    calls = []

    def failing_llm(_messages):
        raise RuntimeError("provider unavailable")

    def tool_executor(name, params):
        calls.append((name, params))
        return json.dumps({"message": "Consulta registrada para revision."})

    agent = ReActAgent(
        client_id="client-1",
        llm_callable=failing_llm,
        tool_executor=tool_executor,
        long_memory=FakeLongMemory(),
        logger=NullLogger(),
    )

    answer = agent.chat("consulta")

    assert answer == "Consulta registrada para revision."
    assert calls[0][0] == "escalate_query"
    assert calls[0][1]["reason"].startswith("llm_error:")
