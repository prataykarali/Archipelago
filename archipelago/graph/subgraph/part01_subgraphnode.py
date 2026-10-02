"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from . import _deps as _rt  # noqa: F401

# Upper bound on neighbor rows pulled per graph query, so a hub concept cannot
# flood the bounded subgraph.
_NEIGHBORHOOD_SCAN_LIMIT = 64


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


def _kuzu_ids(conn: Any, query: str, params: dict[str, str], limit: int) -> list[str]:
    """Run a parameterized neighborhood query and drain the id column."""
    ids: list[str] = []
    try:
        res = conn.execute(query, params)
        while res.has_next() and len(ids) < limit:
            value = res.get_next()[0]
            if value:
                ids.append(str(value))
    except Exception:
        return []
    return ids


def _get_direct_prereqs(
    cid: str,
    concepts_data: dict[str, Any],
    name_idx: dict[str, str],
    kuzu_conn: Any | None = None,
) -> list[str]:
    res: list[str] = []
    seen: set[str] = set()

    # 1. Check Kuzu connection if available (parameterized: no interpolation)
    if kuzu_conn is not None:
        for pid in _kuzu_ids(
            kuzu_conn,
            "MATCH (a:Concept {id: $cid})-[:REQUIRES]->(b:Concept) RETURN b.id",
            {"cid": str(cid)},
            _NEIGHBORHOOD_SCAN_LIMIT,
        ):
            if pid != cid and pid not in seen:
                seen.add(pid)
                res.append(pid)

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
        for query in (
            "MATCH (b:Concept)-[:REQUIRES]->(a:Concept {id: $cid}) RETURN b.id",
            "MATCH (a:Concept {id: $cid})-[:UNLOCKS]->(b:Concept) RETURN b.id",
        ):
            for uid in _kuzu_ids(kuzu_conn, query, {"cid": str(cid)}, _NEIGHBORHOOD_SCAN_LIMIT):
                if uid != cid and uid not in seen:
                    seen.add(uid)
                    res.append(uid)

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
        for query in (
            "MATCH (a:Concept {id: $cid})-[r:RELATED]->(b:Concept) RETURN b.id, r.relation_type",
            "MATCH (a:Concept {id: $cid})<-[r:RELATED]-(b:Concept) RETURN b.id, r.relation_type",
        ):
            try:
                rows = kuzu_conn.execute(query, {"cid": str(cid)})
                while rows.has_next() and len(res) < _NEIGHBORHOOD_SCAN_LIMIT:
                    rid, rtype = rows.get_next()
                    if rid and rid != cid and rid not in seen:
                        seen.add(rid)
                        res.append((str(rid), str(rtype or "related").lower()))
            except Exception:
                continue

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
