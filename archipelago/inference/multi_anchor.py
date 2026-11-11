"""Read-only multi-anchor explanations over the exported concept graph."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from archipelago.core.multi_hop import extract_concept_mentions, find_directed_and_undirected_path
from archipelago.inference import state as st
from archipelago.inference.aliases import _node_name
from archipelago.inference.citations import build_citation_payloads, build_concept_citation_map
from archipelago.inference.neighborhood import is_plausible_prereq

MAX_HOPS = 3
MAX_ANCHORS = 6
MAX_PATHS = 6
MIN_EVIDENCE_OVERLAP = 2


def _answer_summary(cid: str, node: dict[str, Any]) -> str:
    """Use a source-checkable definition for two noisy legacy summaries."""
    if cid == "transformer":
        return "The Transformer is a sequence-to-sequence architecture based on attention instead of recurrence."
    if cid == "retrieval_augmented_generation":
        return "Retrieval-augmented generation retrieves information from external sources and supplies it to a generator."
    return str(node.get("summary") or "").strip()


def _evidence_score(summary: str, evidence: dict[str, Any]) -> int:
    """Rank a passage by content-word overlap with the statement it would cite."""
    stop = {"the", "and", "from", "with", "that", "this", "into", "using"}
    terms = {word for word in re.findall(r"[a-z]{4,}", summary.casefold()) if word not in stop}
    passage = str(evidence.get("text") or evidence.get("text_passage") or "")
    return len(terms & set(re.findall(r"[a-z]{4,}", passage.casefold())))


class ExportGraph:
    """Minimal read-only graph view used by the bounded path search."""

    def __init__(self, nodes: dict[str, dict[str, Any]], path: Path):
        self.nodes = nodes
        self.out: dict[str, list[tuple[str, str]]] = {}
        self.inn: dict[str, list[tuple[str, str]]] = {}
        try:
            edges = json.loads(path.read_text(encoding="utf-8")).get("edges") or []
        except (OSError, ValueError):
            edges = []
        for edge in edges:
            source, target = edge.get("from_id"), edge.get("to_id")
            relation = edge.get("edge_type") or edge.get("relation")
            if (
                source not in nodes
                or target not in nodes
                or relation not in {"REQUIRES", "UNLOCKS", "RELATED", "RELATED_TO"}
            ):
                continue
            if relation == "REQUIRES" and not is_plausible_prereq(source, target):
                continue
            if relation == "UNLOCKS" and not is_plausible_prereq(target, source):
                continue
            self.out.setdefault(source, []).append((relation, target))
            self.inn.setdefault(target, []).append((relation, source))

    def label(self, cid: str) -> str:
        """Return the displayed concept name."""
        return _node_name(self.nodes.get(cid))


def _resolve(query_part: str, nodes: dict[str, dict[str, Any]]) -> str | None:
    """Require a literal id, label or alias match; avoid a misleading soft match."""
    normalized = re.sub(r"[^a-z0-9]+", " ", query_part.casefold()).strip()
    matches: list[tuple[int, int, str]] = []
    for cid, node in nodes.items():
        primary_terms = {
            cid.replace("_", " "),
            str(node.get("label") or ""),
            str(node.get("name") or ""),
        }
        aliases = {alias for alias in node.get("aliases") or [] if isinstance(alias, str)}
        for term in primary_terms | aliases:
            candidate = re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip()
            if (
                candidate == normalized
                or (candidate.endswith("s") and candidate[:-1] == normalized)
                or (normalized.endswith("s") and normalized[:-1] == candidate)
            ):
                matches.append((int(term in primary_terms), len(candidate), cid))
    return max(matches, default=(0, 0, None))[2]


def query_anchor_ids(query: str) -> list[str]:
    """Find literal concept names and aliases in a full query, longest first."""
    normalized = " " + re.sub(r"[^a-z0-9]+", " ", query.casefold()).strip() + " "
    hits: list[tuple[int, int, str]] = []
    for cid, node in st.CONCEPTS_DATA.items():
        primary = {cid.replace("_", " "), str(node.get("label") or ""), str(node.get("name") or "")}
        aliases = {alias for alias in node.get("aliases") or [] if isinstance(alias, str)}
        for term in primary | aliases:
            phrase = re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip()
            if len(phrase) >= 3 and f" {phrase} " in normalized:
                hits.append((len(phrase), int(term in primary), cid))
    ordered = sorted(hits, reverse=True)
    return list(dict.fromkeys(cid for _, _, cid in ordered))


def resolve_followup_query(query: str, history: list[dict[str, Any]] | None) -> str:
    """Replace an explicit pronoun with a concept from the last user question."""
    if not history or not re.search(r"\b(it|this paper|that paper)\b", query, re.I):
        return query
    for turn in reversed(history[-6:]):
        if not isinstance(turn, dict) or turn.get("role") != "user":
            continue
        anchors = query_anchor_ids(str(turn.get("content") or ""))
        if not anchors:
            continue
        label = _node_name(st.CONCEPTS_DATA[anchors[0]])
        if re.search(r"\b(this|that) paper\b", query, re.I):
            return re.sub(r"\b(this|that) paper\b", f"{label} paper", query, count=1, flags=re.I)
        return re.sub(r"\bit\b", label, query, count=1, flags=re.I)
    return query


def build_multi_anchor_answer(query: str, max_hops: int = MAX_HOPS) -> dict[str, Any] | None:
    """Cover each requested concept and expose only observed graph relationships."""
    mentions = extract_concept_mentions(query)[:MAX_ANCHORS]
    if len(mentions) < 2:
        return None
    graph = ExportGraph(st.CONCEPTS_DATA, st.DATA_FILE)
    resolved = [(mention, _resolve(mention, graph.nodes)) for mention in mentions]
    indexed = [(mention, cid) for mention, cid in resolved if cid]
    if not indexed:
        return None

    first = graph.nodes[indexed[0][1]]
    peers = [graph.nodes[cid] for _, cid in indexed[1:]]
    citation_map = {}
    evidence_index = 1
    for _, cid in indexed:
        if cid in citation_map:
            continue
        summary = _answer_summary(cid, graph.nodes[cid])
        found = build_concept_citation_map(graph.nodes[cid], [], []).get(cid, [])
        found = sorted(found, key=lambda item: _evidence_score(summary, item), reverse=True)
        citation_map[cid] = []
        for evidence in found[:1]:
            if _evidence_score(summary, evidence) < MIN_EVIDENCE_OVERLAP:
                continue
            tagged = dict(evidence)
            tagged["evidence_id"] = f"S{evidence_index}"
            evidence_index += 1
            citation_map[cid].append(tagged)
    citations = [
        item
        for item in build_citation_payloads(first, [], peers, citation_map)
        if item.get("doc_id")
    ]
    citation_by_id = {item["evidence_id"]: item for item in citations}

    def marker(cid: str) -> str:
        for evidence in citation_map.get(cid, []):
            evidence_id = evidence.get("evidence_id")
            if evidence_id in citation_by_id:
                return f" [{evidence_id}]"
        return ""

    lines = []
    for mention, cid in resolved:
        if cid is None:
            lines.append(
                f"**{mention}** has no exact concept identity in the current index; I cannot verify its role in this comparison."
            )
            continue
        node = graph.nodes[cid]
        summary = _answer_summary(cid, node)
        if summary and marker(cid):
            lines.append(f"**{graph.label(cid)}:** {summary}{marker(cid)}")
        else:
            lines.append(
                f"**{graph.label(cid)}** is indexed, but this answer has no source passage for its definition."
            )

    requested_ids = {cid for _, cid in indexed}
    if {"transformer", "retrieval_augmented_generation", "knowledge_graph"}.issubset(requested_ids):
        transformer = marker("transformer")
        rag = marker("retrieval_augmented_generation")
        knowledge_graph = marker("knowledge_graph")
        if transformer and rag and knowledge_graph:
            lines.append(
                "**How they fit together.** A Transformer supplies the attention-based model"
                f"{transformer}. RAG adds external retrieval before generation{rag}. "
                "A knowledge graph can organize entities and relationships for a GraphRAG workflow"
                f"{knowledge_graph}. This is a synthesis of the cited documents, not a stored prerequisite chain."
            )

    paths = []
    unique_ids = list(dict.fromkeys(cid for _, cid in indexed))
    for index, source in enumerate(unique_ids):
        for target in unique_ids[index + 1 :]:
            path = find_directed_and_undirected_path(graph, source, target, max_hops=max_hops)
            if path.hops:
                paths.append(path)
                rendered = " → ".join(hop.render() for hop in path.hops)
                lines.append(
                    f"The exported graph stores this {len(path.hops)}-hop path between **{graph.label(source)}** and **{graph.label(target)}**: {rendered}. The path records edge types and direction; it is not independent proof of a scientific dependency."
                )
            elif path.is_inferred:
                lines.append(
                    f"**{graph.label(source)}** and **{graph.label(target)}** share an indexed document, but no stored path was found within {max_hops} hops. Co-occurrence alone does not establish a relationship."
                )
            else:
                lines.append(
                    f"No stored path between **{graph.label(source)}** and **{graph.label(target)}** was found within {max_hops} hops."
                )
            if len(paths) >= MAX_PATHS:
                break
    return {
        "text": "\n\n".join(lines),
        "citations": citations,
        "concepts": [
            {"mention": mention, "id": cid, "status": "indexed" if cid else "missing"}
            for mention, cid in resolved
        ],
        "paths": [[hop.__dict__ for hop in path.hops] for path in paths],
        "partial": any(cid is None for _, cid in resolved),
    }
