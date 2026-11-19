#!/usr/bin/env python3
"""CLI entry point for building immutable S5-v3.1 Corpus v3.1 and manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from corpus_v31.builder import build_corpus_v31  # noqa: E402
from corpus_v31.constants import (  # noqa: E402
    DEFAULT_V31_CORPUS_MANIFEST,
    DEFAULT_V31_LICENSE_MANIFEST,
    DEFAULT_V31_OUTPUT_JSONL,
)

REPO_ROOT_DEPTH = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for Corpus v3.1 builder."""
    default_root = Path(__file__).resolve().parents[REPO_ROOT_DEPTH]
    parser = argparse.ArgumentParser(
        description=(
            "Build immutable S5-v3.1 Corpus v3.1 combining 818 eligible v3 "
            "passages + 4 verified CC-licensed CS sources."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--output-jsonl", type=Path, default=None)
    parser.add_argument("--output-corpus-manifest", type=Path, default=None)
    parser.add_argument("--output-license-manifest", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Execute Corpus v3.1 build and print deterministic JSON summary."""
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    out_jsonl = (
        args.output_jsonl.resolve()
        if args.output_jsonl is not None
        else (repo_root / DEFAULT_V31_OUTPUT_JSONL)
    )
    out_corpus_manifest = (
        args.output_corpus_manifest.resolve()
        if args.output_corpus_manifest is not None
        else (repo_root / DEFAULT_V31_CORPUS_MANIFEST)
    )
    out_license_manifest = (
        args.output_license_manifest.resolve()
        if args.output_license_manifest is not None
        else (repo_root / DEFAULT_V31_LICENSE_MANIFEST)
    )

    _passages, corpus_manifest, _license_manifest = build_corpus_v31(
        repo_root=repo_root,
        output_jsonl=out_jsonl,
        output_corpus_manifest=out_corpus_manifest,
        output_license_manifest=out_license_manifest,
    )
    print(
        json.dumps(
            {
                "output_jsonl": str(out_jsonl),
                "jsonl_sha256": corpus_manifest["private_corpus_jsonl"]["sha256"],
                "summary": corpus_manifest["summary"],
                "deduplication": {
                    "exact_duplicates_dropped": corpus_manifest["deduplication"][
                        "exact_duplicates_dropped"
                    ],
                    "near_duplicates_detected": corpus_manifest["deduplication"][
                        "near_duplicates_detected"
                    ],
                    "near_duplicates_dropped_from_new_oa": corpus_manifest["deduplication"][
                        "near_duplicates_dropped_from_new_oa"
                    ],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
