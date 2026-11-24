"""Check that response metadata describes the executed synthesis path."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine import answer  # noqa: E402
from engine.provenance import build_grounding_trace  # noqa: E402

pytestmark = pytest.mark.unit


def _engine() -> answer.Engine:
    return answer.Engine.__new__(answer.Engine)


def _prepared() -> dict:
    return {
        "route": "GRAPH_SYNTHESIS",
        "text": "Grounded draft with enough words to avoid appending an additional draft after the response.",
        "payload": {"logs": [], "trace": {"claim_support_status": "not_assessed"}},
        "anchor": None,
    }


def _metadata(chunks: list[str]) -> dict:
    return json.loads(chunks[0].split("[STREAM_START]", 1)[0])


def test_provider_trace_identifies_actual_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    monkeypatch.setattr(
        answer, "provider_config", lambda: {"provider": "xkiro", "model": "primary"}
    )
    monkeypatch.setattr(
        answer, "fallback_config", lambda _: {"provider": "nvidia", "model": "fallback"}
    )

    def stream(config: dict, *_args: object, **_kwargs: object):
        if config["provider"] == "nvidia":
            yield "Live provider response with enough detail to count as the complete response."

    monkeypatch.setattr(answer, "stream_completion", stream)
    meta = _metadata(list(engine.stream_chat("Explain graphs", prepared=_prepared())))
    assert meta["trace"]["provider"] == "nvidia"
    assert meta["trace"]["model"] == "fallback"
    assert meta["trace"]["synthesis_mode"] == "nvidia_fallback"
    assert meta["trace"]["template_influenced"] is False


def test_unavailable_provider_is_not_claimed_as_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    monkeypatch.setattr(answer, "provider_config", lambda: None)
    meta = _metadata(list(engine.stream_chat("Explain graphs", prepared=_prepared())))
    assert meta["trace"]["provider"] == "unavailable"
    assert meta["trace"]["model"] == ""
    assert meta["trace"]["synthesis_mode"] == "provider_unavailable_fallback"


def test_general_explanation_does_not_claim_support() -> None:
    trace = build_grounding_trace(
        route="GENERAL_EXPLANATION",
        anchor_id=None,
        anchor_label=None,
        hops=0,
        citations=[],
        provider="",
        latency_s=0.0,
        latency_ms=0,
    )
    assert trace["explanation_status"] == "general_explanation"
    assert trace["claim_support_status"] == "not_assessed"
    assert trace["reader_page_verified"] is False
    assert trace["provider"] == "pending"
