#!/usr/bin/env python3
"""CLI entry point for building S5-v3 Corpus v3 and its metadata-only manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from corpus_v3.builder import build_corpus_v3  # noqa: E402
from corpus_v3.constants import (  # noqa: E402
    DEFAULT_OUTPUT_JSONL,
    DEFAULT_OUTPUT_MANIFEST,
)

REPO_ROOT_DEPTH = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for Corpus v3 builder."""
    default_root = Path(__file__).resolve().parents[REPO_ROOT_DEPTH]
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic S5-v3 Corpus v3 from verified local OA sources "
            "and emit metadata-only manifest."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=default_root,
        help="Repository root directory.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=None,
        help="Output path for private Git-ignored passage JSONL.",
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=None,
        help="Output path for public metadata-only manifest JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run Corpus v3 build and print a concise JSON summary."""
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_jsonl = (
        args.output_jsonl.resolve()
        if args.output_jsonl is not None
        else (repo_root / DEFAULT_OUTPUT_JSONL)
    )
    output_manifest = (
        args.output_manifest.resolve()
        if args.output_manifest is not None
        else (repo_root / DEFAULT_OUTPUT_MANIFEST)
    )

    _passages, manifest = build_corpus_v3(
        repo_root=repo_root,
        output_jsonl=output_jsonl,
        output_manifest=output_manifest,
    )
    print(
        json.dumps(
            {
                "output_jsonl": str(output_jsonl),
                "output_manifest": str(output_manifest),
                "jsonl_sha256": manifest["private_corpus_jsonl"]["sha256"],
                "summary": manifest["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
