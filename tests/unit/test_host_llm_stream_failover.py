"""Verify the hosted chat stream changes providers after an empty response."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine import answer, llm  # noqa: E402

pytestmark = pytest.mark.unit


def test_stream_tries_nvidia_when_xkiro_returns_no_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty primary stream must not silently become a grounded answer."""
    engine = answer.Engine.__new__(answer.Engine)
    monkeypatch.setattr(
        engine,
        "answer",
        lambda _query: {
            "route": "GRAPH_SYNTHESIS",
            "text": "Grounded draft.",
            "payload": {"logs": []},
        },
    )
    primary = {"provider": "xkiro", "model": "first"}
    fallback = {"provider": "nvidia", "model": "second"}
    attempted: list[str] = []
    monkeypatch.setattr(answer, "provider_config", lambda: primary)
    monkeypatch.setattr(answer, "fallback_config", lambda _current: fallback)

    def fake_stream(config: dict[str, str], _text: str, query: str):
        attempted.append(config["provider"])
        assert query == "Explain graph retrieval"
        if config["provider"] == "nvidia":
            yield "Live answer."

    monkeypatch.setattr(answer, "stream_completion", fake_stream)
    chunks = list(engine.stream_chat("Explain graph retrieval"))

    assert attempted == ["xkiro", "nvidia"]
    metadata = json.loads(chunks[0].split("[STREAM_START]", 1)[0])
    assert metadata["model"]["provider"] == "nvidia"
    assert chunks[-1] == "Live answer."
    assert "Grounded draft." not in chunks[1:]


def test_stream_keeps_grounded_answer_when_provider_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed polish call must not hide the available indexed answer."""
    engine = answer.Engine.__new__(answer.Engine)
    monkeypatch.setattr(
        engine,
        "answer",
        lambda _query: {
            "route": "GRAPH_SYNTHESIS",
            "text": "Grounded draft.",
            "payload": {"logs": []},
        },
    )
    monkeypatch.setattr(answer, "provider_config", lambda: {"provider": "xkiro", "model": "first"})
    monkeypatch.setattr(answer, "fallback_config", lambda _current: None)
    monkeypatch.setattr(answer, "stream_completion", lambda _config, _text, _query: iter(()))

    chunks = list(engine.stream_chat("Explain graph retrieval"))

    metadata = json.loads(chunks[0].split("[STREAM_START]", 1)[0])
    assert metadata["model"]["provider"] == "unavailable"
    assert chunks[-1] == "Grounded draft."


def test_nvidia_stream_disables_reasoning_and_includes_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NVIDIA must spend its answer budget on visible reply text."""
    sent: dict = {}

    class Response:
        status_code = 200

        def iter_lines(self):
            yield b'data: {"choices":[{"delta":{"content":"Live answer."}}]}'
            yield b"data: [DONE]"

        def close(self):
            pass

    def post(_url: str, **kwargs):
        sent.update(kwargs["json"])
        return Response()

    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(llm, "_pace_provider_call", lambda: None)
    config = {
        "provider": "nvidia",
        "model": "test",
        "base_url": "https://example.com",
        "key": "test",
    }

    assert list(
        llm.stream_completion(
            config, "Grounded notes", "Why LoRA?", "Earlier reply", "RES-112", "expanded"
        )
    ) == ["Live answer."]
    assert sent["reasoning_effort"] == "none"
    assert sent["max_tokens"] == llm.EXPANDED_REPLY_MAX_TOKENS
    assert "RES-112" in sent["messages"][0]["content"]
    assert "decide answer length" in sent["messages"][0]["content"]
    assert json.loads(sent["messages"][1]["content"])["question"] == "Why LoRA?"
    assert json.loads(sent["messages"][1]["content"])["previous_answer"] == "Earlier reply"
    assert "RES-" in sent["messages"][0]["content"]
    assert "Never expose placeholders" in sent["messages"][0]["content"]


def test_expanded_research_reply_keeps_verified_source_link(monkeypatch):
    """Research evidence uses the selected layout and retains its source trail."""
    engine = answer.Engine.__new__(answer.Engine)
    source_line = "[1] Verified paper: abstract. Source: https://example.org/paper"
    prepared = {
        "route": "RESEARCH_EVIDENCE",
        "text": "Evidence summary.\n" + source_line,
        "payload": {"logs": []},
        "anchor": None,
        "research_overlay": True,
    }
    monkeypatch.setattr(answer, "provider_config", lambda: {"provider": "xkiro", "model": "test"})
    monkeypatch.setattr(answer, "fallback_config", lambda _current: None)

    def fake_stream(_config, _evidence, _query, _previous, template_id, detail, **options):
        assert template_id == "RES-061"
        assert detail == "expanded"
        assert options["reply_plan"]["primary_template"]["id"] == template_id
        yield "Detailed cited synthesis."

    monkeypatch.setattr(answer, "stream_completion", fake_stream)
    chunks = list(
        engine.stream_chat("Is this claim supported?", prepared=prepared, reply_detail="expanded")
    )
    metadata = json.loads(chunks[0].split("[STREAM_START]", 1)[0])
    assert metadata["reply_template"]["id"] == "RES-061"
    assert "Detailed cited synthesis." in "".join(chunks)
    assert source_line in chunks[-1]
