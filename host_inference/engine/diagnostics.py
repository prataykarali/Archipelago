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
MCQ_MAX_QUESTIONS = 4
MCQ_OPTION_CHARS = 220
MASTERY_TICKS = 3
CHECKPOINT_QUESTIONS = 4
MIN_DIAGNOSTIC_QUESTIONS = 3
# How long a roadmap step summary may be.
ROADMAP_STEP_CHARS = 160
# Distractors are drawn from this many top-ranked neighbours.
DISTRACTOR_POOL = 8


def diagnostic_intro(engine, cid: str) -> str:
    """The 'answer four checks first' preamble shown before the quiz."""
    graph = engine.graph
    pres = graph.prereqs(cid, 2)[:4] or [cid]
    names = ", ".join(graph.label(p) for p in pres)
    return (
        f"**Diagnostic checkpoint for {graph.label(cid)}.** "
        "Full text generation is paused. Answer the four checks on the prerequisite nodes, "
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
    return {
        "concept_id": focus,
        "concept_name": graph.label(focus),
        "difficulty": node.get("difficulty") or "intermediate",
        "question": f"Which statement matches the indexed catalog definition of {graph.label(focus)}?",
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
    page = src.get("page_number") or 1
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
    mastered_ids = [row["concept_id"] for row in history if row.get("is_correct")]
    gap_ids = [row["concept_id"] for row in history if not row.get("is_correct")]
    completed = asked >= MIN_DIAGNOSTIC_QUESTIONS and (
        ticks >= MASTERY_TICKS or asked >= CHECKPOINT_QUESTIONS
    )
    stride = "advance" if is_tick else "leap_back"
    next_q = None
    next_concept = current
    if not completed:
        slot = min(asked, 3)
        next_q = mcq_for(engine, target, slot)
        next_concept = next_q["concept_id"]
    nodes = []
    for cid in dict.fromkeys(mastered_ids):
        if cid in graph.nodes and cid != target:
            pub = node_public(graph.nodes[cid])
            src = graph.cite_record(cid)
            pub.update(
                {
                    "status": "mastered",
                    "role": "prereq",
                    "doc_id": src.get("doc_id") or "",
                    "page_number": src.get("page_number") or 1,
                    "printed_page": src.get("page_number") or 1,
                    "url": src.get("url") or "",
                }
            )
            nodes.append(pub)
    for cid in dict.fromkeys(gap_ids):
        if cid in graph.nodes and cid != target and cid not in mastered_ids:
            pub = node_public(graph.nodes[cid])
            src = graph.cite_record(cid)
            pub.update(
                {
                    "status": "review_gap",
                    "role": "prereq",
                    "doc_id": src.get("doc_id") or f"/library?book={cid}",
                    "page_number": src.get("page_number") or 1,
                    "printed_page": src.get("page_number") or 1,
                    "url": src.get("url") or "",
                }
            )
            nodes.append(pub)
    target_pub = node_public(graph.nodes[target])
    target_src = graph.cite_record(target)
    target_pub.update(
        {
            "status": "unlocked" if ticks >= MASTERY_TICKS else "target",
            "role": "target",
            "doc_id": target_src.get("doc_id") or "",
            "page_number": target_src.get("page_number") or 1,
            "printed_page": target_src.get("page_number") or 1,
            "url": target_src.get("url") or "",
        }
    )
    nodes.append(target_pub)
    # A roadmap has one next step per node. Use the computed learning order,
    # then include any assessed prerequisite that the shortest path omitted.
    roadmap = _personalized_roadmap(graph, target, mastered_ids, gap_ids)
    by_id = {node["id"]: node for node in nodes}
    curriculum_order = mcq_for(engine, target, 0)["chain"][:-1]
    curriculum_order.extend(step["id"] for step in roadmap["steps"])
    curriculum_order.extend(by_id)
    ordered_ids = list(
        dict.fromkeys(cid for cid in curriculum_order if cid in by_id and cid != target)
    )
    ordered_ids.append(target)
    nodes = [by_id[cid] for cid in ordered_ids]
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
    correct_count = sum(1 for row in history if row.get("is_correct"))
    evaluation = {
        "target_concept": target,
        "baseline_concept": graph.label(mastered_ids[-1]) if mastered_ids else "None",
        "score": f"{correct_count}/{len(history)}",
        "passed": ticks >= MASTERY_TICKS,
        "full_score": ticks >= MASTERY_TICKS,
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
            "3_consecutive_ticks_mastered"
            if ticks >= MASTERY_TICKS
            else ("four_question_checkpoint" if completed else "")
        ),
        "total_asked": asked,
        "stride_action": stride,
        "next_concept": next_concept,
        "next_question": next_q,
        "personalized_graph": evaluation["personalized_graph"],
        "evaluation": evaluation,
    }
