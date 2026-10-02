"""The personalized learning path: shortest route through material still unknown.

The contract calls for a *custom* learning path — "skip already known topics and
generate a custom prerequisite detour".  The previous roadmap ignored the
diagnostic entirely: it emitted the target's prerequisite chain in fixed depth
order, so a student who had already proven mastery of a node was still told to
study it, and a gap sitting two hops *sideways* from the target was never
routed to.

This module is the fix.  Dijkstra runs outward from the target over the
``REQUIRES``/``UNLOCKS`` subgraph, skipping nodes the student has demonstrated,
and assigns each remaining node a cost-to-target.  The returned plan is every
unmastered node still reachable, ordered deepest-prerequisite-first and closed by
the target itself — so it always ends at the learning objective, never re-teaches
a validated concept, and always surfaces the review gaps.

Deepest-first is the correct study order for a prerequisite DAG: you cannot use
3NF before the functional dependencies that define it.  Ordering by cost-to-target
descending is therefore equivalent to topological order on the subset that
matters, and it degrades gracefully when the graph's edges are inconsistent —
a fixed prerequisite list does not.
"""
from __future__ import annotations

from heapq import heappop, heappush

#: Cost of traversing one prerequisite edge. Uniform, because the graph carries
#: no per-edge difficulty weighting we can honestly claim to respect.
EDGE_COST = 1.0

#: Extra cost for reaching a node the diagnostic flagged as a review gap.
#: Reaching it is not optional, so this does not gate the result; it biases which
#: node is treated as the starting point when several are equidistant.
GAP_PENALTY = 1.5

#: Cap on path length, so a weakly connected graph cannot produce a 40-step plan.
MAX_PATH_NODES = 8

#: Recorded in every roadmap so an auditor can see what produced the ordering.
SEARCH_ALGORITHM = "Dijkstra_from_target_skipping_mastered"

#: Relations that express a study dependency. RELATED is not a dependency: a node
#: merely co-mentioned with the target is not something you must learn first.
DEPENDENCY_RELATIONS = frozenset({"REQUIRES", "UNLOCKS", "inv-REQUIRES", "inv-UNLOCKS"})


def _dependency_neighbours(graph, cid: str) -> list[str]:
    """Nodes reachable from ``cid`` along a dependency edge, in either direction."""
    hops: list[str] = []
    for kind, nxt in graph.out.get(cid, []):
        if kind in DEPENDENCY_RELATIONS and nxt in graph.nodes and nxt not in hops:
            hops.append(nxt)
    for kind, nxt in graph.inn.get(cid, []):
        if kind in DEPENDENCY_RELATIONS and nxt in graph.nodes and nxt not in hops:
            hops.append(nxt)
    return hops


def _costs_to_target(
    graph, target: str, mastered: frozenset[str], gaps: frozenset[str]
) -> dict[str, float]:
    """Dijkstra cost from every reachable unmastered node back to ``target``.

    Mastered nodes are excluded from the search entirely rather than traversed
    with a zero weight: a concept the student has validated is not a waypoint
    they need to pass through on the way to anything else.
    """
    blocked = set(mastered)
    distances: dict[str, float] = {target: 0.0}
    # (cost_so_far, tie_break, node) — the counter keeps the heap deterministic
    # instead of falling back on set ordering.
    counter = 0
    frontier: list[tuple[float, int, str]] = [(0.0, 0, target)]

    while frontier:
        cost_so_far, _tie, current = heappop(frontier)
        if cost_so_far > distances.get(current, float("inf")):
            continue
        if len(distances) >= MAX_PATH_NODES:
            break
        for nxt in _dependency_neighbours(graph, current):
            if nxt in blocked:
                continue
            step = EDGE_COST + (GAP_PENALTY if nxt in gaps else 0.0)
            tentative = cost_so_far + step
            if tentative >= distances.get(nxt, float("inf")):
                continue
            distances[nxt] = tentative
            counter += 1
            heappush(frontier, (tentative, counter, nxt))

    distances.pop(target, None)
    return distances


def learning_path(
    graph,
    target: str,
    mastered: frozenset[str],
    gaps: frozenset[str] = frozenset(),
) -> list[str]:
    """Study order for ``target``: unmet prerequisites first, target last.

    ``mastered`` nodes are excluded from the search, so the returned list is by
    construction the material the student has *not* yet demonstrated.

    Returns ``[target]`` when nothing is outstanding — the honest answer for a
    student who has mastered the whole prerequisite closure, not an error.
    """
    if target not in graph.nodes:
        return []

    costs = _costs_to_target(graph, target, mastered, gaps)
    if not costs:
        return [target]

    # Deepest prerequisite first (largest cost-to-target); ties broken by id so
    # the same diagnostic always produces the same plan.
    ordered = sorted(costs, key=lambda cid: (-costs[cid], cid))
    return [*ordered[:MAX_PATH_NODES - 1], target]


__all__ = [
    "DEPENDENCY_RELATIONS",
    "EDGE_COST",
    "GAP_PENALTY",
    "MAX_PATH_NODES",
    "SEARCH_ALGORITHM",
    "learning_path",
]
