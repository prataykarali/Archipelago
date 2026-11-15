#!/usr/bin/env python3
"""Build deterministic, document-disjoint dataset splits and audit historical leakage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from archipelago.eval.dataset_integrity import (  # noqa: E402
    audit_historical_9722_claim,
    build_document_disjoint_splits,
    detect_cross_split_contamination,
)


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build clean document-disjoint dataset splits.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=ROOT / "data" / "datasets" / "dual_ingest_multisource_v3",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "datasets" / "clean_splits_v1",
    )
    parser.add_argument(
        "--audit-out",
        type=Path,
        default=ROOT / "artifacts" / "validation" / "s2_historical_benchmark_audit.json",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # 1. Audit historical 97.22% benchmark (non-destructive)
    hist_audit = audit_historical_9722_claim(ROOT)

    # 2. Audit okf_v5 train/test doc overlap
    v5_train = _load_jsonl(ROOT / "training_data" / "okf_train_pairs_v5.jsonl")
    v5_test = _load_jsonl(ROOT / "training_data" / "okf_test_pairs_v5.jsonl")
    v5_audit = detect_cross_split_contamination({"train": v5_train, "test": v5_test})

    audit_payload = {
        "historical_9722_audit": hist_audit,
        "okf_v5_split_audit": v5_audit,
    }
    args.audit_out.parent.mkdir(parents=True, exist_ok=True)
    args.audit_out.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    print(f"Wrote historical audit to {args.audit_out}")

    # 3. Build clean document-disjoint splits from dual_ingest_multisource_v3
    all_rows: list[dict] = []
    for part in ("train.jsonl", "validation.jsonl", "test.jsonl"):
        p = args.source_dir / part
        if p.exists():
            all_rows.extend(_load_jsonl(p))

    splits, manifest = build_document_disjoint_splits(all_rows, seed=args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for sname, srows in splits.items():
        out_file = args.out_dir / f"{sname}.jsonl"
        out_file.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in srows) + "\n",
            encoding="utf-8",
        )
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        f"Clean splits written to {args.out_dir}: "
        f"docs={manifest['doc_counts']} rows={manifest['row_counts']} "
        f"disjoint={manifest['contamination_check']['is_document_disjoint']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
