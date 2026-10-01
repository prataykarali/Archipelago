"""Learning-roadmap and practice-quiz builders for the hosted librarian.

One concern: turning the concept graph into the staged learning progression the
chat UI renders.  Roadmaps walk *backwards* through REQUIRES/UNLOCKS edges so
the stages read foundation → prerequisites → target; quizzes reuse the
diagnostic MCQ builder so a topic always yields real catalogue-backed options.
"""
from __future__ import annotations

from engine.constants import KILL_SWITCH

# Estimated study hours per difficulty tier (a planning aid, not a claim).
STUDY_HOURS = {
    "foundational": 3,
    "beginner": 4,
    "intermediate": 6,
    "advanced": 8,
    "expert": 10,
}
DEFAULT_STUDY_HOURS = 5
DEFAULT_DIFFICULTY = "intermediate"

MAX_STAGES = 4
MAX_ITEM_SUMMARY_CHARS = 240
DEFAULT_QUIZ_QUESTIONS = 3
QUIZ_OPTION_KEYS = ("A", "B", "C", "D")

FOUNDATION_STAGE_NAME = "Foundations"
PREREQUISITE_STAGE_NAME = "Prerequisites"


def resolve_topic(graph, topic: str) -> str | None:
    """Resolve free text to a concept id (literal phrase first, then cosine)."""
    hits = graph.phrase_hits(topic)
    if hits:
        return hits[0]
    ranked = graph.rank(topic, top_k=1)
    if ranked and ranked[0][0] >= KILL_SWITCH:
        return ranked[0][1]
    return None


def _roadmap_item(graph, cid: str) -> dict:
    node = graph.nodes[cid]
    record = graph.cite_record(cid)
    doc_id = record.get("doc_id") or ""
    return {
        "id": cid,
        "name": graph.label(cid),
        "summary": (node.get("summary") or "")[:MAX_ITEM_SUMMARY_CHARS],
        "difficulty": node.get("difficulty") or DEFAULT_DIFFICULTY,
        "study_hours": STUDY_HOURS.get(node.get("difficulty") or "", DEFAULT_STUDY_HOURS),
        "citations": [doc_id.split("/")[-1]] if doc_id else [],
        "doc_id": doc_id,
        "page_number": record.get("page_number") or 1,
        "url": record.get("url") or "",
    }


def _stage_name(graph, index: int, last_index: int, target: str, count: int) -> str:
    if index == last_index:
        return graph.label(target)
    if index == 0:
        return FOUNDATION_STAGE_NAME
    return f"{PREREQUISITE_STAGE_NAME} ({count} concepts)"


def build_roadmap(graph, topic: str) -> dict:
    """Return ``{"stages": [...]}`` for a topic, or ``{"error": ...}`` if unknown.

    Each stage carries ordered items with ``name``, ``summary``, ``study_hours``
    and ``citations`` — the exact shape ``ui/chat/js/21-generate-roadmap.js``
    renders.
    """
    clean = (topic or "").strip()
    if not clean:
        return {"error": "A topic is required to build a roadmap."}
    target = resolve_topic(graph, clean)
    if target is None:
        return {"error": f"No indexed concept matches '{clean}'."}

    # Walk backwards from the target through prerequisite levels.
    levels: list[list[str]] = []
    seen = {target}
    frontier = [target]
    for _ in range(MAX_STAGES - 1):
        nxt: list[str] = []
        for cur in frontier:
            for prereq in graph.prereqs(cur, 1):
                if prereq not in seen:
                    seen.add(prereq)
                    nxt.append(prereq)
        if not nxt:
            break
        levels.append(nxt)
        frontier = nxt

    groups = list(reversed(levels)) + [[target]]
    last_index = len(groups) - 1
    stages = []
    for index, group in enumerate(groups):
        stages.append({
            "stage": _stage_name(graph, index, last_index, target, len(group)),
            "index": index,
            "items": [_roadmap_item(graph, cid) for cid in group],
        })
    return {
        "topic": graph.label(target),
        "target_id": target,
        "hops": len(levels),
        "stages": stages,
    }


def build_quiz(engine, topic: str, count: int = DEFAULT_QUIZ_QUESTIONS) -> dict:
    """Return ``{"quiz": {"questions": [...]}}`` built from diagnostic MCQs."""
    clean = (topic or "").strip()
    if not clean:
        return {"error": "A topic is required to build a quiz."}
    target = resolve_topic(engine.graph, clean)
    if target is None:
        return {"error": f"No indexed concept matches '{clean}'."}
    questions = []
    for slot in range(max(1, count)):
        mcq = engine.mcq_for(target, slot)
        options = mcq.get("options") or {}
        correct = mcq.get("correct_option") or "A"
        questions.append({
            "concept_id": mcq.get("concept_id") or target,
            "question": mcq.get("question") or "",
            "options": [options.get(key, "") for key in QUIZ_OPTION_KEYS],
            "answer": options.get(correct, ""),
            "explanation": mcq.get("explanation") or "",
            "citation": mcq.get("citation") or "",
        })
    return {
        "quiz": {
            "topic": engine.graph.label(target),
            "target_id": target,
            "questions": questions,
        }
    }
