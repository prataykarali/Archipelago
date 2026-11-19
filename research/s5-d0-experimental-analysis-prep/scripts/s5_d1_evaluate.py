#!/usr/bin/env python3
"""CLI entrypoint for S5-D1 Read-Only Effectiveness Evaluation.

Safety & Governance Defaults:
- Default mode is `--synthetic-only`, running on deterministic synthetic test
  fixtures with prominent `SYNTHETIC` watermarking.
- Real S5-D1 execution requires BOTH:
  1. Passing preflight on validated human gold + negative-control files, AND
  2. Explicit `--authorize-real-d1` flag + matching `--auth-artifact` JSON
     containing investigator ID, explicit approval declaration, UTC timestamp,
     and exact SHA-256 hashes of the validated gold, negative-control, pool,
     and rankings files.
- Never modifies frozen datasets, corpora, rankings, or workbooks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from d1_pipeline.auth_gate import (  # noqa: E402
    AuthorizationError,
    authorization_template,
    validate_investigator_authorization,
)
from d1_pipeline.constants import (  # noqa: E402
    DEFAULT_FROZEN_POOL,
    DEFAULT_FROZEN_RANKINGS,
    SYNTHETIC_PREFIX,
)
from d1_pipeline.metrics import compute_d1_evaluation  # noqa: E402
from d1_pipeline.preflight import validate_d1_preflight  # noqa: E402
from d1_pipeline.synthetic import build_synthetic_bundle  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for S5-D1 read-only evaluation."""
    parser = argparse.ArgumentParser(
        description="S5-D1 Read-Only Effectiveness Evaluation (defaults to --synthetic-only)."
    )
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Run on self-contained deterministic SYNTHETIC fixtures (default when --authorize-real-d1 is absent).",
    )
    parser.add_argument(
        "--authorize-real-d1",
        action="store_true",
        help="Explicitly authorize real S5-D1 execution (requires passing preflight AND valid --auth-artifact).",
    )
    parser.add_argument(
        "--auth-artifact",
        type=Path,
        default=None,
        help="Path to signed investigator authorization JSON artifact (required with --authorize-real-d1).",
    )
    parser.add_argument(
        "--print-auth-template",
        action="store_true",
        help="Print blank investigator authorization JSON template and exit.",
    )
    parser.add_argument("--gold-labels", type=Path, default=None, help="Path to validated gold-label JSON.")
    parser.add_argument(
        "--frozen-pool",
        type=Path,
        default=DEFAULT_FROZEN_POOL,
        help="Path to frozen blinded pool JSON.",
    )
    parser.add_argument(
        "--frozen-rankings",
        type=Path,
        default=DEFAULT_FROZEN_RANKINGS,
        help="Path to frozen six-system ranked results JSON.",
    )
    parser.add_argument(
        "--neg-control-file",
        type=Path,
        default=None,
        help="Optional separate negative-control verification JSON file.",
    )
    parser.add_argument(
        "--corpus-passages",
        type=Path,
        default=None,
        help="Optional JSON mapping passage_id -> text for verbatim quote checks.",
    )
    parser.add_argument(
        "--schema-mode",
        choices=("auto", "v1", "ac_v2"),
        default="auto",
        help="Gold-label schema contract to enforce (default: auto).",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args(argv)


def _ensure_synthetic_filename(path: Path) -> Path:
    if not path.name.startswith(SYNTHETIC_PREFIX):
        return path.with_name(f"{SYNTHETIC_PREFIX}{path.name}")
    return path


def main(argv: list[str] | None = None) -> int:
    """Run S5-D1 evaluation in synthetic-only or explicitly authorized real mode."""
    args = parse_args(argv)

    if args.print_auth_template:
        print(json.dumps(authorization_template(), indent=2))
        return 0

    # Real D1 path: strictly gated
    if args.authorize_real_d1:
        if args.synthetic_only:
            print("ERROR: Cannot combine --synthetic-only with --authorize-real-d1.", file=sys.stderr)
            return 2
        if args.gold_labels is None:
            print("ERROR: --gold-labels is required for --authorize-real-d1.", file=sys.stderr)
            return 2

        preflight = validate_d1_preflight(
            gold_labels_path=args.gold_labels,
            frozen_pool_path=args.frozen_pool,
            frozen_rankings_path=args.frozen_rankings,
            neg_control_path=args.neg_control_file,
            corpus_passages_path=args.corpus_passages,
            schema_mode=args.schema_mode,
            is_synthetic=False,
        )
        if not preflight.passed:
            print(json.dumps(preflight.to_dict(), indent=2), file=sys.stderr)
            return 1

        try:
            auth_record = validate_investigator_authorization(
                authorize_real_d1_flag=True,
                auth_artifact_path=args.auth_artifact,
                preflight=preflight,
            )
        except AuthorizationError as exc:
            print(f"AUTHORIZATION REFUSED: {exc}", file=sys.stderr)
            return 3

        report = compute_d1_evaluation(
            frozen_rankings_path=args.frozen_rankings,
            gold_labels_path=args.gold_labels,
            preflight=preflight,
            authorization_record=auth_record,
        )
        out_path = args.output
    else:
        # Default safe mode: synthetic-only
        if args.gold_labels is not None and not args.synthetic_only:
            print(
                "AUTHORIZATION REFUSED: Real --gold-labels supplied without --authorize-real-d1 "
                "and --auth-artifact. Pass --synthetic-only to run on synthetic fixtures.",
                file=sys.stderr,
            )
            return 3

        with tempfile.TemporaryDirectory(prefix="s5d1_syn_eval_") as tmp_dir:
            bundle = build_synthetic_bundle(Path(tmp_dir), schema_mode="ac_v2")
            preflight = validate_d1_preflight(
                gold_labels_path=bundle["gold"],
                frozen_pool_path=bundle["pool"],
                frozen_rankings_path=bundle["rankings"],
                corpus_passages_path=bundle["passages"],
                schema_mode="ac_v2",
                is_synthetic=True,
            )
            report = compute_d1_evaluation(
                frozen_rankings_path=bundle["rankings"],
                gold_labels_path=bundle["gold"],
                preflight=preflight,
                authorization_record=None,
            )
        out_path = _ensure_synthetic_filename(args.output) if args.output is not None else None

    rendered = json.dumps(report, indent=2) + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
        print(f"Wrote evaluation report to {out_path}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
