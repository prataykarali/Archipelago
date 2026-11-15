"""Normalize graph edges from gold and extracted payloads."""

from __future__ import annotations

from typing import Any


def _edge_matches_doc(edge: dict[str, Any], doc_id: str) -> tuple[bool, bool]:
    """Check whether an edge record belongs to ``doc_id``.

    Returns ``(in_scope, is_unscopable)``:
    - ``(True, False)``: edge provenance explicitly matches ``doc_id``.
    - ``(False, False)``: edge provenance explicitly belongs to another document.
    - ``(False, True)``: edge lacks valid document provenance (missing/None/opaque tag).
    """
    prov = edge.get("doc_id")
    if not prov and ("from_name" in edge or "from_id" in edge or "from" in edge):
        prov = edge.get("source")
    if not isinstance(prov, str) or not prov.strip():
        return False, True
    prov_s = prov.strip()
    if prov_s == doc_id or prov_s.startswith(f"{doc_id}:"):
        return True, False
    # Opaque tags without ':' (e.g. 'pearson_batch1', 'librarian_upload') cannot be
    # reliably attributed to any document.
    if ":" not in prov_s and "/" not in prov_s and not prov_s.startswith("doc_"):
        return False, True
    return False, False


def _is_export_edge(e: dict[str, Any]) -> bool:
    """True when edge dict uses Kuzu export schema (from_name/from_id/from) rather than gold (source/target)."""
    return "from_name" in e or "from_id" in e or "from" in e


def _add_edge_record(
    e: dict[str, Any],
    edges: set[tuple[str, str]],
    *,
    include_related: bool,
    doc_id: str | None,
    stats: dict[str, int] | None,
) -> None:
    is_export = _is_export_edge(e)
    if is_export:
        src = e.get("from_name") or e.get("from_id") or e.get("from")
        dst = e.get("to_name") or e.get("to_id") or e.get("to")
    else:
        src = e.get("source")
        dst = e.get("target")

    etype = str(e.get("edge_type") or e.get("type") or "").upper()
    if not src or not dst:
        return

    if etype not in ("REQUIRES", "UNLOCKS"):
        if not include_related:
            if stats is not None:
                stats["skipped_related"] = stats.get("skipped_related", 0) + 1
            return

    if doc_id is not None and is_export:
        in_scope, is_unscopable = _edge_matches_doc(e, doc_id)
        if not in_scope:
            if is_unscopable and stats is not None:
                stats["unscopable_edges"] = stats.get("unscopable_edges", 0) + 1
            return

    src_l = str(src).strip().lower()
    dst_l = str(dst).strip().lower()
    if etype == "REQUIRES":
        # Gold files encode requires as source→target (learner path).
        # Export edges use from_name REQUIRES to_name (from_name depends on to_name),
        # so the learner path is to_name → from_name.
        if is_export:
            edges.add((dst_l, src_l))
        else:
            edges.add((src_l, dst_l))
    elif etype == "UNLOCKS":
        edges.add((src_l, dst_l))
    else:
        edges.add((min(src_l, dst_l), max(src_l, dst_l)))


def _extract_edges(
    input_data: Any,
    *,
    include_related: bool = False,
    doc_id: str | None = None,
    stats: dict[str, int] | None = None,
) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    if isinstance(input_data, dict):
        if "edges" in input_data:
            for e in input_data["edges"]:
                if isinstance(e, dict):
                    _add_edge_record(
                        e,
                        edges,
                        include_related=include_related,
                        doc_id=doc_id,
                        stats=stats,
                    )
        else:
            for _cid, c in input_data.items():
                if isinstance(c, dict):
                    name = c.get("name") or c.get("concept_name")
                    if name:
                        name_l = name.strip().lower()
                        for p in c.get("prerequisites", []):
                            edges.add((p.strip().lower(), name_l))
                        for u in c.get("unlocks", []):
                            edges.add((name_l, u.strip().lower()))
                        if include_related:
                            for r in c.get("related", []):
                                if isinstance(r, dict) and r.get("concept"):
                                    rc = r["concept"].strip().lower()
                                    edges.add((min(name_l, rc), max(name_l, rc)))
    elif isinstance(input_data, list):
        if (
            input_data
            and isinstance(input_data[0], dict)
            and (
                "from_name" in input_data[0]
                or "source" in input_data[0]
                or "from_id" in input_data[0]
                or "from" in input_data[0]
            )
        ):
            for e in input_data:
                if isinstance(e, dict):
                    _add_edge_record(
                        e,
                        edges,
                        include_related=include_related,
                        doc_id=doc_id,
                        stats=stats,
                    )
        else:
            for c in input_data:
                if isinstance(c, dict):
                    if "concepts" in c:
                        for sub_c in c["concepts"]:
                            name = sub_c.get("concept_name")
                            if name:
                                name_l = name.strip().lower()
                                for p in sub_c.get("prerequisites", []):
                                    edges.add((p.strip().lower(), name_l))
                                for u in sub_c.get("unlocks", []):
                                    edges.add((name_l, u.strip().lower()))
                                if include_related:
                                    for r in sub_c.get("related_to", []):
                                        if isinstance(r, dict) and r.get("concept"):
                                            rc = r["concept"].strip().lower()
                                            edges.add((min(name_l, rc), max(name_l, rc)))
                    else:
                        name = c.get("concept_name") or c.get("name")
                        if name:
                            name_l = name.strip().lower()
                            for p in c.get("prerequisites", []):
                                edges.add((p.strip().lower(), name_l))
                            for u in c.get("unlocks", []):
                                edges.add((name_l, u.strip().lower()))
                            if include_related:
                                for r in c.get("related_to", []):
                                    if isinstance(r, dict) and r.get("concept"):
                                        rc = r["concept"].strip().lower()
                                        edges.add((min(name_l, rc), max(name_l, rc)))
    return edges
