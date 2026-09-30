"""Bounded Subgraph Generator for Archipelago.

Enforces strict bounded subgraph sizes (5 to 10 nodes for Mode C / Mode B,
and <= 3 nodes for Mode A) to prevent overwhelming multi-hop graph dumps.
Includes pruning by pedagogical relevance, backfilling with foundational
prerequisites, and weak connectivity guarantees.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
import hashlib
from typing import Any


@dataclass
class SubgraphNode:
    id: str
    name: str
    label: str
    difficulty: str  # "foundational" | "intermediate" | "advanced" | "expert"
    summary: str
    role: str        # "target" | "prereq" | "unlock" | "bridge" | "context"
    domain: str = ""
    hop: int = 0     # 0 for target, 1 for 1-hop, 2 for 2-hop

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubgraphEdge:
    from_id: str
    to_id: str
    relation: str    # "REQUIRES" | "UNLOCKS" | "BRIDGES" | "RELATED"
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoundedSubgraph:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    target_ids: list[str]
    query_mode: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "target_ids": self.target_ids,
            "query_mode": self.query_mode,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "metadata": self.metadata,
        }


_DIFFICULTY_RANK: dict[str, int] = {
    "foundational": 1,
    "intermediate": 2,
    "advanced": 3,
    "expert": 4,
}

_UNIVERSAL_FOUNDATIONS = [
    "linear_algebra",
    "matrix_multiplication",
    "calculus",
    "partial_derivative",
    "probability_distribution",
    "vector",
    "gradient_descent",
    "loss_function",
    "neural_network",
    "activation_function",
]


def _normalize_id(name_or_id: str) -> str:
    if not name_or_id:
        return ""
    return name_or_id.lower().strip().replace("-", "_").replace(" ", "_")


def _build_name_to_id_index(concepts_data: dict[str, Any]) -> dict[str, str]:
    idx: dict[str, str] = {}
    for cid, data in concepts_data.items():
        norm_cid = _normalize_id(cid)
        idx[norm_cid] = cid
        name = data.get("name") or data.get("label") or ""
        if name:
            idx[_normalize_id(name)] = cid
        for alias in data.get("aliases") or []:
            idx[_normalize_id(alias)] = cid
    return idx


def _resolve_id(name_or_id: str, name_idx: dict[str, str], concepts_data: dict[str, Any]) -> str | None:
    if not name_or_id:
        return None
    if name_or_id in concepts_data:
        return name_or_id
    norm = _normalize_id(name_or_id)
    if norm in concepts_data:
        return norm
    return name_idx.get(norm)


def _get_node_info(cid: str, concepts_data: dict[str, Any]) -> dict[str, Any]:
    raw = concepts_data.get(cid) or {}
    name = raw.get("name") or raw.get("label") or cid.replace("_", " ").title()
    diff = (raw.get("difficulty") or "intermediate").lower().strip()
    if diff not in _DIFFICULTY_RANK:
        diff = "intermediate"
    summary = raw.get("summary") or f"Core concept: {name}."
    domain = raw.get("domain") or ""
    return {
        "id": cid,
        "name": name,
        "label": name,
        "difficulty": diff,
        "summary": summary,
        "domain": domain,
    }


def _get_direct_prereqs(
    cid: str,
    concepts_data: dict[str, Any],
    name_idx: dict[str, str],
    kuzu_conn: Any | None = None,
) -> list[str]:
    res: list[str] = []
    seen: set[str] = set()

    # 1. Check Kuzu connection if available
    if kuzu_conn is not None:
        try:
            safe = str(cid).replace("'", "\\'")
            q_res = kuzu_conn.execute(
                f"MATCH (a:Concept {{id: '{safe}'}})-[:REQUIRES]->(b:Concept) RETURN b.id"
            )
            while q_res.has_next():
                pid = q_res.get_next()[0]
                if pid and pid != cid and pid not in seen:
                    seen.add(pid)
                    res.append(pid)
        except Exception:
            pass

    # 2. Check concepts_data
    c_node = concepts_data.get(cid) or {}
    for p in c_node.get("prerequisites") or []:
        p_raw = p.get("id") if isinstance(p, dict) else str(p)
        pid = _resolve_id(p_raw, name_idx, concepts_data)
        if pid and pid != cid and pid not in seen:
            seen.add(pid)
            res.append(pid)

    return res


def _get_direct_unlocks(
    cid: str,
    concepts_data: dict[str, Any],
    name_idx: dict[str, str],
    kuzu_conn: Any | None = None,
) -> list[str]:
    res: list[str] = []
    seen: set[str] = set()

    # 1. Check Kuzu
    if kuzu_conn is not None:
        try:
            safe = str(cid).replace("'", "\\'")
            for query in (
                f"MATCH (b:Concept)-[:REQUIRES]->(a:Concept {{id: '{safe}'}}) RETURN b.id",
                f"MATCH (a:Concept {{id: '{safe}'}})-[:UNLOCKS]->(b:Concept) RETURN b.id",
            ):
                q_res = kuzu_conn.execute(query)
                while q_res.has_next():
                    uid = q_res.get_next()[0]
                    if uid and uid != cid and uid not in seen:
                        seen.add(uid)
                        res.append(uid)
        except Exception:
            pass

    # 2. Check concepts_data
    c_node = concepts_data.get(cid) or {}
    for u in c_node.get("unlocks") or []:
        u_raw = u.get("id") if isinstance(u, dict) else str(u)
        uid = _resolve_id(u_raw, name_idx, concepts_data)
        if uid and uid != cid and uid not in seen:
            seen.add(uid)
            res.append(uid)

    return res


def _get_related_neighbors(
    cid: str,
    concepts_data: dict[str, Any],
    name_idx: dict[str, str],
    kuzu_conn: Any | None = None,
) -> list[tuple[str, str]]:
    """Return list of (neighbor_id, relation_type)."""
    res: list[tuple[str, str]] = []
    seen: set[str] = set()

    # 1. Kuzu
    if kuzu_conn is not None:
        try:
            safe = str(cid).replace("'", "\\'")
            for query in (
                f"MATCH (a:Concept {{id: '{safe}'}})-[r:RELATED]->(b:Concept) RETURN b.id, r.relation_type",
                f"MATCH (a:Concept {{id: '{safe}'}})<-[r:RELATED]-(b:Concept) RETURN b.id, r.relation_type",
            ):
                q_res = kuzu_conn.execute(query)
                while q_res.has_next():
                    rid, rtype = q_res.get_next()
                    if rid and rid != cid and rid not in seen:
                        seen.add(rid)
                        res.append((rid, str(rtype or "related").lower()))
        except Exception:
            pass

    # 2. concepts_data
    c_node = concepts_data.get(cid) or {}
    for rel in c_node.get("related") or []:
        if isinstance(rel, dict):
            r_target = rel.get("concept") or rel.get("id") or ""
            rtype = rel.get("relation") or rel.get("relation_type") or "related"
        else:
            r_target = str(rel)
            rtype = "related"
        rid = _resolve_id(r_target, name_idx, concepts_data)
        if rid and rid != cid and rid not in seen:
            seen.add(rid)
            res.append((rid, str(rtype).lower()))

    return res


def _induce_subgraph_edges(
    node_ids: set[str],
    concepts_data: dict[str, Any],
    name_idx: dict[str, str],
    kuzu_conn: Any | None = None,
) -> list[dict[str, Any]]:
    """Find all edges between the selected set of node IDs."""
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(u: str, v: str, rel: str):
        if u in node_ids and v in node_ids and u != v:
            key = (u, v, rel)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append({"from_id": u, "to_id": v, "relation": rel, "weight": 1.0})

    # From concepts_data
    for u in node_ids:
        u_node = concepts_data.get(u) or {}
        # REQUIRES: u requires p (u -> p)
        for p in u_node.get("prerequisites") or []:
            pid = _resolve_id(p.get("id") if isinstance(p, dict) else str(p), name_idx, concepts_data)
            if pid and pid in node_ids:
                add_edge(u, pid, "REQUIRES")
        # UNLOCKS: u unlocks un (u -> un)
        for un in u_node.get("unlocks") or []:
            uid = _resolve_id(un.get("id") if isinstance(un, dict) else str(un), name_idx, concepts_data)
            if uid and uid in node_ids:
                add_edge(u, uid, "UNLOCKS")
        # RELATED
        for rel in u_node.get("related") or []:
            if isinstance(rel, dict):
                rtarget = rel.get("concept") or rel.get("id") or ""
                rtype = rel.get("relation") or rel.get("relation_type") or "RELATED"
            else:
                rtarget = str(rel)
                rtype = "RELATED"
            rid = _resolve_id(rtarget, name_idx, concepts_data)
            if rid and rid in node_ids:
                add_edge(u, rid, rtype.upper())

    # From Kuzu if available
    if kuzu_conn is not None:
        try:
            for u in node_ids:
                safe_u = str(u).replace("'", "\\'")
                res = kuzu_conn.execute(
                    f"MATCH (a:Concept {{id: '{safe_u}'}})-[r:REQUIRES]->(b:Concept) RETURN b.id"
                )
                while res.has_next():
                    v = res.get_next()[0]
                    if v in node_ids:
                        add_edge(u, v, "REQUIRES")
                res = kuzu_conn.execute(
                    f"MATCH (a:Concept {{id: '{safe_u}'}})-[r:UNLOCKS]->(b:Concept) RETURN b.id"
                )
                while res.has_next():
                    v = res.get_next()[0]
                    if v in node_ids:
                        add_edge(u, v, "UNLOCKS")
        except Exception:
            pass

    return edges


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
        d_rank = _DIFFICULTY_RANK.get(d_node.get("difficulty", "intermediate"), 2)
        target_rank = _DIFFICULTY_RANK.get(
            (concepts_data.get(target_id) or {}).get("difficulty", "intermediate"), 2
        )
        if d_rank <= target_rank:
            new_edges.append({"from_id": target_id, "to_id": d, "relation": "REQUIRES", "weight": 1.0})
        else:
            new_edges.append({"from_id": target_id, "to_id": d, "relation": "UNLOCKS", "weight": 1.0})
        bridged_nodes.append(d)

    return bridged_nodes, new_edges


def generate_bounded_subgraph(
    target_id: str,
    secondary_target_id: str | None = None,
    mode: str = "mode_c",
    max_nodes: int = 10,
    min_nodes: int = 5,
    concepts_data: dict[str, Any] | None = None,
    kuzu_conn: Any | None = None,
) -> BoundedSubgraph:
    """Generate a strictly bounded subgraph for query visualization and reasoning.

    Args:
        target_id: Primary concept ID or name.
        secondary_target_id: Optional secondary concept ID for Mode B.
        mode: "mode_a", "mode_b", or "mode_c".
        max_nodes: Upper bound on node count (default 10).
        min_nodes: Lower bound for curriculum / comparative (default 5).
        concepts_data: Optional dict mapping concept_id to metadata (defaults to st.CONCEPTS_DATA).
        kuzu_conn: Optional open Kuzu connection.

    Returns:
        BoundedSubgraph with nodes, edges, target_ids, and metadata.
    """
    if concepts_data is None:
        from archipelago.inference import state as st
        concepts_data = st.CONCEPTS_DATA or {}

    name_idx = _build_name_to_id_index(concepts_data)

    real_target_id = _resolve_id(target_id, name_idx, concepts_data)
    if not real_target_id:
        real_target_id = target_id

    # ── MODE A: Minimal 1-hop / Atomic Concept (<= 3 nodes) ────────────────
    if mode == "mode_a":
        selected_ids = [real_target_id]
        p_list = _get_direct_prereqs(real_target_id, concepts_data, name_idx, kuzu_conn)
        u_list = _get_direct_unlocks(real_target_id, concepts_data, name_idx, kuzu_conn)

        if p_list:
            selected_ids.append(p_list[0])
        if u_list and len(selected_ids) < 3:
            selected_ids.append(u_list[0])

        edges = _induce_subgraph_edges(set(selected_ids), concepts_data, name_idx, kuzu_conn)
        nodes_out = []
        for cid in selected_ids:
            info = _get_node_info(cid, concepts_data)
            role = "target" if cid == real_target_id else ("prereq" if cid in p_list else "unlock")
            nodes_out.append({**info, "role": role, "hop": 0 if cid == real_target_id else 1})

        return BoundedSubgraph(
            nodes=nodes_out,
            edges=edges,
            target_ids=[real_target_id],
            query_mode="mode_a",
            metadata={"description": "Minimal 1-hop atomic concept neighborhood"},
        )

    # ── MODE B: Comparative / Relational Path (5 to 10 nodes) ──────────────
    if mode == "mode_b":
        real_sec_id = _resolve_id(secondary_target_id or "", name_idx, concepts_data)
        targets = [real_target_id]
        if real_sec_id and real_sec_id != real_target_id:
            targets.append(real_sec_id)

        path_nodes: list[str] = []
        if len(targets) == 2:
            src, dst = targets[0], targets[1]
            adj_all: dict[str, list[str]] = {}
            for cid in concepts_data:
                for p in _get_direct_prereqs(cid, concepts_data, name_idx, kuzu_conn):
                    adj_all.setdefault(cid, []).append(p)
                    adj_all.setdefault(p, []).append(cid)
                for u in _get_direct_unlocks(cid, concepts_data, name_idx, kuzu_conn):
                    adj_all.setdefault(cid, []).append(u)
                    adj_all.setdefault(u, []).append(cid)
                for r, _ in _get_related_neighbors(cid, concepts_data, name_idx, kuzu_conn):
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
                for p in _get_direct_prereqs(t, concepts_data, name_idx, kuzu_conn):
                    if p not in selected_ids:
                        selected_ids.append(p)
                        if len(selected_ids) >= max_nodes:
                            break
                if len(selected_ids) >= max_nodes:
                    break
                for u in _get_direct_unlocks(t, concepts_data, name_idx, kuzu_conn):
                    if u not in selected_ids:
                        selected_ids.append(u)
                        if len(selected_ids) >= max_nodes:
                            break

        # Fallback backfill if still < min_nodes
        if len(selected_ids) < min_nodes:
            for uf in _UNIVERSAL_FOUNDATIONS:
                if uf in concepts_data and uf not in selected_ids:
                    selected_ids.append(uf)
                    if len(selected_ids) >= min_nodes:
                        break

        # Prune if > max_nodes
        if len(selected_ids) > max_nodes:
            keep_set = set(targets)
            remaining = [x for x in selected_ids if x not in keep_set]
            selected_ids = list(targets) + remaining[: max_nodes - len(targets)]

        edges = _induce_subgraph_edges(set(selected_ids), concepts_data, name_idx, kuzu_conn)
        selected_ids, edges = _ensure_weak_connectivity(
            real_target_id, selected_ids, edges, concepts_data, min_nodes=min_nodes
        )

        nodes_out = []
        for cid in selected_ids:
            info = _get_node_info(cid, concepts_data)
            role = "target" if cid in targets else ("bridge" if cid in path_nodes else "context")
            nodes_out.append({**info, "role": role, "hop": 0 if cid in targets else 1})

        return BoundedSubgraph(
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

    p1_list = _get_direct_prereqs(real_target_id, concepts_data, name_idx, kuzu_conn)
    for p in p1_list:
        if p != real_target_id:
            candidates[p] = {
                "role": "prereq",
                "hop": 1,
                "priority": 100,
            }

    u1_list = _get_direct_unlocks(real_target_id, concepts_data, name_idx, kuzu_conn)
    for u in u1_list:
        if u != real_target_id and u not in candidates:
            candidates[u] = {
                "role": "unlock",
                "hop": 1,
                "priority": 70,
            }

    for p in p1_list:
        p2_list = _get_direct_prereqs(p, concepts_data, name_idx, kuzu_conn)
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
            node_info = _get_node_info(cid, concepts_data)
            diff = node_info["difficulty"]
            diff_score = 15.0 if diff == "foundational" else (10.0 if diff == "intermediate" else 5.0)
            return base_prio + diff_score

        sorted_cand = sorted(candidates.items(), key=_candidate_score, reverse=True)
        candidates = dict(sorted_cand[:max_nodes])

    if len(candidates) < min_nodes:
        target_info = _get_node_info(real_target_id, concepts_data)
        target_domain = target_info.get("domain", "")

        for cid, data in concepts_data.items():
            if cid not in candidates and (data.get("difficulty") or "").lower() == "foundational":
                if target_domain and data.get("domain") == target_domain:
                    candidates[cid] = {"role": "prereq", "hop": 2, "priority": 25}
                    if len(candidates) >= min_nodes:
                        break

        if len(candidates) < min_nodes:
            for uf in _UNIVERSAL_FOUNDATIONS:
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
    edges = _induce_subgraph_edges(set(selected_ids), concepts_data, name_idx, kuzu_conn)

    selected_ids, edges = _ensure_weak_connectivity(
        real_target_id, selected_ids, edges, concepts_data, min_nodes=min_nodes
    )

    nodes_out = []
    for cid in selected_ids:
        info = _get_node_info(cid, concepts_data)
        meta = candidates.get(cid, {"role": "context", "hop": 1})
        nodes_out.append({
            **info,
            "role": meta["role"],
            "hop": meta.get("hop", 1),
        })

    return BoundedSubgraph(
        nodes=nodes_out,
        edges=edges,
        target_ids=[real_target_id],
        query_mode="mode_c",
        metadata={
            "description": "Deep pedagogical curriculum exploration bounded subgraph",
            "hop_depth": 2,
        },
    )
