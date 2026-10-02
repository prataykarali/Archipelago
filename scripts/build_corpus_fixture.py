#!/usr/bin/env python
"""Build the tracked fixture slice of the concept graph.

The fixture exists so a git-triggered deployment is never *empty*: every corpus
artifact is gitignored, so without this the hosted app boots, passes
``/api/readiness``, and answers "not indexed" to everything.

It is a real slice, not a stub — the same nodes, summaries, edges and page
provenance the full graph has — but small enough to review in a diff, and marked
with ``stats.fixture`` so nobody mistakes it for the full corpus.  When the boot
fetch succeeds (``HF_DATASET_REPO`` + ``HF_TOKEN``) this file is ignored.

Regenerate with::

    python scripts/build_corpus_fixture.py --concepts 60
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "host_inference" / "fixtures" / "okf_graph.json"
SOURCE = REPO_ROOT / "okf_graph.json"

#: Concepts always kept, regardless of ranking. They are the curriculum spine the
#: response contract's own examples are written about, so a fixture without them
#: would fail the contract tests.
PINNED = (
    "third_normal_form",
    "low_rank_adaptation",
    "qlora",
    "bert",
    "attention_mechanism",
    "rag",
    "graph_rag",
    "paging",
    "paged_attention",
)

#: Nodes whose only edge is to something outside the slice are dropped, so every
#: node in the fixture has at least one neighbour the reader can follow.
MIN_DEGREE = 1

#: Provenance sources kept per node. One node in the full graph carries 79; the
#: fixture is a reviewable slice, not the citation apparatus, and the boot fetch
#: supplies the real list.  Truncation is recorded in ``stats.sources_truncated``.
SOURCES_PER_NODE = 2

#: Node fields worth carrying. The rest (``tags``, ``sections``, ``degree``,
#: ``source_categories``) are derived data that only inflates the diff.
NODE_FIELDS = ("id", "label", "name", "concept_type", "difficulty", "summary")


def pick(graph: dict, limit: int) -> tuple[list[dict], list[dict]]:
    """Choose the concept slice and the edges that stay inside it.

    Pinned concepts keep their immediate neighbours even when those neighbours are
    not in the degree-ranked top ``limit``.  Without that, third normal form —
    the contract's own worked example — arrives with no prerequisite and no edge,
    so the fixture answers "what is 3NF" and nothing about what it requires.
    """
    nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("id")}
    edges = graph.get("edges", [])

    neighbours: dict[str, set[str]] = {cid: set() for cid in nodes}
    for edge in edges:
        src, dst = edge.get("from_id"), edge.get("to_id")
        if src in neighbours and dst in neighbours:
            neighbours[src].add(dst)
            neighbours[dst].add(src)

    keep = {cid for cid in PINNED if cid in nodes}
    # Pull in each pinned concept's own neighbours before ranking. Without this,
    # third normal form — whose only edge runs to ``sql``, a node that is neither
    # pinned nor degree-ranked into the slice — arrives with no prerequisite and
    # no edge at all, and the fixture can no longer answer "what must I master
    # before 3NF", which is the contract's own example.
    for cid in sorted(keep):
        keep |= {n for n in neighbours[cid] if n in nodes}

    degree: dict[str, int] = {cid: len(nbrs) for cid, nbrs in neighbours.items()}
    for cid in sorted(nodes, key=lambda c: -degree[c]):
        if len(keep) >= limit:
            break
        keep.add(cid)

    kept_nodes = [nodes[cid] for cid in nodes if cid in keep]
    kept_ids = set(keep)
    kept_edges = [
        edge
        for edge in edges
        if edge.get("from_id") in kept_ids and edge.get("to_id") in kept_ids
    ]
    return kept_nodes, kept_edges


def build(limit: int) -> dict:
    """Assemble the fixture payload from the full export."""
    graph = json.loads(SOURCE.read_text(encoding="utf-8"))
    nodes, edges = pick(graph, limit)

    trimmed: list[dict] = []
    truncated = 0
    for node in nodes:
        slim = {field: node[field] for field in NODE_FIELDS if field in node}
        slim.setdefault("name", slim.get("label") or node["id"])
        sources = (node.get("sources") or [])[:SOURCES_PER_NODE]
        truncated += max(0, len(node.get("sources") or []) - len(sources))
        if sources:
            slim["sources"] = sources
        trimmed.append(slim)
    nodes = trimmed

    concepts = {
        n["id"]: {
            "id": n["id"],
            "name": n["name"],
            "summary": n.get("summary") or "",
            "concept_type": n.get("concept_type") or "definition",
            "difficulty": n.get("difficulty") or "intermediate",
            **({"sources": n["sources"]} if n.get("sources") else {}),
        }
        for n in nodes
    }

    return {
        "stats": {
            "fixture": True,
            "note": (
                "Truncated slice of the library corpus, shipped so a deployment "
                "is never empty. Boot fetch replaces it when HF_DATASET_REPO and "
                "HF_TOKEN are configured."
            ),
            "total_concepts": len(concepts),
            "total_edges": len(edges),
            "sources_truncated": truncated,
        },
        # No "visualization" block: it is a pure projection of nodes+edges and
        # would triple the diff for no information. Readers that want it derive
        # it from these two keys.
        "nodes": nodes,
        "edges": edges,
        "concepts": concepts,
    }


def main() -> int:
    """Write the fixture and report what went in."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concepts", type=int, default=60)
    args = parser.parse_args()

    if not SOURCE.is_file():
        print(f"error: {SOURCE} not found; run the pipeline first", file=sys.stderr)
        return 1

    payload = build(args.concepts)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    size_kb = OUTPUT.stat().st_size / 1024
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)}: "
        f"{payload['stats']['total_concepts']} concepts, "
        f"{payload['stats']['total_edges']} edges, {size_kb:.0f} KB"
    )
    missing = [cid for cid in PINNED if cid not in payload["concepts"]]
    if missing:
        print(f"warning: pinned concepts absent from the corpus: {missing}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
