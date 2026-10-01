"""Contract tests for the hosted learning-roadmap and quiz builders.

The chat UI POSTs ``/api/roadmap`` and expects ``data.stages[].items[]`` with
``name``, ``summary``, ``study_hours`` and ``citations``.  These tests pin that
shape against a small deterministic fake graph so a change to the builder
cannot silently break the roadmap modal again.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from host_roadmap import build_quiz, build_roadmap, resolve_topic  # noqa: E402

pytestmark = pytest.mark.unit


class FakeGraph:
    """Minimal concept graph used by the roadmap/quiz builders."""

    nodes = {
        "target": {"summary": "Target concept.", "difficulty": "advanced"},
        "prereq_a": {"summary": "First prerequisite.", "difficulty": "intermediate"},
        "prereq_b": {"summary": "Second prerequisite.", "difficulty": "foundational"},
    }

    def label(self, cid: str) -> str:
        return cid.replace("_", " ").title()

    def phrase_hits(self, query: str) -> list[str]:
        return ["target"] if "target" in query.lower() else []

    def rank(self, query: str, top_k: int = 1):
        return [(0.95, "target")]

    def prereqs(self, cid: str, k: int = 1) -> list[str]:
        return {"target": ["prereq_a"], "prereq_a": ["prereq_b"], "prereq_b": []}[cid]

    def cite_record(self, cid: str, query: str = "", index: int = 1) -> dict:
        return {
            "doc_id": f"papers/{cid}.pdf",
            "page_number": 4,
            "url": f"/read?doc=papers/{cid}.pdf&page=4",
        }


class FakeEngine:
    def __init__(self):
        self.graph = FakeGraph()

    def mcq_for(self, concept_id: str, slot: int = 0) -> dict:
        return {
            "concept_id": concept_id,
            "options": {"A": "Correct", "B": "Wrong 1", "C": "Wrong 2", "D": "Wrong 3"},
            "correct_option": "A",
            "question": f"Which statement matches {concept_id}?",
            "explanation": "Because it matches the catalogue.",
            "citation": "[S1: target.pdf, #page=4]",
        }


def test_roadmap_orders_stages_foundation_to_target():
    result = build_roadmap(FakeGraph(), "target")
    assert "error" not in result
    assert result["target_id"] == "target"
    assert result["hops"] == 2

    stages = result["stages"]
    assert stages[0]["stage"] == "Foundations"
    assert [item["id"] for item in stages[0]["items"]] == ["prereq_b"]
    assert stages[-1]["stage"] == "Target"
    assert [item["id"] for item in stages[-1]["items"]] == ["target"]


def test_roadmap_items_carry_study_hours_and_citations():
    result = build_roadmap(FakeGraph(), "target")
    item = result["stages"][0]["items"][0]
    assert item["study_hours"] == 3  # foundational tier
    assert item["citations"] == ["prereq_b.pdf"]
    assert item["page_number"] == 4
    assert item["url"].endswith("page=4")


def test_roadmap_rejects_empty_and_unknown_topics():
    assert "error" in build_roadmap(FakeGraph(), "   ")
    unknown = build_roadmap(FakeGraphWithoutHits(), "sourdough")
    assert "error" in unknown
    assert "sourdough" in unknown["error"]


class FakeGraphWithoutHits(FakeGraph):
    def phrase_hits(self, query: str) -> list[str]:
        return []

    def rank(self, query: str, top_k: int = 1):
        return [(0.10, "target")]


def test_resolve_topic_falls_back_to_cosine_then_gives_up():
    assert resolve_topic(FakeGraph(), "target") == "target"
    assert resolve_topic(FakeGraphWithoutHits(), "anything") is None


def test_quiz_returns_ui_shaped_questions():
    result = build_quiz(FakeEngine(), "target", count=2)
    questions = result["quiz"]["questions"]
    assert len(questions) == 2
    first = questions[0]
    assert first["options"] == ["Correct", "Wrong 1", "Wrong 2", "Wrong 3"]
    assert first["answer"] == "Correct"
    assert first["explanation"]


def test_quiz_rejects_missing_topic():
    assert "error" in build_quiz(FakeEngine(), "")
