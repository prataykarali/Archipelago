"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from typing import Any
from . import _deps as _rt  # noqa: F401


def execute_adaptive_step(
    payload: dict[str, Any],
    concepts_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute an adaptive leap-back / skip-list step in the diagnostic quiz (5-10 MCQs max).

    Algorithm:
    - Target node X, foundational leaf R.
    - Prerequisite sequence: [leaf_0, ..., P_{k-2}, P_{k-1}, Y, X]
    - If user answers Y correctly (tick): advance towards X (3 consecutive ticks unlocks X).
    - If user answers incorrectly: LEAP BACK (skip stride = 2 hops towards leaf R).
    - Session bounds: early exit on 3 ticks, or 5-10 questions max.
    """
    if concepts_data is None:
        from archipelago.inference import state as st
        concepts_data = st.CONCEPTS_DATA or {}

    target_id = str(payload.get("target_concept") or "low_rank_adaptation").strip().lower().replace(" ", "_")
    current_cid = str(payload.get("current_concept") or "").strip().lower().replace(" ", "_")
    user_choice = str(payload.get("user_choice") or "").strip().upper()
    history = list(payload.get("history") or [])
    consecutive_ticks = int(payload.get("consecutive_ticks") or 0)
    chain = list(payload.get("chain") or [])

    if not chain:
        chain = _rt.get_prerequisite_chain(target_id, concepts_data)

    prereq_chain = [c for c in chain if c != target_id]
    if not prereq_chain:
        prereq_chain = ["neural_network", "transformer", "fine_tuning"]

    # Verify user choice for current_cid
    current_mcq = payload.get("current_mcq") or _rt.generate_single_mcq_on_the_spot(current_cid, concepts_data, q_index=len(history) + 1)
    correct_opt = current_mcq.get("correct_option", "A").upper().strip()
    is_tick = (user_choice == correct_opt)

    c_node = concepts_data.get(current_cid) or {}
    c_name = current_mcq.get("concept_name") or c_node.get("name") or current_cid.replace("_", " ").title()

    step_record = {
        "mcq_id": current_mcq.get("id", f"mcq_{current_cid}_{len(history) + 1}"),
        "concept_id": current_cid,
        "concept_name": c_name,
        "question": current_mcq.get("question", ""),
        "options": current_mcq.get("options", {}),
        "user_answer": user_choice,
        "correct_answer": correct_opt,
        "is_correct": is_tick,
        "explanation": current_mcq.get("explanation", ""),
        "citation": current_mcq.get("citation", ""),
        "difficulty": current_mcq.get("difficulty", "intermediate"),
    }
    history.append(step_record)

    if is_tick:
        consecutive_ticks += 1
    else:
        consecutive_ticks = 0

    total_asked = len(history)

    # Termination check:
    # 1. 3 consecutive ticks -> foundations mastered, target unlocked!
    mastered = list(payload.get("mastered") or [])
    gaps = list(payload.get("gaps") or [])
    eval_stack = list(payload.get("eval_stack") or [])

    if is_tick:
        if current_cid not in mastered:
            mastered.append(current_cid)
    else:
        if current_cid not in gaps:
            gaps.append(current_cid)
        # Traverse backward along REQUIRES: fetch upstream dependencies of C
        upstream_nodes = [
            p.get("id") if isinstance(p, dict) else str(p).lower().replace(" ", "_")
            for p in (c_node.get("prerequisites") or [])
        ]
        for u in upstream_nodes:
            if u and u != current_cid and u != target_id and u not in mastered and u not in gaps and u not in eval_stack:
                eval_stack.append(u)

    # 1. 3 consecutive ticks -> foundations mastered, target unlocked!
    # 2. total_asked >= 10 -> hard ceiling
    # 3. total_asked >= 5 and all key prereqs diagnosed
    # 4. eval_stack exhausted
    is_complete = False
    completion_reason = ""

    if consecutive_ticks >= 3:
        is_complete = True
        completion_reason = "3_consecutive_ticks_mastered"
    elif total_asked >= 10:
        is_complete = True
        completion_reason = "max_questions_reached"
    elif total_asked >= 5 and len(set(h["concept_id"] for h in history)) >= len(prereq_chain):
        is_complete = True
        completion_reason = "full_chain_evaluated"
    elif eval_stack and len([x for x in eval_stack if x not in mastered and x not in gaps]) == 0 and total_asked >= 3:
        is_complete = True
        completion_reason = "eval_stack_exhausted"

    if is_complete:
        all_mcqs = [
            {
                "id": h.get("mcq_id") or f"mcq_{h.get('concept_id', 'concept')}_{idx + 1}",
                "concept_id": h.get("concept_id", ""),
                "concept_name": h.get("concept_name") or str(h.get("concept_id", "Concept")).replace("_", " ").title(),
                "question": h.get("question", ""),
                "options": h.get("options", {}),
                "correct_option": h.get("correct_answer") or h.get("correct_option", "A"),
                "explanation": h.get("explanation", ""),
                "citation": h.get("citation", ""),
                "difficulty": h.get("difficulty", "intermediate"),
            }
            for idx, h in enumerate(history)
        ]
        user_answers = {
            (h.get("mcq_id") or f"mcq_{h.get('concept_id', 'concept')}_{idx + 1}"): h.get("user_answer") or h.get("user_choice", "A")
            for idx, h in enumerate(history)
        }
        eval_res = _rt.evaluate_diagnostic_mcqs(all_mcqs, user_answers, target_concept_id=target_id, concepts_data=concepts_data)

        # Find final correct question for celebration swipe
        final_correct_q = None
        if is_tick:
            final_correct_q = step_record
        else:
            for prev_h in reversed(history):
                if prev_h.get("is_correct"):
                    final_correct_q = prev_h
                    break

        p_graph = eval_res.get("personalized_graph", {})

        return {
            "status": "complete",
            "completed": True,
            "completion_reason": completion_reason,
            "is_tick": is_tick,
            "current_record": step_record,
            "final_correct_question": final_correct_q,
            "consecutive_ticks": consecutive_ticks,
            "total_asked": total_asked,
            "history": history,
            "chain": chain,
            "mastered": mastered,
            "gaps": gaps,
            "evaluation": eval_res,
            "personalized_graph": p_graph,
            "rendered_graph": {
                "nodes": p_graph.get("nodes", []),
                "edges": p_graph.get("edges", []),
            },
        }

    # Not complete: compute next concept via DPB Stack or Leap-Back Skip-List
    next_cid = None
    while eval_stack:
        candidate = eval_stack.pop()
        if candidate not in mastered and candidate not in gaps:
            next_cid = candidate
            break

    if not next_cid:
        try:
            curr_idx = prereq_chain.index(current_cid)
        except ValueError:
            curr_idx = len(prereq_chain) - 1

        tested_cids = {h["concept_id"] for h in history}

        if is_tick:
            stride_action = "advance"
            next_idx = curr_idx + 1
            while next_idx < len(prereq_chain) and prereq_chain[next_idx] in tested_cids:
                next_idx += 1
            if next_idx >= len(prereq_chain):
                untested = [c for c in prereq_chain if c not in tested_cids]
                next_cid = untested[-1] if untested else prereq_chain[-1]
            else:
                next_cid = prereq_chain[next_idx]
        else:
            stride_action = "leap_back"
            next_idx = max(0, curr_idx - 2)
            while next_idx >= 0 and prereq_chain[next_idx] in tested_cids:
                next_idx -= 1
            if next_idx < 0:
                untested = [c for c in prereq_chain if c not in tested_cids]
                next_cid = untested[0] if untested else prereq_chain[0]
            else:
                next_cid = prereq_chain[next_idx]
    else:
        stride_action = "advance" if is_tick else "traverse_backward"

    next_mcq = _rt.generate_single_mcq_on_the_spot(next_cid, concepts_data, q_index=total_asked + 1)

    return {
        "status": "in_progress",
        "completed": False,
        "is_tick": is_tick,
        "stride_action": stride_action,
        "current_record": step_record,
        "consecutive_ticks": consecutive_ticks,
        "total_asked": total_asked,
        "history": history,
        "chain": chain,
        "eval_stack": eval_stack,
        "mastered": mastered,
        "gaps": gaps,
        "next_concept": next_cid,
        "next_concept_name": next_mcq.get("concept_name", next_cid.replace("_", " ").title()),
        "next_question": next_mcq,
    }


def validate_mcq_submission(
    mcqs: list[dict[str, Any]],
    user_answers: dict[str, Any],
    target_concept_id: str,
) -> tuple[bool, str, dict[str, str]]:
    """Validate submitted MCQ payload against anti-tamper and structural constraints.

    Args:
        mcqs: Active list of MCQ dicts presented to the user.
        user_answers: Mapping of question identifiers to submitted option strings.
        target_concept_id: Anchor concept under assessment.

    Returns:
        tuple (is_valid, error_message, sanitized_answers_dict)
    """
    if not isinstance(target_concept_id, str) or not target_concept_id.strip():
        return False, "Target concept ID must be a non-empty string", {}
    if len(target_concept_id) > 100:
        return False, "Target concept ID exceeds maximum allowed length", {}
    if not isinstance(user_answers, dict):
        return False, "Submitted answers must be a JSON dictionary", {}
    if len(user_answers) > 10:
        return False, "Answer limit exceeded (maximum 10 questions per submission)", {}

    valid_mcq_ids = {m.get("id") for m in mcqs if isinstance(m, dict) and m.get("id")}
    valid_concept_ids = {m.get("concept_id") for m in mcqs if isinstance(m, dict) and m.get("concept_id")}
    valid_options = {"A", "B", "C", "D"}

    sanitized: dict[str, str] = {}
    for key, val in user_answers.items():
        if not isinstance(key, (str, int)):
            continue
        key_str = str(key).strip()
        is_known = (
            key_str in valid_mcq_ids
            or key_str in valid_concept_ids
            or key_str.isdigit()
            or not valid_mcq_ids
        )
        if not is_known:
            continue
        if isinstance(val, str):
            choice = val.strip().upper()
            if choice in valid_options:
                sanitized[key_str] = choice

    return True, "", sanitized
