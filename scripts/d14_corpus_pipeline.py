#!/usr/bin/env python3
"""Reproducible CLI runner for Archipelago D14.1 corpus reconstruction (corpus_v3_d14).

Usage:
    python3 scripts/d14_corpus_pipeline.py
    python3 scripts/d14_corpus_pipeline.py --offline
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archipelago.corpus.acquire import DEFAULT_HF_CACHE_SNAPSHOT  # noqa: E402
from archipelago.corpus.pipeline import (  # noqa: E402
    DEFAULT_GRAPH_REL_PATH,
    DEFAULT_OUTPUT_REL_DIR,
    DEFAULT_REPORTS_REL_DIR,
    PipelineConfig,
    run_pipeline,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for the D14.1 corpus pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / DEFAULT_OUTPUT_REL_DIR,
        help="Gitignored directory for raw OA artifacts and d14_candidate_passages_v3.jsonl.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPO_ROOT / DEFAULT_REPORTS_REL_DIR,
        help="Directory for D14_SOURCE_*, D14_CORPUS_*, and D14_INGESTION_REPORT.md.",
    )
    parser.add_argument(
        "--graph-path",
        type=Path,
        default=REPO_ROOT / DEFAULT_GRAPH_REL_PATH,
        help="Read-only path to okf_graph.json for concept association.",
    )
    parser.add_argument(
        "--hf-cache-dir",
        type=Path,
        default=DEFAULT_HF_CACHE_SNAPSHOT,
        help="Local Hugging Face snapshot directory for baseline corpus_v2_d10_3025 PDFs.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable outbound downloads; only use cached local artifacts.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO logging during ingestion.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Execute the D14.1 corpus pipeline and print a concise JSON summary."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = PipelineConfig(
        repo_root=REPO_ROOT,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
        graph_path=args.graph_path,
        hf_cache_dir=args.hf_cache_dir,
        allow_network=not args.offline,
    )
    manifest = run_pipeline(config)
    print(
        json.dumps(
            {
                "corpus_version": manifest["corpus_version"],
                "passage_index_sha256": manifest["passage_index_sha256"],
                "totals": manifest["totals"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
