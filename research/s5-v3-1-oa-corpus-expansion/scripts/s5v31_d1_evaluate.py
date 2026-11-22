#!/usr/bin/env python3
"""CLI for versioned S5-v3.1 D1 preflight, authorization gate, evaluation, and table export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from eval_v31 import (  # noqa: E402
    V31AuthorizationError,
    V31PreflightError,
    compute_v31_d1_evaluation,
    validate_v31_authorization_gate,
    validate_v31_preflight,
    write_results_tables,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run S5-v3.1 D1 preflight and fail-closed effectiveness evaluation."
    )
    parser.add_argument("--gold-labels", type=Path, required=True)
    parser.add_argument("--retrieval-diagnostics", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--query-manifest", type=Path, default=None)
    parser.add_argument("--pool", type=Path, default=None)
    parser.add_argument("--retrieval-manifest", type=Path, default=None)
    parser.add_argument("--nc-verification", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--synthetic-run", action="store_true")
    parser.add_argument("--authorize-real-v31-d1", action="store_true")
    parser.add_argument("--authorization-file", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    preflight = validate_v31_preflight(
        gold_labels_path=args.gold_labels,
        retrieval_diagnostics_path=args.retrieval_diagnostics,
        corpus_path=args.corpus,
        query_manifest_path=args.query_manifest,
        pool_path=args.pool,
        retrieval_manifest_path=args.retrieval_manifest,
        nc_verification_path=args.nc_verification,
        is_synthetic=args.synthetic_run,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "SYNTHETIC_" if args.synthetic_run else "s5v31_d1_"
    preflight_out = args.output_dir / f"{prefix}preflight_report.json"
    preflight_out.write_text(json.dumps(preflight.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not preflight.passed:
        print(json.dumps(preflight.to_dict(), indent=2, sort_keys=True))
        return 2

    if args.preflight_only:
        print(json.dumps(preflight.to_dict(), indent=2, sort_keys=True))
        return 0

    auth_record = None
    if not args.synthetic_run:
        try:
            auth_record = validate_v31_authorization_gate(
                authorize_flag=args.authorize_real_v31_d1,
                authorization_path=args.authorization_file,
                expected_hashes=preflight.expected_hashes,
            )
        except V31AuthorizationError as exc:
            print(json.dumps({"error": "AUTHORIZATION_REFUSED", "detail": str(exc)}, indent=2))
            return 3

    try:
        report = compute_v31_d1_evaluation(
            gold_labels_path=args.gold_labels,
            retrieval_diagnostics_path=args.retrieval_diagnostics,
            preflight=preflight,
            query_manifest_path=args.query_manifest,
            authorization_record=auth_record,
        )
    except V31PreflightError as exc:
        print(json.dumps({"error": "EVALUATION_REFUSED", "detail": str(exc)}, indent=2))
        return 4

    report_out = args.output_dir / f"{prefix}evaluation_report.json"
    report_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tables = write_results_tables(report, args.output_dir)

    print(
        json.dumps(
            {
                "preflight": str(preflight_out),
                "report": str(report_out),
                "tables": {k: str(v) for k, v in tables.items()},
                "is_synthetic": args.synthetic_run,
                "pool_depth_k": report["pool_depth_k"],
                "system_count": len(report["systems"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
