"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from typing import Any
from . import _deps as _rt  # noqa: F401


def evaluate_diagnostic_mcqs(
    mcqs: list[dict[str, Any]],
    user_answers: dict[str, str],
    target_concept_id: str | None = None,
    concepts_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate submitted MCQ answers, score prerequisite mastery, and build personalized DAG.

    Args:
        mcqs: List of MCQ dicts previously generated.
        user_answers: Mapping of mcq_id or question index -> chosen letter ('A', 'B', 'C', or 'D').
        target_concept_id: The target concept being studied.
        concepts_data: Optional concept data dictionary.

    Returns:
        Evaluation dictionary with score, score_pct, passed (>= 80%), zero_score, full_score,
        mastered_concepts, gap_concepts, baseline_concept, details, and personalized_graph.
    """
    if concepts_data is None:
        from archipelago.inference import state as st
        concepts_data = st.CONCEPTS_DATA or {}

    t_id = str(target_concept_id or "").strip()

    # Input validation and anti-tamper
    is_valid, err_msg, sanitized_answers = _rt.validate_mcq_submission(mcqs, user_answers, t_id)
    if not is_valid:
        return {
            "success": False,
            "error": err_msg,
            "score": "0/0",
            "score_pct": 0.0,
            "passed": False,
            "zero_score": True,
            "full_score": False,
            "mastered_concepts": [],
            "gap_concepts": [],
            "details": [],
            "personalized_graph": {"nodes": [], "edges": []},
        }

    if not mcqs:
        return {
            "success": False,
            "error": "No MCQs provided for evaluation",
            "score": "0/0",
            "score_pct": 0.0,
            "passed": False,
            "zero_score": True,
            "full_score": False,
            "mastered_concepts": [],
            "gap_concepts": [],
            "details": [],
            "personalized_graph": {"nodes": [], "edges": []},
        }

    total = len(mcqs)
    correct_count = 0
    mastered: list[str] = []
    gaps: list[str] = []
    details: list[dict[str, Any]] = []

    for idx, mcq in enumerate(mcqs, 1):
        mcq_id = mcq.get("id", f"q_{idx}")
        cid = mcq.get("concept_id", "")
        cname = mcq.get("concept_name", cid)
        correct = (mcq.get("correct_option") or "A").upper().strip()

        # Extract user answer from dictionary by mcq_id, idx, or concept_id
        user_ans = (
            sanitized_answers.get(mcq_id)
            or sanitized_answers.get(str(idx))
            or sanitized_answers.get(cid)
            or ""
        ).upper().strip()

        is_correct = bool(user_ans and user_ans == correct)
        if is_correct:
            correct_count += 1
            mastered.append(cname)
        else:
            gaps.append(cname)

        c_node = concepts_data.get(cid) or {}
        sources = c_node.get("sources") or []
        first_src = sources[0] if sources and isinstance(sources[0], dict) else {}
        doc_id = first_src.get("doc_id") or ""
        page_num = first_src.get("page_number") or 1
        printed_page = first_src.get("printed_page") or page_num

        details.append({
            "mcq_id": mcq_id,
            "concept_id": cid,
            "concept_name": cname,
            "user_answer": user_ans or "Unanswered",
            "correct_answer": correct,
            "is_correct": is_correct,
            "explanation": mcq.get("explanation", ""),
            "citation": mcq.get("citation", ""),
            "doc_id": doc_id,
            "page_number": page_num,
            "printed_page": printed_page,
        })

    score_pct = round((correct_count / total) * 100.0, 1) if total else 0.0
    passed = score_pct >= 80.0
    zero_score = (correct_count == 0)
    full_score = (correct_count == total and total > 0)

    # Determine recommended baseline concept
    baseline = None
    if mastered:
        baseline = mastered[-1]
    elif gaps:
        baseline = gaps[0]
    else:
        baseline = t_id

    # Construct DAG-verified personalized graph topology
    pers_graph = _rt.build_personalized_graph_dag(
        target_concept_id=t_id,
        mastered_concepts=mastered,
        gap_concepts=gaps,
        concepts_data=concepts_data,
        eval_details=details,
    )

    # Compute step-by-step roadmap
    roadmap: dict[str, Any] = {"hops": 0, "steps": [], "markdown": ""}
    try:
        from archipelago.inference.curriculum import find_roadmap_between
        baseline_id = baseline.lower().replace(" ", "_") if baseline else t_id
        for k, v in concepts_data.items():
            if v.get("name") == baseline or v.get("label") == baseline:
                baseline_id = k
                break
        roadmap = find_roadmap_between(baseline_id, t_id, max_hops=6)
    except Exception as exc:
        roadmap = {"hops": 0, "steps": [], "markdown": "", "error": str(exc)}

    t_name = (concepts_data.get(t_id) or {}).get("name") or t_id.replace("_", " ").title()
    if full_score:
        remediation_msg = (
            f"Prerequisite mastery confirmed (Score: {correct_count}/{total}, 100%). "
            f"All foundational requirements for {t_name} are met! You can advance directly to core mastery and downstream applications."
        )
    elif zero_score:
        remediation_msg = (
            f"Foundational review suggested (Score: {correct_count}/{total}, 0%). "
            f"Gaps detected across all upstream prerequisites: {', '.join(gaps)}. "
            f"Archipelago has constructed a foundational remediation path starting at {baseline} with direct literature deep-links."
        )
    else:
        remediation_msg = (
            f"Targeted review suggested (Score: {correct_count}/{total}, {score_pct}%). "
            f"Mastered: {', '.join(mastered) or 'None'}. Gaps to review: {', '.join(gaps) or 'None'}. "
            f"Starting baseline: {baseline}."
        )

    return {
        "success": True,
        "score": f"{correct_count}/{total}",
        "score_pct": score_pct,
        "passed": passed,
        "zero_score": zero_score,
        "full_score": full_score,
        "mastered_concepts": mastered,
        "gap_concepts": gaps,
        "baseline_concept": baseline,
        "target_concept": t_id,
        "remediation_message": remediation_msg,
        "details": details,
        "personalized_graph": pers_graph,
        "roadmap": roadmap,
    }
