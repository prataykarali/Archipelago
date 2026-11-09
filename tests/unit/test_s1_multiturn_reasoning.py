"""tests/unit/test_s1_multiturn_reasoning.py — Acceptance Tests for S1 Multi-Turn Follow-Ups.

Covers:
- Multi-turn follow-up queries that resolve earlier conversation concepts.
- Pronoun and elided concept resolution across turns.
- Preserves context across both main and hosted chat endpoints.
"""

from __future__ import annotations

from pathlib import Path
import sys
import pytest

ARCHIPELAGO_DIR = Path(__file__).resolve().parents[2]
HOST_DIR = ARCHIPELAGO_DIR / "host_inference"

if str(ARCHIPELAGO_DIR) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO_DIR))
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from host_inference.hostapp.conversation import contextual_query
import engine as hosted_engine


@pytest.fixture(scope="module")
def engine():
    return hosted_engine.Engine()


def test_contextual_query_resolves_pronoun_from_prior_turn():
    """'how does it connect to transformers?' after 'explain BERT' must resolve to BERT."""
    history = [
        {"role": "user", "content": "Explain BERT"},
        {
            "role": "assistant",
            "content": "BERT is a bidirectional transformer pretrained on masked language modeling.",
        },
    ]
    query = "How does it connect to transformers?"
    resolved = contextual_query(query, history)

    assert "bert" in resolved.lower()
    assert "transformer" in resolved.lower()


def test_contextual_query_resolves_short_followup():
    """'what about RAG?' after BERT must resolve both concepts into the context."""
    history = [
        {"role": "user", "content": "Explain BERT"},
        {
            "role": "assistant",
            "content": "BERT is a bidirectional transformer.",
        },
        {"role": "user", "content": "How does it connect to transformers?"},
        {
            "role": "assistant",
            "content": "BERT uses transformer encoder blocks.",
        },
    ]
    query = "What about RAG?"
    resolved = contextual_query(query, history)

    assert "rag" in resolved.lower()


def test_multiturn_reasoning_flow_in_engine(engine):
    """Verify that multi-turn query resolution works end-to-end through the engine."""
    history = [
        {"role": "user", "content": "Explain BERT"},
        {
            "role": "assistant",
            "content": "BERT is a bidirectional transformer encoder model.",
        },
    ]
    followup_raw = "How does it relate to Self-Attention and RAG?"
    resolved = contextual_query(followup_raw, history)

    # Must resolve 'it' to BERT
    assert "bert" in resolved.lower()

    # Query the engine with the resolved multi-turn query
    result = engine.answer(resolved)
    assert result["route"] == "MULTI_CONCEPT", f"Expected MULTI_CONCEPT route, got {result['route']}"

    text = result["text"]
    # All 3 concepts must be present and covered
    assert "bert" in text.lower(), "BERT must be covered in multi-turn follow-up"
    assert "attention" in text.lower(), "Self-Attention must be covered in multi-turn follow-up"
    assert "rag" in text.lower(), "RAG must be covered in multi-turn follow-up"

    # Multi-hop payload verification
    multi_hop = result["payload"].get("multi_hop") or {}
    concepts = [c.lower() for c in multi_hop.get("concepts", [])]
    assert any("bert" in c for c in concepts)
    assert any("attention" in c for c in concepts)
    assert any("rag" in c for c in concepts)
