#!/usr/bin/env python3
"""Run relevance-agnostic technical diagnostics for S5-v3 retrieval variants.

Preserves all six frozen S5-v2.1 systems untouched. Produces ONLY technical
diagnostics (latency, memory, anchor hit rate, fallback rate, short-list rate,
backfill count, graph coverage). NEVER computes effectiveness metrics or
fabricates human relevance labels.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from retrieval_v3 import (  # noqa: E402
    SCHEMA_VERSION,
    BM25LexicalControl,
    RetrievalV3Engine,
    aggregate_variant_diagnostics,
    build_standard_v3_variants,
    load_corpus_v3_passages,
    load_okf_graph,
)

REPO_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CORPUS_PATH = (
    REPO_ROOT / "data" / "annotation_local" / "s5v3" / "corpus_v3" / "s5v3_corpus_passages.jsonl"
)
DEFAULT_GRAPH_PATH = REPO_ROOT / "okf_graph.json"
DEFAULT_QUERIES_PATH = (
    REPO_ROOT
    / "research"
    / "s5-v3-benchmark-expansion"
    / "manifests"
    / "s5v3_query_benchmark_proposed.json"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "research"
    / "s5-v3-benchmark-expansion"
    / "reports"
    / "s5v3_retrieval_diagnostics.json"
)


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_queries(queries_path: Path) -> list[tuple[str, str]]:
    """Load (query_id, query_text) pairs deterministically from JSON or JSONL."""
    raw_text = queries_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    rows: list[dict[str, Any]]
    if queries_path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    else:
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict) and isinstance(parsed.get("queries"), list):
            rows = parsed["queries"]
        else:
            raise ValueError(f"Unsupported query file structure in {queries_path}")

    queries: list[tuple[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        qid = str(row.get("query_id") or row.get("id") or f"q_{idx:03d}")
        qtext = str(row.get("query_text") or row.get("query") or row.get("text") or "").strip()
        if not qtext:
            continue
        queries.append((qid, qtext))
    return queries


def run_diagnostics(
    corpus_path: Path,
    graph_path: Path,
    queries_path: Path,
    output_path: Path,
    *,
    top_k: int | None = None,
) -> dict[str, Any]:
    """Run all standard S5-v3 variants and write relevance-agnostic diagnostics JSON."""
    passages = load_corpus_v3_passages(corpus_path)
    concepts, edges = load_okf_graph(graph_path)
    queries = load_queries(queries_path)

    variants = build_standard_v3_variants()
    if top_k is not None:
        from dataclasses import replace

        variants = [replace(cfg, top_k=top_k) for cfg in variants]

    shared_lexical = BM25LexicalControl(passages)
    variant_reports: dict[str, Any] = {}
    config_hashes: dict[str, str] = {}

    for cfg in variants:
        engine = RetrievalV3Engine(
            cfg,
            passages,
            concepts,
            edges,
            shared_lexical=shared_lexical,
        )
        q_results = [engine.search_query(qid, qtext) for qid, qtext in queries]
        variant_reports[cfg.variant_name] = aggregate_variant_diagnostics(engine, q_results)
        config_hashes[cfg.variant_name] = engine.config_sha256

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "effectiveness_evaluation": "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS",
        "scientific_boundary_notice": (
            "This report contains strictly relevance-agnostic technical diagnostics "
            "(latency, memory, anchor hit rate, fallback rate, short-list rate, "
            "backfill count, graph coverage). No human relevance labels exist yet; "
            "no retrieval effectiveness or system superiority claims are made."
        ),
        "frozen_v2_1_controls_modified": False,
        "inputs": {
            "corpus_path_relative": str(corpus_path.relative_to(REPO_ROOT))
            if corpus_path.is_relative_to(REPO_ROOT)
            else str(corpus_path),
            "corpus_sha256": sha256_file(corpus_path),
            "corpus_passage_count": len(passages),
            "graph_path_relative": str(graph_path.relative_to(REPO_ROOT))
            if graph_path.is_relative_to(REPO_ROOT)
            else str(graph_path),
            "graph_sha256": sha256_file(graph_path),
            "graph_concept_count": len(concepts),
            "graph_edge_count": len(edges),
            "queries_path_relative": str(queries_path.relative_to(REPO_ROOT))
            if queries_path.is_relative_to(REPO_ROOT)
            else str(queries_path),
            "queries_sha256": sha256_file(queries_path),
            "query_count": len(queries),
        },
        "variant_config_hashes": config_hashes,
        "variants": variant_reports,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run S5-v3 relevance-agnostic retrieval technical diagnostics."
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--top-k", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    report = run_diagnostics(
        args.corpus,
        args.graph,
        args.queries,
        args.output,
        top_k=args.top_k,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "query_count": report["inputs"]["query_count"],
                "passage_count": report["inputs"]["corpus_passage_count"],
                "variant_config_hashes": report["variant_config_hashes"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
