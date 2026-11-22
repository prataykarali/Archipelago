"""Strictly blinded depth-k pool builder for S5-v3.1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .constants import (
    BENCHMARK_VERSION,
    BLIND_POOL_SALT,
    HASH_READ_CHUNK_BYTES,
    VALID_POOL_DEPTHS,
    VALID_SPLITS,
)


def compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_READ_CHUNK_BYTES), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _blind_pair_key(query_id: str, passage_id: str) -> str:
    raw = f"{BLIND_POOL_SALT}::{query_id}::{passage_id}".encode()
    return hashlib.sha256(raw).hexdigest()


def _load_corpus_index(corpus_jsonl: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    with corpus_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rec = json.loads(stripped)
            index[str(rec["passage_id"])] = rec
    return index


def build_blinded_pool(
    approved_queries_path: Path,
    retrieval_diagnostics_path: Path,
    retrieval_manifest_path: Path,
    corpus_jsonl_path: Path,
    pool_depth_k: int,
    split: str,
    pool_id: str,
    output_pool_path: Path,
    output_config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build strictly blinded depth-k pool and s5v31_benchmark_config JSON."""
    if pool_depth_k not in VALID_POOL_DEPTHS:
        msg = f"pool_depth_k must be in {sorted(VALID_POOL_DEPTHS)}."
        raise ValueError(msg)
    if split not in VALID_SPLITS:
        msg = f"split must be in {sorted(VALID_SPLITS)}."
        raise ValueError(msg)

    q_manifest = json.loads(approved_queries_path.read_text(encoding="utf-8"))
    diag = json.loads(retrieval_diagnostics_path.read_text(encoding="utf-8"))
    ret_manifest = json.loads(
        retrieval_manifest_path.read_text(encoding="utf-8")
    )
    corpus = _load_corpus_index(corpus_jsonl_path)

    selected_queries = [
        q
        for q in q_manifest.get("queries", [])
        if split == "dev_and_test" or str(q.get("split")) == split
    ]
    if not selected_queries:
        msg = f"No queries matched split='{split}'."
        raise ValueError(msg)

    q_by_id = {str(q["query_id"]): q for q in selected_queries}
    approved_qids = [str(q["query_id"]) for q in selected_queries]
    approved_nc_ids = [
        str(q["query_id"])
        for q in selected_queries
        if str(q.get("category")) == "negative_control"
    ]

    variants = diag.get("variants", {})
    if not isinstance(variants, dict) or not variants:
        msg = "Retrieval diagnostics missing 'variants' dictionary."
        raise ValueError(msg)

    unique_pairs: set[tuple[str, str]] = set()
    for sys_payload in variants.values():
        for q_diag in sys_payload.get("per_query_diagnostics", []):
            qid = str(q_diag.get("query_id", ""))
            if qid not in q_by_id:
                continue
            for result in q_diag.get("results", [])[:pool_depth_k]:
                pid = str(result["passage_id"])
                if pid not in corpus:
                    msg = f"Retrieved passage '{pid}' missing from Corpus v3.1."
                    raise KeyError(msg)
                unique_pairs.add((qid, pid))

    ordered = sorted(unique_pairs, key=lambda pair: _blind_pair_key(*pair))
    blinded_pairs: list[dict[str, Any]] = []
    for idx, (qid, pid) in enumerate(ordered, start=1):
        q = q_by_id[qid]
        rec = corpus[pid]
        blinded_pairs.append(
            {
                "pair_id": f"PAIR-{idx:04d}",
                "query_id": qid,
                "query_text": str(q["query_text"]),
                "domain": str(q.get("domain", "")),
                "passage_id": pid,
                "source_doc_id": str(rec["source_doc_id"]),
                "page_start": rec.get("page_start"),
                "page_end": rec.get("page_end"),
                "section_ref": str(
                    rec.get("section_ref") or rec.get("section_heading") or ""
                ),
                "passage_sha256": str(rec["passage_sha256"]),
            }
        )

    pool_payload: dict[str, Any] = {
        "benchmark_version": BENCHMARK_VERSION,
        "pool_id": pool_id,
        "split": split,
        "pool_depth_k": pool_depth_k,
        "expected_pair_count": len(blinded_pairs),
        "blinding_policy": (
            "Strictly blinded: zero system IDs, ranks, scores, or AI hints."
        ),
        "pairs": blinded_pairs,
    }
    output_pool_path.parent.mkdir(parents=True, exist_ok=True)
    output_pool_path.write_text(
        json.dumps(pool_payload, indent=2) + "\n", encoding="utf-8"
    )
    pool_sha = compute_file_sha256(output_pool_path)

    system_hashes: dict[str, str] = {}
    for sys_name, sys_meta in ret_manifest.get("variants", {}).items():
        if isinstance(sys_meta, dict) and sys_meta.get("config_sha256"):
            system_hashes[str(sys_name)] = str(sys_meta["config_sha256"])
    if not system_hashes:
        for sys_name in sorted(variants.keys()):
            raw = json.dumps(variants[sys_name], sort_keys=True).encode()
            system_hashes[str(sys_name)] = hashlib.sha256(raw).hexdigest()

    benchmark_config: dict[str, Any] = {
        "benchmark_version": BENCHMARK_VERSION,
        "corpus_id": str(
            ret_manifest.get("corpus_id", "s5v31_corpus_v1")
        ),
        "corpus_sha256": compute_file_sha256(corpus_jsonl_path),
        "query_manifest_id": str(
            q_manifest.get("schema_version", "s5v31_approved_queries")
        ),
        "query_manifest_sha256": compute_file_sha256(approved_queries_path),
        "split": split,
        "approved_query_ids": approved_qids,
        "approved_negative_control_ids": approved_nc_ids,
        "pool_id": pool_id,
        "pool_sha256": pool_sha,
        "pool_depth_k": pool_depth_k,
        "expected_pair_count": len(blinded_pairs),
        "retrieval_manifest_sha256": compute_file_sha256(
            retrieval_manifest_path
        ),
        "system_hashes": system_hashes,
    }
    output_config_path.parent.mkdir(parents=True, exist_ok=True)
    output_config_path.write_text(
        json.dumps(benchmark_config, indent=2) + "\n", encoding="utf-8"
    )
    return pool_payload, benchmark_config
