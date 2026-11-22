"""CLI for S5-v3.1 pool building, adjudication, NC verification, and gold."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adjudication_v31.adjudicator import generate_disagreement_worksheet
from adjudication_v31.constants import GOLD_STATUS_FINAL
from adjudication_v31.gold_assembler import assemble_v31_gold
from adjudication_v31.nc_verifier import (
    generate_nc_verification_worksheet,
    validate_nc_verifications,
)
from adjudication_v31.pool_builder import (
    build_blinded_pool,
    compute_file_sha256,
)
from annotation_v31.store import load_blinded_pool


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="S5-v3.1 pool, adjudication, NC, and gold assembly CLI."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pool = sub.add_parser("build-pool")
    p_pool.add_argument("--approved-queries", type=Path, required=True)
    p_pool.add_argument("--retrieval-diagnostics", type=Path, required=True)
    p_pool.add_argument("--retrieval-manifest", type=Path, required=True)
    p_pool.add_argument("--corpus", type=Path, required=True)
    p_pool.add_argument("--depth-k", type=int, required=True)
    p_pool.add_argument("--split", type=str, required=True)
    p_pool.add_argument("--pool-id", type=str, required=True)
    p_pool.add_argument("--output-pool", type=Path, required=True)
    p_pool.add_argument("--output-config", type=Path, required=True)

    p_dis = sub.add_parser("disagreements")
    p_dis.add_argument("--pool", type=Path, required=True)
    p_dis.add_argument("--sub-a", type=Path, required=True)
    p_dis.add_argument("--sub-c", type=Path, required=True)
    p_dis.add_argument("--output", type=Path, required=True)

    p_nc_init = sub.add_parser("init-nc")
    p_nc_init.add_argument("--approved-queries", type=Path, required=True)
    p_nc_init.add_argument("--corpus", type=Path, required=True)
    p_nc_init.add_argument("--split", type=str, default="test")
    p_nc_init.add_argument("--output", type=Path, required=True)

    p_nc_val = sub.add_parser("validate-nc")
    p_nc_val.add_argument("--nc-file", type=Path, required=True)
    p_nc_val.add_argument("--config", type=Path, required=True)
    p_nc_val.add_argument("--corpus", type=Path, required=True)

    p_gold = sub.add_parser("assemble-gold")
    p_gold.add_argument("--config", type=Path, required=True)
    p_gold.add_argument("--pool", type=Path, required=True)
    p_gold.add_argument("--corpus", type=Path, required=True)
    p_gold.add_argument("--sub-a", type=Path, required=True)
    p_gold.add_argument("--sub-c", type=Path, required=True)
    p_gold.add_argument("--adjudication", type=Path, required=True)
    p_gold.add_argument("--nc-file", type=Path, required=True)
    p_gold.add_argument("--signoff", type=Path, required=True)
    p_gold.add_argument("--output", type=Path, required=True)
    p_gold.add_argument("--status", type=str, default=GOLD_STATUS_FINAL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Execute S5-v3.1 pool/adjudication/NC/gold CLI command."""
    args = _parse_args(argv)

    if args.command == "build-pool":
        pool, cfg = build_blinded_pool(
            approved_queries_path=args.approved_queries,
            retrieval_diagnostics_path=args.retrieval_diagnostics,
            retrieval_manifest_path=args.retrieval_manifest,
            corpus_jsonl_path=args.corpus,
            pool_depth_k=args.depth_k,
            split=args.split,
            pool_id=args.pool_id,
            output_pool_path=args.output_pool,
            output_config_path=args.output_config,
        )
        print(
            json.dumps(
                {
                    "pool_id": pool["pool_id"],
                    "expected_pair_count": pool["expected_pair_count"],
                    "pool_sha256": cfg["pool_sha256"],
                    "approved_nc_count": len(
                        cfg["approved_negative_control_ids"]
                    ),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "disagreements":
        pool = load_blinded_pool(args.pool)
        sub_a = json.loads(args.sub_a.read_text(encoding="utf-8"))
        sub_c = json.loads(args.sub_c.read_text(encoding="utf-8"))
        ws = generate_disagreement_worksheet(sub_a, sub_c, pool)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(ws, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {"total_disagreements": ws["total_disagreements"]}, indent=2
            )
        )
        return 0

    if args.command == "init-nc":
        q_manifest = json.loads(
            args.approved_queries.read_text(encoding="utf-8")
        )
        ncs = [
            q
            for q in q_manifest.get("queries", [])
            if str(q.get("category")) == "negative_control"
            and (args.split == "dev_and_test" or str(q.get("split")) == args.split)
        ]
        corpus_sha = compute_file_sha256(args.corpus)
        ws = generate_nc_verification_worksheet(ncs, corpus_sha)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(ws, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"expected_nc_ids": ws["expected_nc_ids"]}, indent=2))
        return 0

    if args.command == "validate-nc":
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
        nc_payload = json.loads(args.nc_file.read_text(encoding="utf-8"))
        corpus_sha = compute_file_sha256(args.corpus)
        errors = validate_nc_verifications(
            nc_payload,
            frozenset(cfg.get("approved_negative_control_ids", [])),
            corpus_sha,
        )
        print(
            json.dumps(
                {"valid": len(errors) == 0, "errors": errors}, indent=2
            )
        )
        return 0 if not errors else 1

    gold = assemble_v31_gold(
        benchmark_config_path=args.config,
        pool_path=args.pool,
        corpus_jsonl_path=args.corpus,
        sub_a_path=args.sub_a,
        sub_c_path=args.sub_c,
        adjudication_path=args.adjudication,
        nc_verification_path=args.nc_file,
        investigator_signoff_path=args.signoff,
        output_gold_path=args.output,
        status=args.status,
    )
    print(
        json.dumps(
            {
                "schema_version": gold["schema_version"],
                "status": gold["status"],
                "judgments": len(gold["judgments"]),
                "iaa": gold["inter_annotator_agreement"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
