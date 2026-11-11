"""Check the hosted API stream with the real indexed concept graph."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine import Engine  # noqa: E402
from hostapp.middleware import register_middleware  # noqa: E402
from hostapp.routes import chat  # noqa: E402

pytestmark = pytest.mark.integration


def test_indexed_concept_flows_through_unchanged_stream_contract(monkeypatch) -> None:
    """A real graph answer reaches the API with a plan and no fake holdings."""
    if not (HOST / "cache" / "okf_graph.json").is_file():
        pytest.skip("Hosted graph cache is unavailable")
    monkeypatch.setattr(chat, "provider_config", lambda: None)
    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _query: prepared)
    from engine import answer

    monkeypatch.setattr(answer, "provider_config", lambda: None)
    app = Flask(__name__)
    ctx = SimpleNamespace(
        auth=SimpleNamespace(required=lambda: False, principal=lambda: (None, None)),
        limiter=SimpleNamespace(check_chat=lambda: (False, 0), check_api=lambda: (False, 0)),
        engine=Engine(),
        cache_metrics=SimpleNamespace(record_request=lambda: None, record_miss=lambda: None),
    )
    register_middleware(app, ctx)
    chat.register(app, ctx)

    response = app.test_client().post(
        "/api/chat", json={"query": "What is third normal form?", "reply_detail": "expanded"}
    )
    assert response.status_code == 200
    metadata_text, body = response.get_data(as_text=True).split("[STREAM_START]", 1)
    metadata = json.loads(metadata_text)
    assert metadata["reply_plan"]["depth"] == "brief"
    assert metadata["reply_template"]["id"].startswith("RES-")
    assert body.lstrip().startswith("**Third Normal Form (3NF).**")
    assert "Live shelf availability" not in body
    assert "Physical Campus Library Inventory" not in body


def test_paper_comparison_uses_the_requested_pair() -> None:
    """A LoRA–QLoRA question must not reuse the old LoRA–BERT demo card."""
    if not (HOST / "cache" / "okf_graph.json").is_file():
        pytest.skip("Hosted graph cache is unavailable")
    result = Engine().answer("Compare LoRA and QLoRA research papers")
    assert result["route"] == "CROSS_DOMAIN"
    assert "QLoRA" in result["text"]
    assert "BERT represent distinct layers" not in result["text"]


def test_unindexed_ai_research_gets_an_evidence_limit_not_an_ood_rejection() -> None:
    """A legitimate research question can be unsupported without being out of domain."""
    if not (HOST / "cache" / "okf_graph.json").is_file():
        pytest.skip("Hosted graph cache is unavailable")
    result = Engine().answer(
        "What research gaps exist in efficient long-term memory for small models?"
    )
    assert result["route"] == "RESEARCH_UNVERIFIED"
    assert "cannot verify" in result["text"]


def test_simple_neural_network_definition_does_not_cite_graph_neural_network_paper() -> None:
    """A general concept answer stays general when indexed evidence is narrower."""
    if not (HOST / "cache" / "okf_graph.json").is_file():
        pytest.skip("Hosted graph cache is unavailable")
    result = Engine().answer("What is a neural network?")
    assert result["route"] == "GENERAL_EXPLANATION"
    assert "trainable model" in result["text"]
    assert result["payload"]["citations"] == []
    assert result["payload"]["render_graph"] is False
