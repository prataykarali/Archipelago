"""Diagnostic checkpoints and the adaptive personalized-QnA flow.

One concern: the ``Personalized`` learning path — building prerequisite MCQs,
scoring ticks and gaps, and emitting the personalized graph for the chat UI.
"""

from __future__ import annotations

from itertools import pairwise

from .nodes import node_public
from .pathfinder import SEARCH_ALGORITHM, learning_path

# Diagnostic / adaptive-quiz caps.
MCQ_DISTRACTORS = 3
MCQ_MAX_QUESTIONS = 6
MCQ_OPTION_CHARS = 220
MASTERY_TICKS = 3
MIN_DIAGNOSTIC_QUESTIONS = 3
# How long a roadmap step summary may be.
ROADMAP_STEP_CHARS = 160
# Distractors are drawn from this many top-ranked neighbours.
DISTRACTOR_POOL = 8


def diagnostic_intro(engine, cid: str) -> str:
    """Introduce the short adaptive prerequisite diagnostic."""
    graph = engine.graph
    pres = graph.prereqs(cid, 2)[:4] or [cid]
    names = ", ".join(graph.label(p) for p in pres)
    return (
        f"**Diagnostic checkpoint for {graph.label(cid)}.** "
        "Full text generation is paused. Answer three to six checks on the prerequisite nodes, "
        f"then the personalized graph is drawn from your ticks and gaps.\n\n"
        f"Upstream nodes in the checkpoint: {names}.\n\n"
        "Use **Yes, Start Diagnostic** under this reply to take the four-option checks."
    )


def mcq_for(engine, concept_id: str, slot: int = 0) -> dict:
    """Build one diagnostic MCQ for ``concept_id`` at prerequisite slot ``slot``."""
    graph = engine.graph
    if concept_id not in graph.nodes:
        concept_id = next(iter(graph.nodes))
    chain = [*list(reversed(graph.prereqs(concept_id, 2)[:3])), concept_id]
    # Unique, keep order.
    seen = []
    for cid in chain:
        if cid not in seen:
            seen.append(cid)
    chain = seen or [concept_id]
    focus = chain[min(slot, len(chain) - 1)]
    node = graph.nodes[focus]
    summary = (node.get("summary") or graph.label(focus)).strip()
    distractor_ids = [
        cid for _score, cid in graph.rank(graph.label(focus), DISTRACTOR_POOL) if cid != focus
    ][:MCQ_DISTRACTORS]
    while len(distractor_ids) < MCQ_DISTRACTORS:
        extra = next(cid for cid in graph.nodes if cid not in distractor_ids and cid != focus)
        distractor_ids.append(extra)
    options = {
        "A": summary[:MCQ_OPTION_CHARS],
        "B": (graph.nodes[distractor_ids[0]].get("summary") or "Unrelated catalog node.")[
            :MCQ_OPTION_CHARS
        ],
        "C": (graph.nodes[distractor_ids[1]].get("summary") or "Unrelated catalog node.")[
            :MCQ_OPTION_CHARS
        ],
        "D": (graph.nodes[distractor_ids[2]].get("summary") or "Unrelated catalog node.")[
            :MCQ_OPTION_CHARS
        ],
    }
    question_stems = (
        "Which statement defines {}?",
        "Which explanation best captures the intuition behind {}?",
        "Which indexed description would you use when applying {}?",
        "Which prerequisite description supports {}?",
        "Which account best explains the mechanism of {}?",
        "Which statement best connects {} to its prerequisites?",
    )
    return {
        "concept_id": focus,
        "concept_name": graph.label(focus),
        "difficulty": node.get("difficulty") or "intermediate",
        "question": question_stems[min(slot, MCQ_MAX_QUESTIONS - 1)].format(graph.label(focus)),
        "options": options,
        "correct_option": "A",
        "explanation": summary,
        "citation": graph.citation(focus),
        "chain": chain,
    }


def diagnostic_payload(engine, concept_id: str) -> dict:
    """Full diagnostic checkpoint payload for the personalized-QnA flow."""
    graph = engine.graph
    if concept_id not in graph.nodes:
        hits = graph.phrase_hits(concept_id.replace("_", " "))
        concept_id = hits[0] if hits else next(iter(graph.nodes))
    first = mcq_for(engine, concept_id, 0)
    chain = first["chain"]
    return {
        "success": True,
        "available": True,
        "target_concept": concept_id,
        "target_label": graph.label(concept_id),
        "chain": chain,
        "prereq_chain": chain[:-1],
        "immediate_prerequisite": chain[-2] if len(chain) > 1 else concept_id,
        "initial_question": first,
        "mcqs": [mcq_for(engine, concept_id, i) for i in range(min(MCQ_MAX_QUESTIONS, len(chain)))],
    }


def _roadmap_step(graph, cid: str) -> dict:
    src = graph.cite_record(cid)
    page = src.get("page_number")
    return {
        "id": cid,
        "name": graph.label(cid),
        "summary": (graph.nodes[cid].get("summary") or "")[:ROADMAP_STEP_CHARS],
        "doc_id": src.get("doc_id") or "",
        "page_number": page,
        "printed_page": page,
        "url": src.get("url") or "",
    }


def _personalized_roadmap(graph, target: str, mastered_ids: list[str], gap_ids: list[str]) -> dict:
    """Roadmap ordered by shortest path through *unmastered* material.

    The chain is the static prerequisite order; this is the personalised one.
    Nodes the student has already passed are excluded from the search, so the
    plan never re-teaches a validated concept, and review gaps carry a penalty so
    the route consolidates them instead of bypassing them.
    """
    mastered = frozenset(mastered_ids)
    gaps = frozenset(gap_ids)
    order = learning_path(graph, target, mastered, gaps)
    return {
        "algorithm": SEARCH_ALGORITHM,
        "skipped_mastered": [cid for cid in mastered if cid != target],
        "hops": max(len(order) - 1, 0),
        "steps": [_roadmap_step(graph, cid) for cid in order if cid in graph.nodes],
    }


def adaptive_step(engine, body: dict) -> dict:
    """Advance one adaptive-quiz step and return the personalized graph."""
    graph = engine.graph
    target = body.get("target_concept") or ""
    if target not in graph.nodes:
        target = next(iter(graph.nodes))
    current = body.get("current_concept") or target
    mcq = body.get("current_mcq") or mcq_for(engine, target, 0)
    choice = str(body.get("user_choice") or "").upper()
    correct = str(mcq.get("correct_option") or "A").upper()
    is_tick = choice == correct
    ticks = int(body.get("consecutive_ticks") or 0)
    ticks = ticks + 1 if is_tick else 0
    history = list(body.get("history") or [])
    history.append(
        {
            "concept_id": mcq.get("concept_id") or current,
            "is_correct": is_tick,
            "choice": choice,
        }
    )
    asked = len(history)
    assessed_ids = list(dict.fromkeys(row["concept_id"] for row in history))
    mastered_ids = [
        cid
        for cid in assessed_ids
        if all(row["is_correct"] for row in history if row["concept_id"] == cid)
    ]
    gap_ids = [
        cid
        for cid in assessed_ids
        if any(not row["is_correct"] for row in history if row["concept_id"] == cid)
    ]
    correct_count = sum(1 for row in history if row.get("is_correct"))
    completed = asked >= MIN_DIAGNOSTIC_QUESTIONS and (
        correct_count >= MASTERY_TICKS or asked >= MCQ_MAX_QUESTIONS
    )
    stride = "advance" if is_tick else "leap_back"
    next_q = None
    next_concept = current
    if not completed:
        slot = min(asked, MCQ_MAX_QUESTIONS - 1)
        next_q = mcq_for(engine, target, slot)
        next_concept = next_q["concept_id"]
    # Include every prerequisite in the computed path, plus assessed concepts.
    roadmap = _personalized_roadmap(graph, target, mastered_ids, gap_ids)
    curriculum_order = [*mastered_ids, *[step["id"] for step in roadmap["steps"]], *gap_ids]
    ordered_ids = list(
        dict.fromkeys(cid for cid in curriculum_order if cid in graph.nodes and cid != target)
    )
    ordered_ids.append(target)
    nodes = []
    first_unmastered = next((cid for cid in ordered_ids if cid not in mastered_ids), target)
    for cid in ordered_ids:
        pub = node_public(graph.nodes[cid])
        src = graph.cite_record(cid)
        concept_answers = [row["is_correct"] for row in history if row["concept_id"] == cid]
        concept_state = (
            "not tested"
            if not concept_answers
            else "mastered"
            if all(concept_answers)
            else "missing"
            if not any(concept_answers)
            else "partially understood"
        )
        status = (
            "MASTERED"
            if cid in mastered_ids
            else "CURRENT"
            if cid == first_unmastered
            else "MISSING"
            if cid in gap_ids
            else "UPCOMING"
        )
        pub.update(
            {
                "status": status,
                "concept_state": concept_state,
                "missing": cid in gap_ids,
                "role": "target" if cid == target else "prereq",
                "doc_id": src.get("doc_id") or "",
                "page_number": src.get("page_number"),
                "printed_page": src.get("page_number"),
                "url": src.get("url") or "",
            }
        )
        nodes.append(pub)
    edges = [
        {
            "from_id": source,
            "to_id": destination,
            "source": source,
            "target": destination,
            "relation": "NEXT_STEP",
        }
        for source, destination in pairwise(ordered_ids)
    ]
    evaluation = {
        "target_concept": target,
        "baseline_concept": graph.label(mastered_ids[-1]) if mastered_ids else "None",
        "score": f"{correct_count}/{len(history)}",
        "passed": correct_count >= MASTERY_TICKS,
        "full_score": correct_count == asked,
        "zero_score": not mastered_ids,
        "personalized_graph": {"nodes": nodes, "edges": edges},
        "roadmap": roadmap,
    }
    return {
        "is_tick": is_tick,
        "current_record": {"correct_answer": correct, "concept_id": mcq.get("concept_id")},
        "consecutive_ticks": ticks,
        "history": history,
        "completed": completed,
        "completion_reason": (
            "three_correct_mastered"
            if completed and correct_count >= MASTERY_TICKS
            else ("six_question_checkpoint" if completed else "")
        ),
        "total_asked": asked,
        "stride_action": stride,
        "next_concept": next_concept,
        "next_question": next_q,
        "personalized_graph": evaluation["personalized_graph"],
        "evaluation": evaluation,
    }
