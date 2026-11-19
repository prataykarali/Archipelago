#!/usr/bin/env python3
"""CLI for S5-v3.1 Stage C: pinned Snowflake model verification & retrieval diagnostics.

Rebuilds BM25, hash-pinned Snowflake dense embeddings, Hybrid RRF, and improved v3
graph variants over the exact identical eligible Corpus v3.1 scope, computing
relevance-agnostic technical diagnostics and depth-5/depth-10 pool sizes.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
V3_SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-benchmark-expansion" / "scripts"

for path_entry in (str(SCRIPT_DIR), str(V3_SCRIPTS_DIR)):
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)

from retrieval_v31 import (  # noqa: E402
    compute_file_sha256,
    load_eligible_v31_passages,
    load_v31_queries,
    make_snowflake_cpu_encoder,
    run_v31_verification_suite,
    verify_essential_model,
)

DEFAULT_MODEL_PIN = (
    REPO_ROOT
    / "research"
    / "s5-v3-benchmark-expansion"
    / "hold_resolution"
    / "s5v3_essential_model_pin.json"
)
DEFAULT_CORPUS_PATH = (
    REPO_ROOT
    / "data"
    / "annotation_local"
    / "s5v3_1"
    / "corpus_v31"
    / "s5v31_corpus_passages.jsonl"
)
DEFAULT_GRAPH_PATH = REPO_ROOT / "okf_graph.json"
DEFAULT_QUERIES_PATH = (
    REPO_ROOT
    / "research"
    / "s5-v3-1-oa-corpus-expansion"
    / "manifests"
    / "s5v31_query_benchmark_proposed.json"
)
DEFAULT_CACHE_PATH = (
    REPO_ROOT
    / "data"
    / "annotation_local"
    / "s5v3_1"
    / "embeddings"
    / "s5v31_snowflake_embeddings.npy"
)
DEFAULT_MANIFEST_OUT = (
    REPO_ROOT
    / "research"
    / "s5-v3-1-oa-corpus-expansion"
    / "manifests"
    / "s5v31_retrieval_manifest.json"
)
DEFAULT_DIAGNOSTICS_OUT = (
    REPO_ROOT
    / "research"
    / "s5-v3-1-oa-corpus-expansion"
    / "reports"
    / "s5v31_retrieval_diagnostics.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Verify pinned Snowflake model and run S5-v3.1 retrieval technical diagnostics."
    )
    parser.add_argument("--model-pin", type=Path, default=DEFAULT_MODEL_PIN)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--cache-npy", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUT)
    parser.add_argument("--diagnostics-out", type=Path, default=DEFAULT_DIAGNOSTICS_OUT)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--verify-model-only", action="store_true")
    parser.add_argument("--force-rebuild-cache", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    model_report = verify_essential_model(args.model_pin, REPO_ROOT, run_smoke_test=True)
    if args.verify_model_only:
        print(json.dumps(model_report.to_dict(), indent=2, sort_keys=True))
        return 0

    passages, corpus_stats = load_eligible_v31_passages(args.corpus)
    queries = load_v31_queries(args.queries)
    model_dir = REPO_ROOT / model_report.local_path_relative
    encoder = make_snowflake_cpu_encoder(model_dir)

    manifest, diagnostics = run_v31_verification_suite(
        passages,
        args.graph,
        queries,
        model_report,
        args.cache_npy,
        encode_fn=encoder,
        top_k=args.top_k,
        force_rebuild_cache=args.force_rebuild_cache,
    )

    now_utc = datetime.now(UTC).isoformat()
    input_meta = {
        "corpus_path_relative": str(args.corpus.relative_to(REPO_ROOT))
        if args.corpus.is_relative_to(REPO_ROOT)
        else str(args.corpus),
        "corpus_sha256": compute_file_sha256(args.corpus),
        "corpus_eligibility_stats": corpus_stats,
        "graph_path_relative": str(args.graph.relative_to(REPO_ROOT))
        if args.graph.is_relative_to(REPO_ROOT)
        else str(args.graph),
        "graph_sha256": compute_file_sha256(args.graph),
        "queries_path_relative": str(args.queries.relative_to(REPO_ROOT))
        if args.queries.is_relative_to(REPO_ROOT)
        else str(args.queries),
        "queries_sha256": compute_file_sha256(args.queries),
        "query_count": len(queries),
    }
    manifest["generated_at_utc"] = now_utc
    manifest["inputs"] = input_meta
    diagnostics["generated_at_utc"] = now_utc
    diagnostics["inputs"] = input_meta

    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.diagnostics_out.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics_out.write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "manifest_out": str(args.manifest_out),
                "diagnostics_out": str(args.diagnostics_out),
                "eligible_passages": len(passages),
                "query_count": len(queries),
                "all_systems_deterministic": manifest["determinism_verification"][
                    "all_systems_deterministic"
                ],
                "depth_5_total_pairs": diagnostics["pooling_diagnostics"]["depth_5"]["all_systems"][
                    "total_unique_query_passage_pairs"
                ],
                "depth_10_total_pairs": diagnostics["pooling_diagnostics"]["depth_10"][
                    "all_systems"
                ]["total_unique_query_passage_pairs"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
