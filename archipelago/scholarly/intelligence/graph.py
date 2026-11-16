"""Source-backed research graph projection from a persisted scholarly run.

Kept separate from the S4 academic OKF graph. No edge is inferred from
semantic similarity: citations come only from provider reference lists.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any


def _hash(prefix: str, value: str) -> str:
    return f"{prefix}:" + sha256(value.casefold().encode()).hexdigest()[:16]


def author_key(paper: dict[str, Any], index: int) -> str:
    """Stable author identity: OpenAlex ID, then ORCID, then S2 ID, else paper-scoped unverified."""
    meta = paper.get("source_metadata") or {}
    ids = meta.get("author_openalex_ids") or []
    provider_id = ids[index] if index < len(ids) else None
    author = paper["authors"][index]
    if provider_id:
        return "author:" + str(provider_id).rsplit("/", 1)[-1]
    if author.get("orcid"):
        return _hash("author", author["orcid"])
    s2_ids = meta.get("author_s2_ids") or []
    s2_id = s2_ids[index] if index < len(s2_ids) else None
    if s2_id:
        return f"author:s2:{s2_id}"
    return _hash("author-unverified", f"{paper['paper_id']}:{index}:{author['name']}")


def venue_key(paper: dict[str, Any]) -> str | None:
    if not paper.get("venue"):
        return None
    venue_id = (paper.get("source_metadata") or {}).get("venue_id")
    return "venue:" + venue_id.rsplit("/", 1)[-1] if venue_id else _hash("venue", paper["venue"])


def build_graph(run: dict[str, Any]) -> dict[str, Any]:
    """Create nodes and typed edges, each carrying its provider."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def edge(source: str, target: str, kind: str, provider: str | None) -> None:
        if (source, target, kind) not in seen:
            seen.add((source, target, kind))
            edges.append(
                {"source": source, "target": target, "type": kind, "provider": provider or "n/a"}
            )

    topic = run["options"]["topic"]
    topic_id = _hash("topic", topic)
    nodes[topic_id] = {"id": topic_id, "kind": "Topic", "name": topic}
    known: dict[str, str] = {}
    for paper in run["papers"]:
        pid = paper["paper_id"]
        ids = paper.get("identifiers") or {}
        oa_id = ids.get("openalex_id")
        if oa_id:
            known[oa_id] = pid
            known[str(oa_id).rsplit("/", 1)[-1]] = pid
        doi = ids.get("doi") or paper.get("doi")
        if doi:
            dnorm = str(doi).strip().casefold().removeprefix("https://doi.org/")
            known[dnorm] = pid
            known[f"https://doi.org/{dnorm}"] = pid
        s2_id = ids.get("semantic_scholar_id")
        if s2_id:
            known[str(s2_id).strip()] = pid
        arxiv_id = ids.get("arxiv_id")
        if arxiv_id:
            anorm = str(arxiv_id).strip().casefold()
            known[anorm] = pid

    total_reference_links = 0
    resolved_known_works = 0
    in_collection_edges = 0
    for paper in run["papers"]:
        paper_id = "paper:" + paper["paper_id"]
        provider = paper.get("citation_provider") or paper.get("source")
        nodes[paper_id] = {
            "id": paper_id,
            "kind": "Paper",
            "name": paper["title"],
            "url": paper["url"],
        }
        edge(paper_id, topic_id, "STUDIES_TOPIC", "topic_eligibility_filter")
        for label in paper.get("topics") or []:
            sub_id = _hash("topic", str(label))
            nodes.setdefault(sub_id, {"id": sub_id, "kind": "Topic", "name": str(label)})
            edge(paper_id, sub_id, "STUDIES_TOPIC", provider)
        for kind, items, node_kind, relation in (
            ("method", paper.get("methods") or [], "Method", "USES_METHOD"),
            ("dataset", paper.get("datasets") or [], "Dataset", "EVALUATED_ON"),
        ):
            for item in items:
                name = item["name"] if isinstance(item, dict) else str(item)
                item_id = _hash(kind, name)
                nodes.setdefault(item_id, {"id": item_id, "kind": node_kind, "name": name})
                edge(paper_id, item_id, relation, "abstract_evidence")
        paper_authors: list[str] = []
        for index, author in enumerate(paper["authors"]):
            author_id = author_key(paper, index)
            nodes.setdefault(
                author_id,
                {
                    "id": author_id,
                    "kind": "Author",
                    "name": author["name"],
                    "orcid": author.get("orcid"),
                },
            )
            paper_authors.append(author_id)
            edge(paper_id, author_id, "AUTHORED_BY", provider)
            for affiliation in author.get("institutions") or []:
                institution_id = _hash("institution", affiliation)
                nodes.setdefault(
                    institution_id,
                    {"id": institution_id, "kind": "Institution", "name": affiliation},
                )
                edge(author_id, institution_id, "AFFILIATED_WITH", provider)
        # Coauthorship is only asserted between provider-identified authors.
        identified = [a for a in paper_authors if not a.startswith("author-unverified")]
        for i, left in enumerate(identified):
            for right in identified[i + 1 :]:
                if left != right:
                    pair = sorted((left, right))
                    edge(pair[0], pair[1], "COAUTHORED_WITH", provider)
        venue_id = venue_key(paper)
        if venue_id:
            nodes.setdefault(venue_id, {"id": venue_id, "kind": "Venue", "name": paper["venue"]})
            edge(paper_id, venue_id, "PUBLISHED_IN", provider)
        for reference in paper.get("references") or []:
            if not isinstance(reference, str) or not reference.strip():
                continue
            total_reference_links += 1
            ref_norm = reference.strip()
            ref_low = ref_norm.casefold().removeprefix("https://doi.org/")
            if ref_norm.startswith("https://openalex.org/W") or ref_low.startswith("10."):
                resolved_known_works += 1
            cited = known.get(ref_norm) or known.get(ref_norm.rsplit("/", 1)[-1]) or known.get(ref_low)
            if cited and cited != paper["paper_id"]:
                before = len(seen)
                edge(paper_id, "paper:" + cited, "CITES", provider)
                if len(seen) > before:
                    in_collection_edges += 1
    return {
        "schema": "archipelago.scholarly_graph.v1",
        "run_at": run["retrieved_at"],
        "nodes": list(nodes.values()),
        "edges": edges,
        "coverage_report": {
            "total_reference_links": total_reference_links,
            "resolved_known_works": resolved_known_works,
            "in_collection_edges": in_collection_edges,
            "resolution_rate": round(resolved_known_works / total_reference_links, 4)
            if total_reference_links
            else None,
        },
    }
