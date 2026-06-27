from agent.core import ReActAgent


def test_parse_action_extracts_final_answer_from_lowercase_marker():
    agent = ReActAgent.__new__(ReActAgent)
    llm_output = """
Thought: I should search the documents first.
Action: search_documents
Action Input: {"query": "iva"}
Observation: Found relevant documents.
Final answer: La respuesta final para el cliente.
""".strip()

    tool_name, params, final_answer = agent._parse_action(llm_output)

    assert tool_name is None
    assert params is None
    assert final_answer == "La respuesta final para el cliente."
