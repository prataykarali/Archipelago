"""Deterministic topic, provider and concept links for saved research sources."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import re
from typing import Any

MAX_NODE_SUMMARY = 850
MAX_CONCEPT_LINKS = 3
MIN_CONCEPT_LABEL_LENGTH = 6
SLUG_WORD = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return SLUG_WORD.sub("-", value.casefold()).strip("-")


def project_research_graph(
    records: list[dict[str, Any]], concepts: dict[str, dict[str, Any]]
) -> dict[str, object]:
    """Build an OKF-like, source-linked graph from persisted intake records."""
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, dict[str, str]]] = []
    providers: Counter[str] = Counter()
    concept_labels = [
        (concept_id, str(node.get("label") or node.get("name") or "").strip())
        for concept_id, node in concepts.items()
    ]
    concept_labels = [
        (concept_id, label)
        for concept_id, label in concept_labels
        if MIN_CONCEPT_LABEL_LENGTH <= len(label) <= 60
    ]
    for record in records:
        key = str(record.get("record_key") or "")
        if not key:
            continue
        title = str(record.get("title") or "Untitled source")
        topic = str(record.get("topic") or "").strip() or "Institutional pages"
        provider = str(record.get("source_name") or "Unknown source")
        source_id = f"record:{key}"
        topic_id = "topic:" + sha256(topic.casefold().encode()).hexdigest()[:16]
        provider_id = f"provider:{_slug(provider)}"
        nodes[source_id] = {
            "data": {
                "id": source_id,
                "name": title,
                "summary": str(record.get("content") or "")[:MAX_NODE_SUMMARY],
                "source_url": str(record.get("source_url") or ""),
                "kind": str(record.get("kind") or "paper"),
                "record_key": key,
                "access_state": (record.get("metadata") or {}).get("access_state", "METADATA_ONLY"),
                "provider": provider,
                "source_count": 1,
                "degree": 2,
            }
        }
        nodes.setdefault(topic_id, {"data": {"id": topic_id, "name": topic, "kind": "topic"}})
        nodes.setdefault(
            provider_id,
            {"data": {"id": provider_id, "name": provider, "kind": "provider"}},
        )
        edges.append(
            {
                "data": {
                    "id": f"{topic_id}:{source_id}",
                    "source": topic_id,
                    "target": source_id,
                    "rel_label": "IN_TOPIC",
                }
            }
        )
        edges.append(
            {
                "data": {
                    "id": f"{provider_id}:{source_id}",
                    "source": provider_id,
                    "target": source_id,
                    "rel_label": "FROM_SOURCE",
                }
            }
        )
        providers[provider] += 1
        match_text = f"{title} {topic}".casefold()
        matched = 0
        for concept_id, label in concept_labels:
            if label.casefold() not in match_text:
                continue
            concept_node_id = f"concept:{concept_id}"
            nodes.setdefault(
                concept_node_id,
                {
                    "data": {
                        "id": concept_node_id,
                        "name": label,
                        "kind": "concept",
                        "summary": str(concepts[concept_id].get("summary") or "")[
                            :MAX_NODE_SUMMARY
                        ],
                    }
                },
            )
            edges.append(
                {
                    "data": {
                        "id": f"{source_id}:{concept_node_id}",
                        "source": source_id,
                        "target": concept_node_id,
                        "rel_label": "MENTIONS",
                    }
                }
            )
            matched += 1
            if matched == MAX_CONCEPT_LINKS:
                break
    # Resolve only citations whose targets are also saved papers. Provider IDs
    # are source metadata; an absent target never becomes a fabricated node.
    by_openalex = {}
    for record in records:
        openalex_id = (record.get("metadata") or {}).get("openalex_id")
        record_key = record.get("record_key")
        if isinstance(openalex_id, str) and record_key:
            by_openalex[openalex_id.rstrip("/").split("/")[-1].casefold()] = f"record:{record_key}"
    for record in records:
        source_id = f"record:{record.get('record_key')}"
        if source_id not in nodes:
            continue
        references = (record.get("metadata") or {}).get("referenced_works") or []
        if not isinstance(references, list):
            continue
        for reference in references:
            if not isinstance(reference, str):
                continue
            target_id = by_openalex.get(reference.rstrip("/").split("/")[-1].casefold())
            if target_id and target_id != source_id:
                edges.append(
                    {
                        "data": {
                            "id": f"citation:{source_id}:{target_id}",
                            "source": source_id,
                            "target": target_id,
                            "rel_label": "CITES",
                        }
                    }
                )
    return {
        "schema": "archipelago.research_graph.v1",
        "nodes": list(nodes.values()),
        "edges": edges,
        "counts": {
            "sources": len(records),
            "nodes": len(nodes),
            "edges": len(edges),
            "providers": dict(providers),
        },
    }
