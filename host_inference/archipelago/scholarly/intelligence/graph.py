"""Source-backed graph projection from a persisted scholarly run."""

from __future__ import annotations

from hashlib import sha256
from typing import Any


def build_graph(run: dict[str, Any]) -> dict[str, Any]:
    """Only create citation edges named by provider reference metadata."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    topic = run["options"]["topic"]
    topic_id = "topic:" + sha256(topic.casefold().encode()).hexdigest()[:16]
    nodes[topic_id] = {"id": topic_id, "kind": "Topic", "name": topic}
    known = {
        paper["identifiers"].get("openalex_id"): paper["paper_id"]
        for paper in run["papers"]
        if paper["identifiers"].get("openalex_id")
    }
    for paper in run["papers"]:
        paper_id = "paper:" + paper["paper_id"]
        nodes[paper_id] = {
            "id": paper_id,
            "kind": "Paper",
            "name": paper["title"],
            "url": paper["url"],
        }
        edges.append(
            {"source": paper_id, "target": topic_id, "type": "STUDIES_TOPIC", "provider": "ranking"}
        )
        for author in paper["authors"]:
            identity = author.get("orcid") or f"unverified:{paper['paper_id']}:{author['name']}"
            author_id = "author:" + sha256(identity.encode()).hexdigest()[:16]
            nodes[author_id] = {
                "id": author_id,
                "kind": "Author",
                "name": author["name"],
                "orcid": author.get("orcid"),
            }
            edges.append(
                {
                    "source": paper_id,
                    "target": author_id,
                    "type": "AUTHORED_BY",
                    "provider": paper["citation_provider"],
                }
            )
            for affiliation in author.get("institutions") or []:
                institution_id = (
                    "institution:" + sha256(affiliation.casefold().encode()).hexdigest()[:16]
                )
                nodes[institution_id] = {
                    "id": institution_id,
                    "kind": "Institution",
                    "name": affiliation,
                }
                edges.append(
                    {
                        "source": author_id,
                        "target": institution_id,
                        "type": "AFFILIATED_WITH",
                        "provider": paper["citation_provider"],
                    }
                )
        if paper["venue"]:
            venue_id = "venue:" + sha256(paper["venue"].casefold().encode()).hexdigest()[:16]
            nodes[venue_id] = {"id": venue_id, "kind": "Venue", "name": paper["venue"]}
            edges.append(
                {
                    "source": paper_id,
                    "target": venue_id,
                    "type": "PUBLISHED_IN",
                    "provider": paper["citation_provider"],
                }
            )
        for reference in paper["references"]:
            cited = known.get(reference) if isinstance(reference, str) else None
            if cited and cited != paper["paper_id"]:
                edges.append(
                    {
                        "source": paper_id,
                        "target": "paper:" + cited,
                        "type": "CITES",
                        "provider": paper["citation_provider"],
                    }
                )
    return {
        "schema": "archipelago.scholarly_graph.v1",
        "run_at": run["retrieved_at"],
        "nodes": list(nodes.values()),
        "edges": edges,
    }
