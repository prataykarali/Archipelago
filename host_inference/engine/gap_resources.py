"""Exact source-to-holding mappings; no keyword-only OPAC recommendations."""

from __future__ import annotations

MAX_RESOURCES = 4


def gap_resources(graph, gaps: list[str], records: list[dict]) -> list[dict]:
    """Map assessed gaps through explicit resource IDs or source document IDs."""
    index: dict[str, list[dict]] = {}
    for record in records:
        for field in ("book_id", "id", "doc_id"):
            identifier = str(record.get(field) or "")
            if identifier:
                index.setdefault(identifier, []).append(record)
    result, seen = [], set()
    for cid in gaps:
        node = graph.nodes.get(cid, {})
        identifiers = list(node.get("resource_ids") or [])
        identifiers += [
            source.get("doc_id")
            for source in node.get("sources", [])
            if isinstance(source, dict) and source.get("doc_id")
        ]
        for identifier in identifiers:
            matches = index.get(str(identifier), [])
            if len(matches) != 1:
                continue
            record = matches[0]
            key = str(record.get("book_id") or record.get("id") or identifier)
            if key in seen:
                continue
            seen.add(key)
            item = {
                "concept_id": cid,
                "title": str(record.get("title") or ""),
                "why": "An indexed source for this assessed prerequisite matches this holding.",
                "status": "imported_snapshot",
            }
            for field in (
                "authors",
                "author",
                "call_number",
                "location",
                "rack",
                "shelf",
                "total_copies",
                "available_copies",
            ):
                if field in record:
                    item[field] = record[field]
            result.append(item)
            if len(result) >= MAX_RESOURCES:
                return result
    return result
