"""Live S5 acceptance: real providers, local store. Not proof of hosted durability.

Usage: python scripts/validation/s5_acceptance.py OUT_DIR
Checks metadata correctness and basic topical eligibility only (no ranking metrics).
"""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from archipelago.scholarly.intelligence.graph import build_graph  # noqa: E402
from archipelago.scholarly.intelligence.search import discover, topic_matches  # noqa: E402
from archipelago.scholarly.intelligence.workbook import HEADERS, build_workbook  # noqa: E402

TOPICS = [
    "graph neural networks",
    "retrieval-augmented generation",
    "continual learning",
    "computer vision OCR",
    "Bengali speech recognition",
]


def check(topic: str, count: int, out: Path) -> dict:
    run = discover({"topic": topic, "top_k": count})
    papers = run["papers"]
    dois = [p["doi"] for p in papers if p["doi"]]
    graph = build_graph(run)
    kinds: dict[str, int] = {}
    for n in graph["nodes"]:
        kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
    edges: dict[str, int] = {}
    for e in graph["edges"]:
        edges[e["type"]] = edges.get(e["type"], 0) + 1
    data = build_workbook(run).getvalue()
    name = out / f"{topic.replace(' ', '_')}_{count}.xlsx"
    name.write_bytes(data)
    book = load_workbook(BytesIO(data))
    ids = {r[0] for r in book["Papers"].iter_rows(min_row=2, values_only=True)}
    fk_ok = all(
        r[1] in ids for r in book["Topic_Results"].iter_rows(min_row=2, values_only=True)
    ) and all(r[0] in ids for r in book["Sources_Provenance"].iter_rows(min_row=2, values_only=True))
    n = len(papers) or 1
    return {
        "topic": topic,
        "requested": count,
        "returned": len(papers),
        "candidates": run["candidate_count"],
        "providers": {s["source"]: f"{s['status']}:{s['record_count']}" for s in run["sources"]},
        "unique_paper_ids": len({p["paper_id"] for p in papers}) == len(papers),
        "doi_coverage": f"{len(dois)}/{len(papers)}",
        "duplicate_dois": len(dois) - len(set(d.casefold() for d in dois)),
        "topic_mismatches": sum(
            not topic_matches(topic, p["title"], p["abstract"], " ".join(p["topics"]))
            for p in papers
        ),
        "abstract_coverage": f"{sum(bool(p['abstract']) for p in papers)}/{len(papers)}",
        "authors_with_provider_id": f"{sum(bool(p['author_ids']) and any(p['author_ids']) for p in papers)}/{len(papers)}",
        "venue_coverage": f"{sum(bool(p['venue']) for p in papers)}/{len(papers)}",
        "reference_coverage": f"{sum(bool(p['references']) for p in papers)}/{len(papers)}",
        "citation_coverage": f"{sum(p['citation_count'] is not None for p in papers)}/{len(papers)}",
        "methods_found": sum(bool(p["methods"]) for p in papers),
        "author_observations": len(run.get("author_observations", [])),
        "graph_nodes": kinds,
        "graph_edges": edges,
        "workbook": str(name),
        "sheets_ok": book.sheetnames == list(HEADERS),
        "foreign_keys_ok": fk_ok,
        "avg_n": n,
    }


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    results = [check(t, 20, out) for t in TOPICS] + [check(TOPICS[0], 50, out)]
    (out / "s5_acceptance.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
