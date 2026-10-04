"""Server-authoritative adaptive questions over the existing hosted graph."""
from __future__ import annotations

import secrets

from .learning_state import (
    CONFIDENCE,
    INITIAL_QUESTIONS,
    MAX_QUESTIONS,
    PREFERENCES,
    misconception,
    neighborhood,
    next_node,
    personalized_graph,
    update_mastery,
)

OPTION_LIMIT = 4
SUMMARY_CHARS = 220
QUESTION_FIELDS = (
    "question_id", "concept_id", "concept_name", "difficulty", "question", "options",
)


def _question(graph, cid: str) -> dict:
    """Shuffle graph-backed definitions; retain answer keys only on the server."""
    summary = str(graph.nodes[cid].get("summary") or "").strip()[:SUMMARY_CHARS]
    if not summary:
        raise ValueError("This prerequisite lacks a definition for a grounded diagnostic.")
    candidates = [cid] + [
        other for _, other in graph.rank(graph.label(cid), top_k=len(graph.nodes))
        if other != cid
    ]
    options, seen = [], set()
    for other in candidates:
        text = str(graph.nodes[other].get("summary") or "").strip()[:SUMMARY_CHARS]
        if text and text not in seen:
            options.append((other, text))
            seen.add(text)
        if len(options) == OPTION_LIMIT:
            break
    if len(options) < 2:
        raise ValueError("More distinct indexed definitions are needed for a diagnostic.")
    secrets.SystemRandom().shuffle(options)
    pairs = dict(zip("ABCD", options, strict=False))
    return {
        "question_id": secrets.token_urlsafe(18),
        "concept_id": cid, "concept_name": graph.label(cid),
        "difficulty": graph.nodes[cid].get("difficulty", "intermediate"),
        "question": f"Which indexed definition describes {graph.label(cid)}?",
        "options": {key: value[1] for key, value in pairs.items()},
        "option_nodes": {key: value[0] for key, value in pairs.items()},
        "correct_option": next(key for key, value in pairs.items() if value[0] == cid),
        "explanation": summary,
        "citation": graph.citation(cid),
    }


def public_question(question: dict | None) -> dict | None:
    """Exclude answer, explanation and distractor identity until after submission."""
    return {key: question[key] for key in QUESTION_FIELDS} if question else None


def start(graph, target: str, preference: str = "conceptual", remembered: dict | None = None) -> tuple[dict, dict]:
    """Start a minimal, bounded session; unknown targets never select a random node."""
    if not isinstance(target, str) or target not in graph.nodes:
        raise ValueError("The target concept is not indexed.")
    if not isinstance(preference, str) or preference not in PREFERENCES:
        raise ValueError("Unknown learning preference.")
    session = {
        "target": target, "preference": preference, "depths": neighborhood(graph, target),
        "history": [], "mastery": {}, "completed": False,
    }
    session["mastery"] = {
        cid: dict(record) for cid, record in (remembered or {}).items()
        if cid in session["depths"] and isinstance(record, dict)
    }
    cid = next_node(graph, session)
    session["question"] = _question(graph, cid)
    first = public_question(session["question"])
    return session, {
        "success": True, "available": True, "target_concept": target,
        "target_label": graph.label(target), "chain": [*session["depths"], target],
        "prereq_chain": list(session["depths"]), "initial_question": first,
        "mcqs": [first], "initial_questions": INITIAL_QUESTIONS,
        "max_questions": MAX_QUESTIONS, "preference": preference,
    }


def advance(graph, session: dict, body: dict) -> dict:
    """Grade only the issued question; ignore all client-provided mastery and keys."""
    question = session["question"]
    if session["completed"] or body.get("question_id") != question["question_id"]:
        raise ValueError("This question expired or was already answered. Restart the diagnostic.")
    confidence = body.get("confidence", "medium")
    preference = body.get("preference", session["preference"])
    choice = str(body.get("user_choice") or "").upper()
    if not isinstance(confidence, str) or not isinstance(preference, str) or confidence not in CONFIDENCE or preference not in PREFERENCES:
        raise ValueError("Unknown confidence or learning preference.")
    if choice not in question["options"]:
        raise ValueError("Choose one of the issued options.")
    session["preference"] = preference
    cid = question["concept_id"]
    correct = choice == question["correct_option"]
    session["mastery"][cid] = update_mastery(
        cid, correct, confidence, session["mastery"].get(cid),
    )
    session["history"].append({
        "concept_id": cid, "is_correct": correct, "confidence": confidence, "choice": choice,
    })
    next_cid = next_node(graph, session)
    session["completed"] = next_cid is None
    next_question = _question(graph, next_cid) if next_cid is not None else None
    graph_payload = personalized_graph(graph, session)
    mastered = [cid for cid, value in session["mastery"].items() if value["mastery_state"] == "mastered"]
    gaps = [cid for cid, value in session["mastery"].items() if value["mastery_state"] == "review_gap"]
    passed = len(mastered) == len(session["depths"])
    total = len(session["history"])
    result = {
        "is_tick": correct,
        "current_record": {
            "correct_answer": question["correct_option"], "concept_id": cid,
            "explanation": question["explanation"], "citation": question["citation"],
            "mastery_state": session["mastery"][cid]["mastery_state"],
        },
        "misconception": misconception(graph, cid, question["option_nodes"][choice], confidence, correct),
        "consecutive_ticks": len(mastered), "history": session["history"],
        "completed": session["completed"],
        "completion_reason": (
            "question_budget" if total >= MAX_QUESTIONS else "coverage_sufficient"
        ) if session["completed"] else "",
        "total_asked": total, "stride_action": "advance" if correct else "review",
        "next_concept": next_cid, "next_question": public_question(next_question),
        "personalized_graph": graph_payload, "mastered": mastered, "gaps": gaps,
        "evaluation": {
            "target_concept": session["target"], "score": f"{len(mastered)}/{len(session['depths'])}",
            "passed": passed, "full_score": passed, "zero_score": not mastered,
            "personalized_graph": graph_payload,
            "coverage": {"assessed": len(session["mastery"]), "total": len(session["depths"])},
        },
    }
    if next_question:
        session["question"] = next_question
    return result
