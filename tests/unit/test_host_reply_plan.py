"""Exercise the hosted response plan against real registry and evidence shapes."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine.reply_plan import build_reply_plan, plan_guidance  # noqa: E402
from hostapp import research_chat  # noqa: E402
from hostapp.conversation import contextual_query  # noqa: E402
from library_index import Catalog  # noqa: E402

pytestmark = pytest.mark.unit


def test_page_and_research_modules_require_matching_evidence() -> None:
    """A comparison can use real papers and pages without inventing holdings."""
    payload = {
        "citations": [{"doc_id": "papers/LoRA.pdf", "page_number": 3}],
        "research_sources": [{"title": "LoRA", "url": "https://example.org/lora"}],
        "anchor_concept": {"id": "lora"},
        "prerequisites": [{"id": "linear_algebra"}],
    }
    plan = build_reply_plan("Compare LoRA papers and cite the page", "GRAPH_SYNTHESIS", payload)
    assert plan["primary_template"]["id"] == "RES-091"
    assert "RES-062" in plan["secondary_templates"]
    assert "RES-061" in plan["secondary_templates"]
    assert "digital_resources" not in plan["presentation"]
    assert "physical_holdings" not in plan["presentation"]
    assert plan["depth"] == "deep"
    guidance = plan_guidance(plan)
    assert "RES-062 Exact-page research answer" in guidance
    assert "RES-061 Claim-to-evidence card" in guidance


def test_simple_question_stays_brief_and_does_not_gain_empty_modules() -> None:
    """One short factual question must not become a generic research report."""
    plan = build_reply_plan("What is backpropagation?", "GRAPH_SYNTHESIS", {"citations": []})
    assert plan["depth"] == "brief"
    assert plan["presentation"] == ["direct_answer"]
    assert plan["secondary_templates"] == []


def test_follow_up_uses_bounded_previous_user_topic() -> None:
    """The active referent comes from conversation history, not a guessed paper."""
    history = [
        {"role": "user", "content": "Explain GraphRAG"},
        {"role": "assistant", "content": "A very long prior answer"},
    ]
    resolved = contextual_query("What about its limitations?", history)
    assert resolved.startswith("What about its limitations?")
    assert "Explain GraphRAG" in resolved
    assert "very long prior answer" not in resolved
    assert contextual_query("Explain BERT", history) == "Explain BERT"


def test_research_overlay_exposes_source_without_inventing_pdf_page(monkeypatch) -> None:
    """Saved research metadata gives a clickable source but no fake full-text page."""
    monkeypatch.setattr(
        research_chat,
        "search_records",
        lambda _query, kind=None: [
            {
                "record_key": "paper-1",
                "title": "GraphRAG study",
                "topic": "GraphRAG",
                "content": "A source excerpt about graph retrieval.",
                "source_url": "https://example.org/paper",
                "kind": "paper",
            }
        ],
    )
    monkeypatch.setattr(research_chat, "library_paper_evidence", lambda _row: None)
    prepared = {
        "route": "GRAPH_SYNTHESIS",
        "text": "Graph retrieval uses linked concepts.",
        "payload": {"routing": {"route": "GRAPH_SYNTHESIS"}, "citations": []},
    }
    result = research_chat.enrich_with_research(prepared, "GraphRAG research papers")
    source = result["payload"]["research_sources"][0]
    assert source["evidence_id"] == "P1"
    assert source["url"] == "https://example.org/paper"
    assert source["page_number"] is None
    assert source in result["payload"]["citations"]


def test_catalog_metadata_without_passage_has_no_claimed_page() -> None:
    """A matched PDF or e-book title alone does not verify PDF page one."""
    catalog = Catalog.__new__(Catalog)
    catalog.best_passage = lambda _query, _key: None
    paper = catalog._hf_reply(
        "Open this paper", {"path": "papers/Hu2021_LoRA.pdf", "title": "LoRA"}
    )
    assert paper["citation"]["page_number"] is None
    assert "page=1" not in paper["citation"]["url"]
    book = catalog._pearson_reply(
        "Open this book", {"id": "verified-book-id", "title": "Digital textbook"}
    )
    assert book["citation"]["page_number"] is None
    assert "page=1" not in book["citation"]["url"]
