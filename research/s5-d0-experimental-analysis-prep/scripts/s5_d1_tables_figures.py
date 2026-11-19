#!/usr/bin/env python3
"""CLI entrypoint for S5-D1 reproducible tables (MD/LaTeX/CSV) and SVG figures.

Automatically propagates prominent `SYNTHETIC` watermarking to all filenames,
headers, captions, CSV metadata, and SVG plot titles/watermarks whenever the
input evaluation report has `is_synthetic: true`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from d1_pipeline.figures import generate_all_figures  # noqa: E402
from d1_pipeline.tables import generate_all_tables  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for table and figure generation."""
    parser = argparse.ArgumentParser(
        description="Generate reproducible Markdown/LaTeX/CSV tables and SVG figures from an S5-D1 report."
    )
    parser.add_argument(
        "--eval-report",
        type=Path,
        required=True,
        help="Path to S5-D1 evaluation report JSON (produced by s5_d1_evaluate.py).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where generated tables and figures will be written.",
    )
    parser.add_argument(
        "--force-synthetic-watermark",
        action="store_true",
        help="Force SYNTHETIC prefix and watermark on all generated artifacts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Generate all tables and figures and print JSON manifest of written paths."""
    args = parse_args(argv)
    if not args.eval_report.exists():
        print(f"ERROR: Evaluation report not found: {args.eval_report}", file=sys.stderr)
        return 1

    report = json.loads(args.eval_report.read_text(encoding="utf-8"))
    is_syn = bool(report.get("is_synthetic", False)) or args.force_synthetic_watermark

    tables = generate_all_tables(
        report,
        args.output_dir / "tables",
        force_synthetic=is_syn,
    )
    figures = generate_all_figures(
        report,
        args.output_dir / "figures",
        force_synthetic=is_syn,
    )

    manifest = {
        "is_synthetic": is_syn,
        "tables": tables,
        "figures": figures,
    }
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
