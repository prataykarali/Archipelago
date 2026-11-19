#!/usr/bin/env python3
"""CLI entrypoint for S5-D1 Preflight Validator.

Validates either legacy v1 (`s5d0_adjudicated_gold_v1`) or versioned A/C v2
(`s5d1_adjudicated_gold_ac_v2`) gold labels + negative controls without running
any retrieval effectiveness evaluation.
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

from d1_pipeline.constants import DEFAULT_FROZEN_POOL, DEFAULT_FROZEN_RANKINGS  # noqa: E402
from d1_pipeline.preflight import validate_d1_preflight  # noqa: E402
from d1_pipeline.synthetic import build_synthetic_bundle  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for S5-D1 preflight validation."""
    parser = argparse.ArgumentParser(
        description="S5-D1 Preflight Validator (read-only; supports legacy v1 and A/C v2 schemas)."
    )
    parser.add_argument("--gold-labels", type=Path, help="Path to adjudicated gold-label JSON.")
    parser.add_argument(
        "--frozen-pool",
        type=Path,
        default=DEFAULT_FROZEN_POOL,
        help="Path to frozen blinded 254-pair pool JSON.",
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
        help="Optional JSON mapping passage_id -> text for verbatim quote verification.",
    )
    parser.add_argument(
        "--schema-mode",
        choices=("auto", "v1", "ac_v2"),
        default="auto",
        help="Gold-label schema contract to enforce (default: auto).",
    )
    parser.add_argument(
        "--synthetic-demo",
        action="store_true",
        help="Run preflight on a self-contained deterministic SYNTHETIC bundle.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Execute S5-D1 preflight validation and return process exit code."""
    args = parse_args(argv)

    if args.synthetic_demo:
        with tempfile.TemporaryDirectory(prefix="s5d1_syn_preflight_") as tmp_dir:
            bundle = build_synthetic_bundle(Path(tmp_dir), schema_mode="ac_v2")
            result = validate_d1_preflight(
                gold_labels_path=bundle["gold"],
                frozen_pool_path=bundle["pool"],
                frozen_rankings_path=bundle["rankings"],
                corpus_passages_path=bundle["passages"],
                schema_mode="ac_v2",
                is_synthetic=True,
            )
    else:
        if args.gold_labels is None:
            print("ERROR: --gold-labels is required (or pass --synthetic-demo).", file=sys.stderr)
            return 2
        result = validate_d1_preflight(
            gold_labels_path=args.gold_labels,
            frozen_pool_path=args.frozen_pool,
            frozen_rankings_path=args.frozen_rankings,
            neg_control_path=args.neg_control_file,
            corpus_passages_path=args.corpus_passages,
            schema_mode=args.schema_mode,
            is_synthetic=False,
        )

    rendered = json.dumps(result.to_dict(), indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
