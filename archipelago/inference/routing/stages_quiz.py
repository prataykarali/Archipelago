"""Quiz routing stages: diagnostic evaluation, quiz requests, roadmaps."""
from __future__ import annotations

import re

from . import _deps as _rt


def quiz_route(q_raw: str, history: list | None, ranked: list, best: dict | None, best_cos: float) -> dict | None:
    """Quiz-answer evaluation, diagnostic quiz requests, X→Y roadmaps."""
    # Check if user is replying to a diagnostic quiz with answers
    quiz_answers = _rt._extract_quiz_answers(q_raw)
    is_quiz_response = False
    if len(quiz_answers) >= 3:
        is_quiz_response = True
    elif history and len(quiz_answers) >= 1:
        last_asst = next((h.get("content", "") for h in reversed(history) if h.get("role") == "assistant"), "")
        if "Knowledge Assessment" in last_asst or "diagnostic question" in last_asst.lower() or "Question 1:" in last_asst:
            is_quiz_response = True

    if is_quiz_response:
        target_concept = _rt._get_active_concept_from_history(history) or "low_rank_adaptation"
        return {
            "anchor_id": target_concept,
            "score": 1.0,
            "related": ranked,
            "slots": {
                "intent": "roadmap_quiz_eval",
                "target_concept": target_concept,
                "answers": quiz_answers,
            },
            "scope": "yes",
            "route": "roadmap_quiz_eval",
            "reason": "diagnostic_evaluation",
        }

    # Diagnostic knowledge assessment check (Context-Aware)
    if re.search(r"\b(quiz\s+me|diagnostic\s+quiz|test\s+my\s+knowledge|assess\s+my\s+knowledge|evaluate\s+my\s+knowledge)\b", q_raw, re.I):
        # 1. Check if user explicitly named a specific concept in this query
        clean_quiz_q = re.sub(
            r"\b(can\s+you\s+)?(quiz\s+me|diagnostic\s+quiz|test\s+my\s+knowledge|assess\s+my\s+knowledge|evaluate\s+my\s+knowledge)\b",
            " ", q_raw, flags=re.I
        )
        clean_quiz_q = re.sub(r"\b(on|about|for|to|prerequisites|prereqs|baseline|this|it|that|topic|concept|what\s+we\s+discussed|please)\b", " ", clean_quiz_q, flags=re.I).strip()
        target_concept = None
        if clean_quiz_q and len(clean_quiz_q) >= 3:
            specific_ranked = _rt.rank_concepts(clean_quiz_q, top_k=1)
            if specific_ranked and (float(specific_ranked[0].get("cos", 0)) >= 0.48 or float(specific_ranked[0].get("lexical", 0)) >= 0.70):
                target_concept = specific_ranked[0]["id"]

        # 2. If no explicit concept named, or query leans on context ("this", "it"), check history!
        if not target_concept and history:
            target_concept = _rt._get_active_concept_from_history(history)

        if not target_concept:
            target_concept = best["id"] if (best and best["id"] != "knowledge_graph") else "low_rank_adaptation"

        return {
            "anchor_id": target_concept,
            "score": best_cos,
            "related": ranked,
            "slots": {"intent": "roadmap_quiz", "target_concept": target_concept},
            "scope": "yes",
            "route": "roadmap_quiz",
            "reason": "diagnostic_assessment",
        }

    # Roadmap between two concepts check (e.g. roadmap from X to Y)
    roadmap_match = re.search(r"\broadmap\s+(?:from|between)\s+(.+?)\s+(?:to|and)\s+(.+)", q_raw, re.I)
    if roadmap_match:
        from_term = roadmap_match.group(1).strip()
        to_term = roadmap_match.group(2).strip()
        from_ranked = _rt.rank_concepts(from_term, top_k=1)
        to_ranked = _rt.rank_concepts(to_term, top_k=1)
        start_id = from_ranked[0]["id"] if from_ranked else from_term.lower().replace(" ", "_")
        target_id = to_ranked[0]["id"] if to_ranked else to_term.lower().replace(" ", "_")
        return {
            "anchor_id": target_id,
            "score": 1.0,
            "related": ranked,
            "slots": {"intent": "roadmap_between", "start_id": start_id, "target_id": target_id},
            "scope": "yes",
            "route": "roadmap_between",
            "reason": "personalized_roadmap",
        }

    return None
