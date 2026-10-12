"""Verify the hosted chat stream changes providers after an empty response."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine import answer  # noqa: E402

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

    def fake_stream(config: dict[str, str], _text: str):
        attempted.append(config["provider"])
        if config["provider"] == "nvidia":
            yield "Live answer."

    monkeypatch.setattr(answer, "stream_completion", fake_stream)
    chunks = list(engine.stream_chat("Explain graph retrieval"))

    assert attempted == ["xkiro", "nvidia"]
    assert chunks[-1] == "Live answer."
    assert "Grounded draft." not in chunks[1:]
