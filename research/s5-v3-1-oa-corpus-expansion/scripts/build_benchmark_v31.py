"""CLI to build/validate S5-v3.1 proposed benchmark and blinded audit workbooks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from benchmark_v31.audit_validator import (
    validate_blank_workbook,
    validate_completed_submission,
)
from benchmark_v31.audit_workbook import generate_private_audit_workbooks
from benchmark_v31.builder import build_benchmark_manifest, write_manifest
from benchmark_v31.constants import (
    DEFAULT_AUDIT_SCHEMA_OUTPUT,
    DEFAULT_CORPUS_V31_JSONL,
    DEFAULT_GRAPH_JSON,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_PRIVATE_AUDIT_DIR,
    DEFAULT_V3_PROPOSED_JSON,
    DEFAULT_V21_SPECS_JSON,
)
from benchmark_v31.corpus_index import load_corpus_metadata
from benchmark_v31.graph_anchors import GraphAnchorIndex
from benchmark_v31.leakage import load_v21_queries
from benchmark_v31.queries_catalog import get_proposed_v31_query_drafts
from benchmark_v31.schema import QuerySpec
from benchmark_v31.validator import validate_benchmark


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or validate the S5-v3.1 proposed query benchmark."
    )
    parser.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=Path(DEFAULT_CORPUS_V31_JSONL),
    )
    parser.add_argument(
        "--graph-json",
        type=Path,
        default=Path(DEFAULT_GRAPH_JSON),
    )
    parser.add_argument(
        "--v21-specs",
        type=Path,
        default=Path(DEFAULT_V21_SPECS_JSON),
    )
    parser.add_argument(
        "--v3-proposed",
        type=Path,
        default=Path(DEFAULT_V3_PROPOSED_JSON),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_MANIFEST_OUTPUT),
    )
    parser.add_argument(
        "--audit-schema-output",
        type=Path,
        default=Path(DEFAULT_AUDIT_SCHEMA_OUTPUT),
    )
    parser.add_argument(
        "--private-audit-dir",
        type=Path,
        default=Path(DEFAULT_PRIVATE_AUDIT_DIR),
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing manifest without rewriting.",
    )
    parser.add_argument(
        "--validate-submission",
        type=Path,
        default=None,
        help="Validate a completed human query-audit JSON submission.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Build or validate S5-v3.1 benchmark manifest and audit workbooks."""
    args = _parse_args(argv)

    if args.validate_submission is not None:
        manifest = json.loads(args.output.read_text(encoding="utf-8"))
        expected = frozenset(
            str(q["query_id"]) for q in manifest.get("queries", [])
        )
        sub = json.loads(args.validate_submission.read_text(encoding="utf-8"))
        res = validate_completed_submission(sub, expected_query_ids=expected)
        for issue in res.issues:
            print(f"[ERROR] {issue.item_id} ({issue.code}): {issue.message}")
        print(
            f"Submission validation: items={res.item_count} "
            f"errors={len(res.issues)}"
        )
        return 0 if res.is_valid else 1

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
        for issue in report.issues:
            print(
                f"[{issue.severity}] {issue.query_id} ({issue.code}): "
                f"{issue.message}"
            )
        print(
            f"Validated {report.total_queries} queries: "
            f"errors={report.error_count} splits={report.split_counts} "
            f"domains={report.domain_counts}"
        )
        return 0 if report.is_valid else 1

    drafts = get_proposed_v31_query_drafts()
    manifest, report = build_benchmark_manifest(
        drafts=drafts,
        corpus_jsonl_path=args.corpus_jsonl,
        graph_json_path=args.graph_json,
        v21_specs_path=args.v21_specs,
        v3_proposed_path=args.v3_proposed,
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
    audit_info = generate_private_audit_workbooks(
        proposed_manifest_path=args.output,
        corpus_jsonl_path=args.corpus_jsonl,
        private_audit_dir=args.private_audit_dir,
        public_schema_path=args.audit_schema_output,
    )
    expected = frozenset(
        str(q["query_id"]) for q in manifest.get("queries", [])
    )
    blank_payload = json.loads(
        Path(audit_info["private_json"]).read_text(encoding="utf-8")
    )
    blank_res = validate_blank_workbook(
        blank_payload, expected_query_ids=expected, require_no_raw_text=False
    )
    if not blank_res.is_valid:
        print("Generated private workbook failed blank validation!")
        return 1

    print(
        json.dumps(
            {
                "manifest_output": str(args.output),
                "summary": manifest["summary"],
                "audit_workbooks": audit_info,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
