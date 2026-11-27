"""Unit tests for D11-A.4 Final Targeted Blocker Closure."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = ROOT / "host_inference"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

os.environ.setdefault("ARCHIPELAGO_GRAPH_PATH", str(HOST_DIR / "fixtures" / "okf_graph.json"))

import engine.answer as answer_mod  # noqa: E402
from engine.answer import Engine  # noqa: E402
from hostapp.research_run_chat import is_research_request  # noqa: E402


@pytest.mark.unit
def test_d11_a4_mid_stream_deadline_enforced_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stalled mid-stream provider must terminate at deadline and emit STREAM_INCOMPLETE + STREAM_META."""
    eng = Engine()
    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {"provider": "xkiro", "model": "cohere/command-a", "base_url": "http://x", "key": "k"},
    )
    monkeypatch.setattr(answer_mod, "fallback_config", lambda _c: None)

    def slow_stream(*_a, **_kw):
        yield "Partial opening sentence. "
        time.sleep(0.15)
        yield "Should never arrive after deadline."

    monkeypatch.setattr(answer_mod, "stream_completion", slow_stream)
    monkeypatch.setattr(answer_mod, "last_stream_outcome", lambda: {"status": "complete"})
    monkeypatch.setattr(answer_mod, "last_provider_error", lambda: None)

    prepared = eng.answer("How does virtual memory paging work?")
    deadline = time.perf_counter() + 0.08
    raw = "".join(
        eng.stream_chat(
            "How does virtual memory paging work?",
            prepared=prepared,
            request_deadline=deadline,
        )
    )
    assert "[STREAM_INCOMPLETE:stream_deadline_exceeded]" in raw
    assert "[STREAM_META:" in raw
    meta_str = raw.split("[STREAM_META:", 1)[1].split("]", 1)[0]
    tmeta = json.loads(meta_str)
    assert tmeta["provider_status"] == "stream_deadline_exceeded"
    assert tmeta["stream_status"] == "incomplete_stream"


@pytest.mark.unit
def test_d11_a4_rbac_allows_academic_inference_blocks_research_management() -> None:
    """Academic probability/inference queries must not trip student RBAC; research management must stay blocked."""
    academic_queries = [
        "What probability concepts are prerequisites for Kullback-Leibler divergence and variational inference?",
        "Explain Bayesian inference and posterior estimation in statistics.",
        "Compare Gibbs sampling and variational inference methods.",
    ]
    for q in academic_queries:
        assert is_research_request(q, True) is False, f"False RBAC trigger on: {q}"

    staff_only_queries = [
        "Find 10 research papers on transformers",
        "Show my saved research runs",
        "Export my research collection to Excel",
        "Check my topic monitor for new papers",
    ]
    for q in staff_only_queries:
        assert is_research_request(q, True) is True, f"Missed RBAC enforcement on: {q}"


@pytest.mark.unit
def test_d11_a4_telemetry_populates_real_evidence_ms_and_null_when_unexecuted() -> None:
    """evidence_retrieval_ms is measured when retrieval runs and None when skipped."""
    eng = Engine()
    res_grounded = eng.answer("How does virtual memory paging work?")
    assert isinstance(res_grounded["evidence_retrieval_ms"], float)
    assert res_grounded["evidence_retrieval_ms"] >= 0.0

    res_greeting = eng.answer("Hello!")
    assert res_greeting["evidence_retrieval_ms"] is None


@pytest.mark.unit
def test_d11_a4_generalizable_concept_specificity_and_unseen_paraphrases() -> None:
    """Generic unigrams ('data', 'syntax', 'tree') must not hijack multi-word domain queries."""
    eng = Engine()
    assert eng.answer("What data structures are prerequisites for graph shortest-path algorithms?")["anchor"] != "data"
    assert eng.answer("How does the OSI Data Link Layer frame packets over the Physical Layer?")["anchor"] == "data_link_layer"
    assert eng.answer("How do data hazards and branch prediction affect five-stage RISC pipeline throughput?")["anchor"] != "data"
    assert eng.answer("How does LALR bottom-up parsing construct a syntax tree from tokens?")["anchor"] == "syntax_analysis"

    # Unseen development paraphrases
    assert eng.answer("Explain how bottom-up parser grammars build abstract syntax trees.")["anchor"] == "syntax_analysis"
    assert eng.answer("What is the role of the Data Link Layer in Ethernet framing?")["anchor"] == "data_link_layer"
    assert eng.answer("How do you avoid data races in multi-threaded operating systems?")["anchor"] != "data"
    # Direct short definition still resolves
    assert eng.answer("What is data?")["anchor"] == "data"
