"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import logging
from collections import deque
from typing import Any
from . import _deps as _rt  # noqa: F401

_LOGGER = logging.getLogger("archipelago.graph.subgraph")


def _ensure_weak_connectivity(
    target_id: str,
    selected_node_ids: list[str],
    edges: list[dict[str, Any]],
    concepts_data: dict[str, Any],
    min_nodes: int = 5,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Ensure all nodes are weakly connected to the component containing target_id."""
    adj: dict[str, set[str]] = {n: set() for n in selected_node_ids}
    for e in edges:
        u, v = e["from_id"], e["to_id"]
        if u in adj and v in adj:
            adj[u].add(v)
            adj[v].add(u)

    # BFS from target_id to find connected component
    visited: set[str] = set()
    queue = deque([target_id])
    visited.add(target_id)
    while queue:
        curr = queue.popleft()
        for nbr in adj.get(curr, []):
            if nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)

    disconnected = [n for n in selected_node_ids if n not in visited]
    if not disconnected:
        return selected_node_ids, edges

    bridged_nodes = list(visited)
    new_edges = list(edges)

    for d in disconnected:
        d_node = concepts_data.get(d) or {}
        d_rank = _rt._DIFFICULTY_RANK.get(d_node.get("difficulty", "intermediate"), 2)
        target_rank = _rt._DIFFICULTY_RANK.get(
            (concepts_data.get(target_id) or {}).get("difficulty", "intermediate"), 2
        )
        if d_rank <= target_rank:
            new_edges.append({"from_id": target_id, "to_id": d, "relation": "REQUIRES", "weight": 1.0})
        else:
            new_edges.append({"from_id": target_id, "to_id": d, "relation": "UNLOCKS", "weight": 1.0})
        bridged_nodes.append(d)

    return bridged_nodes, new_edges


def _resolve_kuzu_conn(kuzu_conn: Any | None) -> Any | None:
    """Return an explicit connection, else open one on the live graph database.

    The in-memory concept index carries no topology edges, so without a real
    Kùzu connection every neighborhood would come back empty.
    """
    if kuzu_conn is not None:
        return kuzu_conn
    try:
        import kuzu
        from archipelago.inference import state as st
        if getattr(st, "db", None) is None:
            return None
        return kuzu.Connection(st.db)
    except Exception as exc:
        _LOGGER.debug("subgraph kuzu connection unavailable: %s", exc)
        return None


def generate_bounded_subgraph(
    target_id: str,
    secondary_target_id: str | None = None,
    mode: str = "mode_c",
    max_nodes: int = 10,
    min_nodes: int = 5,
    concepts_data: dict[str, Any] | None = None,
    kuzu_conn: Any | None = None,
) -> _rt.BoundedSubgraph:
    """Generate a strictly bounded subgraph for query visualization and reasoning.

    Args:
        target_id: Primary concept ID or name.
        secondary_target_id: Optional secondary concept ID for Mode B.
        mode: "mode_a", "mode_b", or "mode_c".
        max_nodes: Upper bound on node count (default 10).
        min_nodes: Lower bound for curriculum / comparative (default 5).
        concepts_data: Optional dict mapping concept_id to metadata (defaults to st.CONCEPTS_DATA).
        kuzu_conn: Optional open Kuzu connection; defaults to the live graph.

    Returns:
        _rt.BoundedSubgraph with nodes, edges, target_ids, and metadata.
    """
    if concepts_data is None:
        from archipelago.inference import state as st
        concepts_data = st.CONCEPTS_DATA or {}

    kuzu_conn = _resolve_kuzu_conn(kuzu_conn)

    name_idx = _rt._build_name_to_id_index(concepts_data)

    real_target_id = _rt._resolve_id(target_id, name_idx, concepts_data)
    if not real_target_id:
        real_target_id = target_id

    # ── MODE A: Minimal 1-hop / Atomic Concept (<= 3 nodes) ────────────────
    if mode == "mode_a":
        selected_ids = [real_target_id]
        p_list = _rt._get_direct_prereqs(real_target_id, concepts_data, name_idx, kuzu_conn)
        u_list = _rt._get_direct_unlocks(real_target_id, concepts_data, name_idx, kuzu_conn)

        if p_list:
            selected_ids.append(p_list[0])
        if u_list and len(selected_ids) < 3:
            selected_ids.append(u_list[0])

        edges = _rt._induce_subgraph_edges(set(selected_ids), concepts_data, name_idx, kuzu_conn)
        nodes_out = []
        for cid in selected_ids:
            info = _rt._get_node_info(cid, concepts_data)
            role = "target" if cid == real_target_id else ("prereq" if cid in p_list else "unlock")
            nodes_out.append({**info, "role": role, "hop": 0 if cid == real_target_id else 1})

        return _rt.BoundedSubgraph(
            nodes=nodes_out,
            edges=edges,
            target_ids=[real_target_id],
            query_mode="mode_a",
            metadata={"description": "Minimal 1-hop atomic concept neighborhood"},
        )

    # ── MODE B: Comparative / Relational Path (5 to 10 nodes) ──────────────
    if mode == "mode_b":
        real_sec_id = _rt._resolve_id(secondary_target_id or "", name_idx, concepts_data)
        targets = [real_target_id]
        if real_sec_id and real_sec_id != real_target_id:
            targets.append(real_sec_id)

        path_nodes: list[str] = []
        if len(targets) == 2:
            src, dst = targets[0], targets[1]
            adj_all: dict[str, list[str]] = {}
            for cid in concepts_data:
                for p in _rt._get_direct_prereqs(cid, concepts_data, name_idx, kuzu_conn):
                    adj_all.setdefault(cid, []).append(p)
                    adj_all.setdefault(p, []).append(cid)
                for u in _rt._get_direct_unlocks(cid, concepts_data, name_idx, kuzu_conn):
                    adj_all.setdefault(cid, []).append(u)
                    adj_all.setdefault(u, []).append(cid)
                for r, _ in _rt._get_related_neighbors(cid, concepts_data, name_idx, kuzu_conn):
                    adj_all.setdefault(cid, []).append(r)
                    adj_all.setdefault(r, []).append(cid)

            q = deque([(src, [src])])
            visited = {src}
            while q:
                curr, path = q.popleft()
                if curr == dst:
                    path_nodes = path
                    break
                if len(path) > 6:
                    continue
                for nbr in adj_all.get(curr, []):
                    if nbr not in visited:
                        visited.add(nbr)
                        q.append((nbr, path + [nbr]))

        selected_ids = list(path_nodes) if path_nodes else list(targets)

        # Contextual bridge nodes to reach min_nodes
        if len(selected_ids) < min_nodes:
            for t in targets:
                for p in _rt._get_direct_prereqs(t, concepts_data, name_idx, kuzu_conn):
                    if p not in selected_ids:
                        selected_ids.append(p)
                        if len(selected_ids) >= max_nodes:
                            break
                if len(selected_ids) >= max_nodes:
                    break
                for u in _rt._get_direct_unlocks(t, concepts_data, name_idx, kuzu_conn):
                    if u not in selected_ids:
                        selected_ids.append(u)
                        if len(selected_ids) >= max_nodes:
                            break

        # Fallback backfill if still < min_nodes
        if len(selected_ids) < min_nodes:
            for uf in _rt._UNIVERSAL_FOUNDATIONS:
                if uf in concepts_data and uf not in selected_ids:
                    selected_ids.append(uf)
                    if len(selected_ids) >= min_nodes:
                        break

        # Prune if > max_nodes
        if len(selected_ids) > max_nodes:
            keep_set = set(targets)
            remaining = [x for x in selected_ids if x not in keep_set]
            selected_ids = list(targets) + remaining[: max_nodes - len(targets)]

        edges = _rt._induce_subgraph_edges(set(selected_ids), concepts_data, name_idx, kuzu_conn)
        selected_ids, edges = _ensure_weak_connectivity(
            real_target_id, selected_ids, edges, concepts_data, min_nodes=min_nodes
        )

        nodes_out = []
        for cid in selected_ids:
            info = _rt._get_node_info(cid, concepts_data)
            role = "target" if cid in targets else ("bridge" if cid in path_nodes else "context")
            nodes_out.append({**info, "role": role, "hop": 0 if cid in targets else 1})

        return _rt.BoundedSubgraph(
            nodes=nodes_out,
            edges=edges,
            target_ids=targets,
            query_mode="mode_b",
            metadata={"description": "Comparative cross-domain bridge subgraph"},
        )

    # ── MODE C: Deep Pedagogical / Curriculum Exploration (5 to 10 nodes) ──
    candidates: dict[str, dict[str, Any]] = {}

    candidates[real_target_id] = {
        "role": "target",
        "hop": 0,
        "priority": 1000,
    }

    p1_list = _rt._get_direct_prereqs(real_target_id, concepts_data, name_idx, kuzu_conn)
    for p in p1_list:
        if p != real_target_id:
            candidates[p] = {
                "role": "prereq",
                "hop": 1,
                "priority": 100,
            }

    u1_list = _rt._get_direct_unlocks(real_target_id, concepts_data, name_idx, kuzu_conn)
    for u in u1_list:
        if u != real_target_id and u not in candidates:
            candidates[u] = {
                "role": "unlock",
                "hop": 1,
                "priority": 70,
            }

    for p in p1_list:
        p2_list = _rt._get_direct_prereqs(p, concepts_data, name_idx, kuzu_conn)
        for p2 in p2_list:
            if p2 != real_target_id and p2 not in candidates:
                candidates[p2] = {
                    "role": "prereq",
                    "hop": 2,
                    "priority": 50,
                }

    if len(candidates) > max_nodes:
        def _candidate_score(item: tuple[str, dict[str, Any]]) -> float:
            cid, meta = item
            if meta["role"] == "target":
                return 10000.0
            base_prio = float(meta["priority"])
            node_info = _rt._get_node_info(cid, concepts_data)
            diff = node_info["difficulty"]
            diff_score = 15.0 if diff == "foundational" else (10.0 if diff == "intermediate" else 5.0)
            return base_prio + diff_score

        sorted_cand = sorted(candidates.items(), key=_candidate_score, reverse=True)
        candidates = dict(sorted_cand[:max_nodes])

    if len(candidates) < min_nodes:
        target_info = _rt._get_node_info(real_target_id, concepts_data)
        target_domain = target_info.get("domain", "")

        for cid, data in concepts_data.items():
            if cid not in candidates and (data.get("difficulty") or "").lower() == "foundational":
                if target_domain and data.get("domain") == target_domain:
                    candidates[cid] = {"role": "prereq", "hop": 2, "priority": 25}
                    if len(candidates) >= min_nodes:
                        break

        if len(candidates) < min_nodes:
            for uf in _rt._UNIVERSAL_FOUNDATIONS:
                if uf in concepts_data and uf not in candidates:
                    candidates[uf] = {"role": "prereq", "hop": 2, "priority": 20}
                    if len(candidates) >= min_nodes:
                        break

        if len(candidates) < min_nodes:
            for cid, data in concepts_data.items():
                if cid not in candidates and (data.get("difficulty") or "").lower() == "foundational":
                    candidates[cid] = {"role": "prereq", "hop": 2, "priority": 15}
                    if len(candidates) >= min_nodes:
                        break

    selected_ids = list(candidates.keys())
    edges = _rt._induce_subgraph_edges(set(selected_ids), concepts_data, name_idx, kuzu_conn)

    selected_ids, edges = _ensure_weak_connectivity(
        real_target_id, selected_ids, edges, concepts_data, min_nodes=min_nodes
    )

    nodes_out = []
    for cid in selected_ids:
        info = _rt._get_node_info(cid, concepts_data)
        meta = candidates.get(cid, {"role": "context", "hop": 1})
        nodes_out.append({
            **info,
            "role": meta["role"],
            "hop": meta.get("hop", 1),
        })

    return _rt.BoundedSubgraph(
        nodes=nodes_out,
        edges=edges,
        target_ids=[real_target_id],
        query_mode="mode_c",
        metadata={
            "description": "Deep pedagogical curriculum exploration bounded subgraph",
            "hop_depth": 2,
        },
    )
