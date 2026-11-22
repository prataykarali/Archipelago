"""Fail-closed S5-v3.1 dual-human gold assembler with investigator signoff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from annotation_v31.store import (
    load_blinded_pool,
    load_corpus_passages,
    validate_human_submission,
)

from .adjudicator import (
    compute_inter_annotator_agreement,
    validate_adjudication_worksheet,
)
from .constants import (
    BENCHMARK_VERSION,
    GOLD_SCHEMA_VERSION,
    GOLD_STATUS_FINAL,
    MIN_RATIONALE_CHARS,
    VALID_GOLD_STATUSES,
)
from .nc_verifier import validate_nc_verifications
from .pool_builder import compute_file_sha256


def _validate_investigator_signoff(
    signoff: dict[str, Any],
    benchmark_config: dict[str, Any],
    nc_verification_sha256: str,
) -> list[str]:
    errors: list[str] = []
    if signoff.get("human_signoff_confirmed") is not True:
        errors.append("INVESTIGATOR_SIGNOFF_NOT_CONFIRMED")
    for fname in ("investigator_id", "signed_timestamp_utc"):
        if not str(signoff.get(fname, "")).strip():
            errors.append(f"MISSING_INVESTIGATOR_{fname.upper()}")
    if (
        len(str(signoff.get("approval_declaration", "")).strip())
        < MIN_RATIONALE_CHARS
    ):
        errors.append("SHORT_INVESTIGATOR_DECLARATION")

    hash_pairs = (
        ("corpus_sha256", benchmark_config.get("corpus_sha256")),
        (
            "query_manifest_sha256",
            benchmark_config.get("query_manifest_sha256"),
        ),
        ("pool_sha256", benchmark_config.get("pool_sha256")),
        (
            "retrieval_manifest_sha256",
            benchmark_config.get("retrieval_manifest_sha256"),
        ),
        ("nc_verification_sha256", nc_verification_sha256),
    )
    for field_name, expected in hash_pairs:
        if str(signoff.get(field_name, "")) != str(expected):
            errors.append(f"SIGNOFF_HASH_MISMATCH:{field_name}")
    return errors


def _strip_nc_query_text(
    verifications: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    cleaned: dict[str, dict[str, Any]] = {}
    for qid, rec in sorted(verifications.items()):
        cleaned[qid] = {k: v for k, v in rec.items() if k != "query_text"}
    return cleaned


def assemble_v31_gold(
    *,
    benchmark_config_path: Path,
    pool_path: Path,
    corpus_jsonl_path: Path,
    sub_a_path: Path,
    sub_c_path: Path,
    adjudication_path: Path,
    nc_verification_path: Path,
    investigator_signoff_path: Path,
    output_gold_path: Path,
    status: str = GOLD_STATUS_FINAL,
) -> dict[str, Any]:
    """Assemble and validate s5v31_adjudicated_gold_v1; fail closed on errors."""
    if status not in VALID_GOLD_STATUSES:
        msg = f"Invalid gold status '{status}'."
        raise ValueError(msg)

    config = json.loads(benchmark_config_path.read_text(encoding="utf-8"))
    if config.get("benchmark_version") != BENCHMARK_VERSION:
        msg = f"Expected benchmark_version='{BENCHMARK_VERSION}'."
        raise ValueError(msg)

    corpus_sha = compute_file_sha256(corpus_jsonl_path)
    if str(config.get("corpus_sha256")) != corpus_sha:
        msg = "Corpus SHA-256 mismatch against benchmark_config."
        raise ValueError(msg)

    pool_sha = compute_file_sha256(pool_path)
    if str(config.get("pool_sha256")) != pool_sha:
        msg = "Pool SHA-256 mismatch against benchmark_config."
        raise ValueError(msg)

    pool = load_blinded_pool(pool_path)
    if int(config["expected_pair_count"]) != len(pool["pairs"]):
        msg = "Benchmark config expected_pair_count != pool pair count."
        raise ValueError(msg)
    corpus = load_corpus_passages(corpus_jsonl_path)

    sub_a = json.loads(sub_a_path.read_text(encoding="utf-8"))
    sub_c = json.loads(sub_c_path.read_text(encoding="utf-8"))
    err_a = validate_human_submission(sub_a, pool, corpus)
    err_c = validate_human_submission(sub_c, pool, corpus)
    if err_a or err_c:
        msg = f"Submission validation failed: A={err_a}, C={err_c}"
        raise ValueError(msg)

    rev_a_id = str(sub_a["reviewer_provenance"]["reviewer_id"])
    rev_c_id = str(sub_c["reviewer_provenance"]["reviewer_id"])
    if rev_a_id == rev_c_id:
        msg = "Dual independent reviewers must have distinct reviewer_id values."
        raise ValueError(msg)

    ja_map = sub_a["judgments"]
    jc_map = sub_c["judgments"]
    grades_a: list[int] = []
    grades_c: list[int] = []
    disagreement_ids: set[str] = set()
    for pair in pool["pairs"]:
        pid = str(pair["pair_id"])
        ga = int(ja_map[pid]["grade"])
        gc = int(jc_map[pid]["grade"])
        grades_a.append(ga)
        grades_c.append(gc)
        if ga != gc:
            disagreement_ids.add(pid)

    adj = json.loads(adjudication_path.read_text(encoding="utf-8"))
    adj_errors = validate_adjudication_worksheet(
        adj, frozenset(disagreement_ids)
    )
    if adj_errors:
        msg = f"Adjudication validation failed: {adj_errors}"
        raise ValueError(msg)

    nc_payload = json.loads(nc_verification_path.read_text(encoding="utf-8"))
    expected_nc_ids = frozenset(config.get("approved_negative_control_ids", []))
    nc_errors = validate_nc_verifications(
        nc_payload, expected_nc_ids, corpus_sha
    )
    if nc_errors:
        msg = f"Negative-control verification failed: {nc_errors}"
        raise ValueError(msg)

    nc_sha = compute_file_sha256(nc_verification_path)
    signoff = json.loads(investigator_signoff_path.read_text(encoding="utf-8"))
    signoff_errors = _validate_investigator_signoff(signoff, config, nc_sha)
    if signoff_errors:
        msg = f"Investigator signoff validation failed: {signoff_errors}"
        raise ValueError(msg)

    adj_by_pair = {
        str(row["pair_id"]): row for row in adj.get("disagreements", [])
    }
    adjudicator_id = str(adj["adjudicator_provenance"]["adjudicator_id"])
    judgments: list[dict[str, Any]] = []
    for pair in pool["pairs"]:
        pid = str(pair["pair_id"])
        ga = int(ja_map[pid]["grade"])
        gc = int(jc_map[pid]["grade"])
        if ga == gc:
            judgments.append(
                {
                    "pair_id": pid,
                    "query_id": str(pair["query_id"]),
                    "passage_id": str(pair["passage_id"]),
                    "passage_sha256": str(pair["passage_sha256"]),
                    "reviewer_a_grade": ga,
                    "reviewer_c_grade": gc,
                    "final_grade": ga,
                    "adjudication_source": "DUAL_HUMAN_AGREEMENT",
                    "supporting_quotation": str(
                        ja_map[pid].get("supporting_quotation", "")
                    ),
                    "adjudication_rationale": "Exact dual human agreement.",
                    "adjudicator_id": "",
                }
            )
        else:
            row = adj_by_pair[pid]
            judgments.append(
                {
                    "pair_id": pid,
                    "query_id": str(pair["query_id"]),
                    "passage_id": str(pair["passage_id"]),
                    "passage_sha256": str(pair["passage_sha256"]),
                    "reviewer_a_grade": ga,
                    "reviewer_c_grade": gc,
                    "final_grade": int(row["final_grade"]),
                    "adjudication_source": "ADJUDICATED_HUMAN",
                    "supporting_quotation": str(
                        row.get("supporting_quotation", "")
                    ),
                    "adjudication_rationale": str(
                        row["adjudication_rationale"]
                    ),
                    "adjudicator_id": adjudicator_id,
                }
            )

    iaa = compute_inter_annotator_agreement(grades_a, grades_c)
    prov_a = {
        **sub_a["reviewer_provenance"],
        "submission_sha256": compute_file_sha256(sub_a_path),
    }
    prov_c = {
        **sub_c["reviewer_provenance"],
        "submission_sha256": compute_file_sha256(sub_c_path),
    }

    gold: dict[str, Any] = {
        "schema_version": GOLD_SCHEMA_VERSION,
        "status": status,
        "benchmark_config": config,
        "reviewer_a_provenance": prov_a,
        "reviewer_c_provenance": prov_c,
        "inter_annotator_agreement": iaa,
        "adjudication_summary": {
            "all_disagreements_adjudicated": True,
            "total_disagreements": len(disagreement_ids),
            "adjudicated_count": len(adj_by_pair),
            "adjudication_worksheet_sha256": compute_file_sha256(
                adjudication_path
            ),
            "adjudicator_provenance": adj["adjudicator_provenance"],
        },
        "negative_control_verifications": _strip_nc_query_text(
            nc_payload["verifications"]
        ),
        "investigator_signoff": signoff,
        "judgments": judgments,
    }
    output_gold_path.parent.mkdir(parents=True, exist_ok=True)
    output_gold_path.write_text(
        json.dumps(gold, indent=2) + "\n", encoding="utf-8"
    )
    return gold
