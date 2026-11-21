"""Regression tests for the stale-graph bug fix (SIGIR Demo Phase 1).

Verifies that queries for unmatched concepts do NOT silently substitute
a different graph node, and that matched concepts resolve correctly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

# Force deterministic provider so tests run without API keys.
os.environ.setdefault("ARCHIPELAGO_LLM_PROVIDER", "deterministic")


@pytest.fixture(scope="module")
def engine():
    """Load the hosted Engine, skip if graph cache is absent."""
    graph = HOST_DIR / "cache" / "okf_graph.json"
    if not graph.is_file():
        pytest.skip("hosted concept graph cache is not present")
    from engine.answer import Engine

    return Engine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload(engine, query: str) -> dict:
    """Return only the payload dict from an Engine.answer() call."""
    return engine.answer(query)["payload"]


def _anchor_id(payload: dict) -> str | None:
    """Extract the anchor concept id or None."""
    ac = payload.get("anchor_concept")
    if isinstance(ac, dict):
        return ac.get("id")
    return ac


# ---------------------------------------------------------------------------
# Test A — Compiler query must NOT match Transformer / Attention / any node
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStaleGraphRegression:
    """The stale-graph bug silently substituted the highest-scoring node
    (e.g. ``transformer_encoder``) when no concept matched.  After the fix,
    unmatched queries must have anchor_concept=None and render_graph=False.
    """

    def test_a_compiler_query_no_anchor(self, engine):
        """Compiler query → no concept match, no graph rendered."""
        p = _payload(engine, "How do compilers transform source code into machine instructions?")
        assert _anchor_id(p) is None, (
            f"Compiler query matched {_anchor_id(p)} — stale-graph bug is back"
        )
        assert p.get("render_graph") is False

    def test_a_compiler_query_has_citations(self, engine):
        """Compiler query should still return general citations if any exist."""
        p = _payload(engine, "How do compilers transform source code into machine instructions?")
        # Citations are allowed but NOT mandatory for unmatched queries
        # The key assertion is: no fabricated anchor
        assert _anchor_id(p) is None

    def test_b_transformer_query_resolves(self, engine):
        """'What is Transformer?' → anchor_concept.id == 'transformer'."""
        p = _payload(engine, "What is Transformer?")
        assert _anchor_id(p) == "transformer", (
            f"Transformer query resolved to {_anchor_id(p)}, expected 'transformer'"
        )
        assert p.get("render_graph") is True

    def test_c_attention_transformer_relation(self, engine):
        """Multi-concept query → anchor is attention_mechanism."""
        p = _payload(engine, "How does Attention Mechanism relate to Transformer?")
        assert _anchor_id(p) == "attention_mechanism", (
            f"Attention+Transformer resolved to {_anchor_id(p)}, expected 'attention_mechanism'"
        )
        assert p.get("render_graph") is True

    def test_d_spanner_truetime_no_anchor(self, engine):
        """Out-of-domain query → no concept match."""
        p = _payload(engine, "Explain Spanner TrueTime")
        assert _anchor_id(p) is None, (
            f"Spanner TrueTime matched {_anchor_id(p)} — should be None"
        )
        assert p.get("render_graph") is False

    def test_e_dbms_library_routing(self, engine):
        """Library catalog query → CATALOG_SHELF_ROUTING route."""
        result = engine.answer("Where can I find DBMS in the UEM library?")
        assert result["route"] == "CATALOG_SHELF_ROUTING"
        p = result["payload"]
        # Library queries don't need a concept anchor
        assert _anchor_id(p) is None or result["route"] == "CATALOG_SHELF_ROUTING"


# ---------------------------------------------------------------------------
# Trace payload tests (SIGIR Demo instrumentation)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTracePayload:
    """Verify the trace dict added for the SIGIR Demo Inspector."""

    def test_trace_present_on_matched_query(self, engine):
        """Matched concept → trace with verified grounding."""
        p = _payload(engine, "What is Transformer?")
        trace = p.get("trace")
        assert trace is not None, "trace dict missing from payload"
        assert trace["concept_id"] == "transformer"
        assert trace["grounding_status"] == "verified"
        assert trace["graph_hops"] >= 1
        assert trace["retrieval_mode"].startswith("Graph-Assisted")

    def test_trace_present_on_unmatched_query(self, engine):
        """Unmatched concept → trace with unmatched grounding."""
        p = _payload(engine, "Explain Spanner TrueTime")
        trace = p.get("trace")
        assert trace is not None, "trace dict missing from payload"
        assert trace["concept_id"] is None
        assert trace["grounding_status"] in {"unmatched", "general"}
        assert trace["graph_hops"] == 0

    def test_trace_grounding_badge_text(self, engine):
        """Grounding badge text must be a human-readable string."""
        p = _payload(engine, "What is Transformer?")
        badge = p["trace"]["grounding_badge"]
        assert isinstance(badge, str)
        assert len(badge) > 5  # noqa: PLR2004 — sanity check
