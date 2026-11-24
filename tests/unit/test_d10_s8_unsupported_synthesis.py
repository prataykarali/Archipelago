"""Prevent live synthesis from replacing an evidence-based abstention."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine import answer  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "query",
    [
        "Explain Spanner TrueTime and its prerequisites.",
        "How does Raft consensus elect a leader?",
    ],
)
def test_unsupported_answer_never_calls_provider(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    """A provider cannot turn an unindexed topic into an asserted answer."""
    engine = answer.Engine()
    prepared = engine.answer(query)
    assert prepared["payload"]["trace"]["grounding_status"] == "unmatched"
    monkeypatch.setattr(answer, "provider_config", lambda: {"provider": "xkiro", "model": "test"})

    def unexpected_provider(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unsupported answer reached live provider")

    monkeypatch.setattr(answer, "stream_completion", unexpected_provider)
    chunks = list(engine.stream_chat(query, prepared=prepared))
    metadata = json.loads(chunks[0].split("[STREAM_START]", 1)[0])
    assert metadata["synthesis_mode"] == "verified_deterministic"
    assert "".join(chunks[1:]) == prepared["text"]


def test_supported_answer_can_use_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provenance-verified BERT passage still permits live synthesis."""
    engine = answer.Engine()
    prepared = engine.answer("What is BERT?")
    assert prepared["payload"]["trace"]["grounding_status"] == "verified"
    monkeypatch.setattr(answer, "provider_config", lambda: {"provider": "xkiro", "model": "test"})
    monkeypatch.setattr(answer, "fallback_config", lambda _config: None)
    monkeypatch.setattr(answer, "stream_completion", lambda *_args: iter(["Supported reply."]))
    chunks = list(engine.stream_chat("What is BERT?", prepared=prepared))
    metadata = json.loads(chunks[0].split("[STREAM_START]", 1)[0])
    assert metadata["synthesis_mode"] == "xkiro_synthesis"


@pytest.mark.parametrize(
    "status",
    ["unmatched", "partial", "general", "source_linked"],
)
def test_unverified_evidence_cannot_be_polished(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """Missing anchors, passages, or exact support retain deterministic text."""
    engine = answer.Engine()
    prepared = engine.answer("What is BERT?")
    prepared["payload"]["trace"]["grounding_status"] = status
    prepared["research_overlay"] = True
    monkeypatch.setattr(answer, "provider_config", lambda: {"provider": "xkiro", "model": "test"})

    def unexpected_provider(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unverified answer reached live provider")

    monkeypatch.setattr(answer, "stream_completion", unexpected_provider)
    chunks = list(engine.stream_chat("What is BERT?", prepared=prepared))
    metadata = json.loads(chunks[0].split("[STREAM_START]", 1)[0])
    assert metadata["synthesis_mode"] == "verified_deterministic"
    assert "".join(chunks[1:]) == prepared["text"]
