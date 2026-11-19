"""CLI to build and validate the S5-v3 proposed query benchmark manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from benchmark_v3.builder import build_benchmark_manifest, write_manifest
from benchmark_v3.constants import (
    DEFAULT_CORPUS_JSONL,
    DEFAULT_GRAPH_JSON,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_V21_SPECS_JSON,
)
from benchmark_v3.corpus_index import load_corpus_metadata
from benchmark_v3.graph_anchors import GraphAnchorIndex
from benchmark_v3.leakage import load_v21_queries
from benchmark_v3.queries_catalog import get_proposed_query_drafts
from benchmark_v3.schema import QuerySpec
from benchmark_v3.validator import validate_benchmark


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or validate the S5-v3 proposed query benchmark."
    )
    parser.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=Path(DEFAULT_CORPUS_JSONL),
        help="Path to Corpus v3 passages JSONL.",
    )
    parser.add_argument(
        "--graph-json",
        type=Path,
        default=Path(DEFAULT_GRAPH_JSON),
        help="Path to canonical okf_graph.json.",
    )
    parser.add_argument(
        "--v21-specs",
        type=Path,
        default=Path(DEFAULT_V21_SPECS_JSON),
        help="Path to frozen S5-v2.1 blinded query specs JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_MANIFEST_OUTPUT),
        help="Output path for metadata-only proposed benchmark manifest.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing manifest at --output without rewriting.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for building or validating the S5-v3 benchmark."""
    args = _parse_args(argv)
    if args.validate_only:
        raw = json.loads(args.output.read_text(encoding="utf-8"))
        queries = [QuerySpec.from_dict(item) for item in raw.get("queries", [])]
        corpus_index = load_corpus_metadata(args.corpus_jsonl)
        graph_index = GraphAnchorIndex.from_json_path(args.graph_json)
        v21_queries = load_v21_queries(args.v21_specs)
        report = validate_benchmark(
            queries=queries,
            corpus_index=corpus_index,
            graph_index=graph_index,
            v21_queries=v21_queries,
            enforce_size_bounds=True,
        )
        print(
            f"Validated {report.total_queries} queries: "
            f"errors={report.error_count} splits={report.split_counts} "
            f"categories={report.category_counts} regimes={report.regime_counts}"
        )
        for issue in report.issues:
            print(
                f"[{issue.severity}] {issue.query_id} ({issue.code}): "
                f"{issue.message}"
            )
        return 0 if report.is_valid else 1

    drafts = get_proposed_query_drafts()
    manifest, report = build_benchmark_manifest(
        drafts=drafts,
        corpus_jsonl_path=args.corpus_jsonl,
        graph_json_path=args.graph_json,
        v21_specs_path=args.v21_specs,
        enforce_size_bounds=True,
    )
    for issue in report.issues:
        print(
            f"[{issue.severity}] {issue.query_id} ({issue.code}): "
            f"{issue.message}"
        )
    if not report.is_valid:
        print(f"Build aborted: {report.error_count} validation errors.")
        return 1

    write_manifest(manifest, args.output)
    print(
        f"Wrote {args.output} ({report.total_queries} queries): "
        f"splits={report.split_counts} categories={report.category_counts} "
        f"regimes={report.regime_counts}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
