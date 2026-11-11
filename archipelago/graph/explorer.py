"""Read-only, paginated view of every persisted graph entity and relation."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

import kuzu

NODE_KEYS = {
    "Concept": "id",
    "Document": "id",
    "Chunk": "id",
    "Resource": "id",
    "Subject": "subject_name",
    "JournalIssue": "issue_id",
}
RELATIONS = (
    "REQUIRES",
    "UNLOCKS",
    "RELATED",
    "HAS_CHUNK",
    "MENTIONS",
    "PROVIDES_TEXT",
    "CATEGORIZES",
    "HAS_ISSUE",
)
RELATION_SPECS = {
    "REQUIRES": ("Concept", "id", "Concept", "id", "r.relation_type,r.source"),
    "UNLOCKS": ("Concept", "id", "Concept", "id", "r.relation_type,r.source"),
    "RELATED": ("Concept", "id", "Concept", "id", "r.relation_type,r.source"),
    "HAS_CHUNK": ("Document", "id", "Chunk", "id", ""),
    "MENTIONS": ("Chunk", "id", "Concept", "id", ""),
    "PROVIDES_TEXT": ("Resource", "id", "Document", "id", "r.pdf_url"),
    "CATEGORIZES": ("Subject", "subject_name", "Resource", "id", ""),
    "HAS_ISSUE": ("Resource", "id", "JournalIssue", "issue_id", ""),
}
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 200
DEFAULT_NEIGHBORHOOD_SIZE = 40
MAX_NEIGHBORHOOD_HOPS = 3
SUMMARY_CHAR_LIMIT = 600
SOURCE_REF_CHAR_LIMIT = 500
EDGE_ID_HEX_LENGTH = 16
VERSION_HEX_LENGTH = 12


def _rows(connection: kuzu.Connection, query: str) -> list[list[Any]]:
    result = connection.execute(query)
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    return rows


def _node_id(raw: dict[str, Any]) -> str:
    kind = str(raw.get("_label") or "")
    field = NODE_KEYS.get(kind, "id")
    value = str(raw.get(field) or "").strip()
    return value if kind == "Concept" else f"{kind.lower()}:{value}"


def _public_node(raw: dict[str, Any]) -> dict[str, Any]:
    kind = str(raw.get("_label") or "")
    name = raw.get("name") or raw.get("title") or raw.get("subject_name")
    name = name or raw.get("resource_title") or raw.get("id") or raw.get("issue_id")
    node = {
        "id": _node_id(raw),
        "name": str(name or ""),
        "kind": kind,
        "summary": str(raw.get("summary") or "")[:SUMMARY_CHAR_LIMIT],
    }
    for key in (
        "concept_type",
        "author",
        "publisher",
        "copyright_year",
        "page_number",
        "section_title",
        "published_date",
        "status",
        "total_copies",
        "available_copies",
    ):
        if raw.get(key) is not None:
            node[key] = raw[key]
    return node


@lru_cache(maxsize=2)
def load_persisted_graph(path: str, modified_ns: int) -> dict[str, Any]:
    """Load a graph snapshot from Kùzu without creating or changing storage."""
    database = kuzu.Database(path, read_only=True)
    connection = kuzu.Connection(database)
    nodes = []
    for kind in NODE_KEYS:
        for (raw,) in _rows(connection, f"MATCH (n:{kind}) RETURN n"):
            if isinstance(raw, dict) and raw.get(NODE_KEYS[kind]):
                nodes.append(_public_node(raw))
    nodes.sort(key=lambda node: node["id"])
    ids = {node["id"] for node in nodes}
    edges = []
    duplicates: Counter[tuple[str, str, str]] = Counter()
    for relation, (src_type, src_key, dst_type, dst_key, extra) in RELATION_SPECS.items():
        query = (
            f"MATCH (a:{src_type})-[r:{relation}]->(b:{dst_type}) "
            f"RETURN a.{src_key},b.{dst_key}" + (f",{extra}" if extra else "")
        )
        for row in _rows(connection, query):
            src_id = str(row[0]) if src_type == "Concept" else f"{src_type.lower()}:{row[0]}"
            dst_id = str(row[1]) if dst_type == "Concept" else f"{dst_type.lower()}:{row[1]}"
            if src_id not in ids or dst_id not in ids:
                continue
            key = (src_id, dst_id, relation)
            duplicates[key] += 1
            digest = sha256(f"{src_id}|{relation}|{dst_id}|{duplicates[key]}".encode()).hexdigest()[
                :EDGE_ID_HEX_LENGTH
            ]
            edge = {
                "id": f"edge:{digest}",
                "source": src_id,
                "target": dst_id,
                "relation": relation,
            }
            if relation in {"REQUIRES", "UNLOCKS", "RELATED"}:
                if row[2]:
                    edge["relation_type"] = str(row[2])
                if row[3]:
                    edge["source_ref"] = str(row[3])[:SOURCE_REF_CHAR_LIMIT]
            elif relation == "PROVIDES_TEXT" and row[2]:
                edge["pdf_url"] = str(row[2])[:SOURCE_REF_CHAR_LIMIT]
            edges.append(edge)
    edges.sort(key=lambda edge: edge["id"])
    degree = Counter(endpoint for edge in edges for endpoint in (edge["source"], edge["target"]))
    node_types = Counter(node["kind"] for node in nodes)
    edge_types = Counter(edge["relation"] for edge in edges)
    return {
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "orphans": sum(node["id"] not in degree for node in nodes),
            "node_types": dict(node_types),
            "relation_types": dict(edge_types),
        },
        "version": sha256(
            (
                "\n".join(node["id"] for node in nodes)
                + "\n"
                + "\n".join(edge["id"] for edge in edges)
            ).encode()
        ).hexdigest()[:VERSION_HEX_LENGTH],
        "last_sync": Path(path).stat().st_mtime,
    }


def graph_snapshot(path: Path) -> dict[str, Any]:
    """Return the cached read-only view, invalidated when storage changes."""
    return load_persisted_graph(str(path.resolve()), path.stat().st_mtime_ns)


def graph_page(
    graph: dict[str, Any],
    *,
    kind: str = "nodes",
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    node_type: str = "",
    relation: str = "",
    search: str = "",
) -> dict[str, Any]:
    """Page records deterministically; filtering never changes the snapshot."""
    if kind not in {"nodes", "edges"}:
        raise ValueError("kind must be nodes or edges")
    records = graph[kind]
    if kind == "nodes":
        records = [row for row in records if not node_type or row["kind"] == node_type]
        if search:
            term = search.casefold()
            records = [
                row
                for row in records
                if term
                in " ".join(
                    str(row.get(key) or "") for key in ("name", "author", "id", "summary")
                ).casefold()
            ]
    elif relation:
        records = [row for row in records if row["relation"] == relation]
    size = max(1, min(limit, MAX_PAGE_SIZE))
    start = max(0, offset)
    page_items = records[start : start + size]
    payload = {
        "items": page_items,
        "offset": start,
        "next_offset": start + size if start + size < len(records) else None,
        "total": len(records),
        "counts": graph["counts"],
        "version": graph["version"],
        "last_sync": graph["last_sync"],
    }
    if kind == "nodes":
        page_ids = {item["id"] for item in page_items}
        payload["visible_edges"] = [
            edge
            for edge in graph["edges"]
            if edge["source"] in page_ids
            and edge["target"] in page_ids
            and (not relation or edge["relation"] == relation)
        ]
    return payload


def graph_neighborhood(
    graph: dict[str, Any],
    node_id: str,
    limit: int = DEFAULT_NEIGHBORHOOD_SIZE,
    max_hops: int = 2,
) -> dict[str, Any]:
    """Return a bounded multi-hop neighborhood with typed valid endpoints."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    if node_id not in by_id:
        raise KeyError(node_id)
    size = max(1, min(limit, MAX_PAGE_SIZE))
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append(edge)
        adjacency.setdefault(edge["target"], []).append(edge)
    selected: list[dict[str, Any]] = []
    seen_edges: set[str] = set()
    ids = {node_id}
    frontier = [node_id]
    for _depth in range(max(1, min(max_hops, MAX_NEIGHBORHOOD_HOPS))):
        next_frontier = []
        for current in frontier:
            for edge in adjacency.get(current, []):
                if edge["id"] in seen_edges:
                    continue
                seen_edges.add(edge["id"])
                selected.append(edge)
                other = edge["target"] if edge["source"] == current else edge["source"]
                if other not in ids:
                    ids.add(other)
                    next_frontier.append(other)
                if len(selected) >= size:
                    break
            if len(selected) >= size:
                break
        if len(selected) >= size or not next_frontier:
            break
        frontier = next_frontier
    return {
        "target_id": node_id,
        "nodes": [by_id[cid] for cid in sorted(ids)],
        "edges": selected,
        "total_edges": len(adjacency.get(node_id, [])),
        "counts": graph["counts"],
        "version": graph["version"],
    }
