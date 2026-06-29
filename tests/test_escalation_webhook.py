from agent import tools


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


def test_escalate_query_posts_to_webhook_when_configured(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return DummyResponse(status_code=200)

    monkeypatch.setenv("ACCOUNTANT_WEBHOOK_URL", "https://example.test/hook")
    monkeypatch.setenv("ESCALATION_LOG_PATH", str(tmp_path / "escalations.jsonl"))
    monkeypatch.setattr(tools.requests, "post", fake_post)

    result = tools.escalate_query("out_of_scope", "client data")

    assert result["escalated"] is True
    assert result["webhook_sent"] is True
    assert result["queued_locally"] is True
    assert calls[0]["url"] == "https://example.test/hook"
    assert calls[0]["json"]["reason"] == "out_of_scope"
    assert (tmp_path / "escalations.jsonl").exists()
