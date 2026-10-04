"""Bounded, evidence-based learning state; no identity or external inference."""
from __future__ import annotations

from collections import deque
import math
import time

INITIAL_QUESTIONS = 3
MAX_QUESTIONS = 10
MAX_HOPS = 3
MAX_NODES = 24
HALF_LIFE_DAYS = 30
SECONDS_PER_DAY = 86400
MASTERY_THRESHOLD = 0.6
CONFIDENCE = {"high": 0.95, "medium": 0.75, "low": 0.35}
PREFERENCES = {
    "conceptual": {"definition", "theory"},
    "mathematical": {"metric", "theory"},
    "code": {"method", "technique", "tool"},
}
MISCONCEPTION_RELATIONS = frozenset({"contrasts_with", "variant_of", "improves_on"})


def neighborhood(graph, target: str) -> dict[str, int]:
    """Breadth-first prerequisite depths, with cycle and size bounds."""
    depths: dict[str, int] = {}
    queue = deque([(target, 0)])
    visited = {target}
    while queue and len(depths) < MAX_NODES:
        current, depth = queue.popleft()
        if depth >= MAX_HOPS:
            continue
        neighbors = [dst for kind, dst in graph.out.get(current, []) if kind == "REQUIRES"]
        neighbors += [src for kind, src in graph.inn.get(current, []) if kind == "UNLOCKS"]
        for cid in sorted(set(neighbors)):
            if cid in visited or cid not in graph.nodes or len(depths) >= MAX_NODES:
                continue
            visited.add(cid)
            depths[cid] = depth + 1
            queue.append((cid, depth + 1))
    return depths or {target: 0}


def update_mastery(
    node_id: str, correct: bool, confidence: str, previous: dict | None = None,
    now: float | None = None,
) -> dict:
    """Interpret correctness and reported confidence, without diagnosing misconceptions."""
    previous = previous or {}
    weight = CONFIDENCE[confidence] if correct else 0.0
    return {
        "node_id": node_id,
        "mastery_state": "mastered" if weight >= MASTERY_THRESHOLD else "review_gap",
        "confidence": weight,
        "reported_confidence": confidence,
        "last_verified": time.time() if now is None else now,
        "verification_count": int(previous.get("verification_count", 0)) + 1,
    }


def effective_mastery(record: dict, now: float | None = None) -> str:
    """Decay confidence, without scheduling repeated compulsory retests."""
    state = record.get("mastery_state", "missing")
    if state != "mastered":
        return state
    age = max(0.0, (time.time() if now is None else now) - record["last_verified"])
    weight = record["confidence"] * math.exp2(-age / (HALF_LIFE_DAYS * SECONDS_PER_DAY))
    return "mastered" if weight >= MASTERY_THRESHOLD else "fading"


def next_node(graph, session: dict) -> str | None:
    """Cover prerequisite hops first, then weak evidence; never target ten by default."""
    history, depths = session["history"], session["depths"]
    if len(history) >= MAX_QUESTIONS:
        return None
    asked = {row["concept_id"] for row in history}
    by_depth: dict[int, int] = {}
    for row in history:
        depth = depths[row["concept_id"]]
        by_depth[depth] = by_depth.get(depth, 0) + 1
    if len(history) >= INITIAL_QUESTIONS and set(by_depth) == set(depths.values()):
        verified = session["mastery"].values()
        if verified and all(effective_mastery(record) == "mastered" for record in verified):
            return None
    preferred = PREFERENCES[session["preference"]]
    unasked = [cid for cid in depths if cid not in asked]
    if unasked:
        return min(unasked, key=lambda cid: (
            by_depth.get(depths[cid], 0),
            -depths[cid],
            effective_mastery(session["mastery"].get(cid, {})) == "mastered",
            graph.nodes[cid].get("concept_type") not in preferred,
            cid,
        ))
    # One successful micro-verification suffices. Wrong answers are evidence of
    # gaps, not a reason to interrogate indefinitely.
    uncertain = [
        cid for cid, record in session["mastery"].items()
        if record["confidence"] > 0 and effective_mastery(record) != "mastered"
        and sum(row["concept_id"] == cid for row in history) < 2
    ]
    return uncertain[0] if uncertain else None


def misconception(graph, focus: str, selected_node: str, confidence: str, correct: bool) -> dict | None:
    """Explain a potential confusion only when an explicit graph relation supports it."""
    if correct or confidence != "high" or not selected_node:
        return None
    for left, right in ((focus, selected_node), (selected_node, focus)):
        for relation, dst in graph.out.get(left, []):
            if dst == right and relation.lower() in MISCONCEPTION_RELATIONS:
                return {
                    "possible": True,
                    "relation": relation,
                    "source": left,
                    "target": right,
                    "prompt": (
                        f"The graph relates {graph.label(left)} and {graph.label(right)} "
                        f"as {relation.lower()}. What distinguishes their definitions?"
                    ),
                }
    return None


def personalized_graph(graph, session: dict) -> dict:
    """Project only real neighborhood edges; unassessed nodes remain missing."""
    ids = set(session["depths"]) | {session["target"]}
    nodes = []
    for cid in sorted(ids):
        record = session["mastery"].get(cid, {})
        status = "target" if cid == session["target"] else effective_mastery(record)
        source = graph.cite_record(cid, "")
        nodes.append({
            "id": cid, "label": graph.label(cid), "name": graph.label(cid),
            "summary": graph.nodes[cid].get("summary", ""),
            "status": status, "role": "target" if cid == session["target"] else "prereq",
            "why": "Your selected target." if cid == session["target"] else (
                f"An indexed prerequisite at hop {session['depths'][cid]}; "
                + ("not yet assessed." if not record else f"diagnostic evidence: {status}.")
            ),
            **{key: source.get(key) for key in ("doc_id", "page_number", "url")},
        })
    edges = [
        {"source": src, "target": dst, "relation": kind}
        for src in sorted(ids) for kind, dst in graph.out.get(src, [])
        if dst in ids and kind in {"REQUIRES", "UNLOCKS"}
    ]
    return {"nodes": nodes, "edges": edges}
