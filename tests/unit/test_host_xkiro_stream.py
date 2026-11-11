"""Hosted provider response behavior."""

from __future__ import annotations

import json
from pathlib import Path
import sys

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


def test_xkiro_rate_limit_reports_unavailable_provider(monkeypatch):
    import engine as hosted_engine
    from engine import answer

    class RateLimitedResponse:
        status_code = 429

        def close(self):
            pass

    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, payload=kwargs["json"])
        return RateLimitedResponse()

    monkeypatch.setenv("XKIRO_API_KEY", "configured-test-key")
    monkeypatch.setattr(answer, "fallback_config", lambda _current: None)
    monkeypatch.setattr(hosted_engine.requests, "post", fake_post)
    instance = hosted_engine.Engine.__new__(hosted_engine.Engine)
    instance.answer = lambda query: {
        "route": "GRAPH_SYNTHESIS",
        "text": "Grounded fallback with [citation].",
        "payload": {"anchor_concept": {"id": "graph_retrieval"}, "logs": []},
    }

    chunks = list(instance.stream_chat("explain graph retrieval"))
    metadata = json.loads(chunks[0].split("\n[STREAM_START]\n", 1)[0])

    assert captured["payload"]["max_tokens"] == 700
    assert "Answer the student's question directly" in captured["payload"]["messages"][0]["content"]
    evidence = json.loads(captured["payload"]["messages"][1]["content"])
    assert evidence["question"] == "explain graph retrieval"
    assert metadata["model"]["provider"] == "unavailable"
    assert "retry" in chunks[-1].lower()
