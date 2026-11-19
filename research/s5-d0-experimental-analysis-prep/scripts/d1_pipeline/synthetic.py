"""Deterministic synthetic test fixtures for S5-D1 dry-runs and unit tests.

All data generated here is 100% synthetic and explicitly marked SYNTHETIC.
It NEVER reads or modifies real reviewer workbooks or frozen benchmark outputs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from d1_pipeline.constants import (
    AUTH_APPROVED_STATUS,
    AUTH_SCHEMA_VERSION,
    LEGACY_V1_SCHEMA_VERSION,
    SYSTEM_BASELINE_1HOP,
    SYSTEM_REPAIRED_1HOP,
    SYSTEM_REPAIRED_2HOP,
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_synthetic_bundle(
    target_dir: Path,
    *,
    schema_mode: str = "ac_v2",
    neg_control_overrides: dict[str, str] | None = None,
) -> dict[str, Path]:
    """Write a complete, deterministic synthetic S5-D1 bundle into target_dir.

    Queries:
    - Q-S5B2-01 (answerable): 4 pooled passages [p1(g=2), p2(g=1), p3(g=2), p4(g=0)]
    - Q-S5B2-02 (answerable): 3 pooled passages [p5(g=2), p6(g=0), p7(g=1)]
    - Q-S5B2-03 (provisional neg control): 2 pooled passages [p8(g=0), p9(g=0)]
    - Q-S5B2-08 (provisional neg control): 2 pooled passages [p10(g=0), p11(g=1)]
    - Q-S5B2-11 (provisional neg control): 2 pooled passages [p12(g=0), p13(g=0)]
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    passages: dict[str, str] = {
        "syn_doc/p1": "SYNTHETIC passage p1: An address space isolates running programs in memory.",
        "syn_doc/p2": "SYNTHETIC passage p2: Virtual memory mentions address spaces briefly.",
        "syn_doc/p3": "SYNTHETIC passage p3: The OS provides an address space for isolation and protection.",
        "syn_doc/p4": "SYNTHETIC passage p4: Unrelated networking timer background text.",
        "syn_doc/p5": "SYNTHETIC passage p5: TCP congestion control uses AIMD window scaling.",
        "syn_doc/p6": "SYNTHETIC passage p6: Unrelated disk scheduling text.",
        "syn_doc/p7": "SYNTHETIC passage p7: Packet loss triggers window reduction in transport layers.",
        "syn_doc/p8": "SYNTHETIC passage p8: ARM architecture overview without latency figures.",
        "syn_doc/p9": "SYNTHETIC passage p9: Generic page table description without nanoseconds.",
        "syn_doc/p10": "SYNTHETIC passage p10: GPU cluster description without electricity costs.",
        "syn_doc/p11": "SYNTHETIC passage p11: Partial mention of Llama training hardware count.",
        "syn_doc/p12": "SYNTHETIC passage p12: General switch firmware security concepts.",
        "syn_doc/p13": "SYNTHETIC passage p13: Buffer overflow definition in systems security.",
    }

    query_specs = [
        ("Q-S5B2-01", [("SYN-P01", "syn_doc/p1", 2, 2, 2, "An address space isolates running programs"),
                       ("SYN-P02", "syn_doc/p2", 1, 1, 1, "Virtual memory mentions address spaces"),
                       ("SYN-P03", "syn_doc/p3", 2, 1, 2, "OS provides an address space for isolation"),
                       ("SYN-P04", "syn_doc/p4", 0, 0, 0, "")]),
        ("Q-S5B2-02", [("SYN-P05", "syn_doc/p5", 2, 2, 2, "TCP congestion control uses AIMD"),
                       ("SYN-P06", "syn_doc/p6", 0, 0, 0, ""),
                       ("SYN-P07", "syn_doc/p7", 1, 1, 1, "Packet loss triggers window reduction")]),
        ("Q-S5B2-03", [("SYN-P08", "syn_doc/p8", 0, 0, 0, ""),
                       ("SYN-P09", "syn_doc/p9", 0, 0, 0, "")]),
        ("Q-S5B2-08", [("SYN-P10", "syn_doc/p10", 0, 0, 0, ""),
                       ("SYN-P11", "syn_doc/p11", 1, 1, 1, "Partial mention of Llama training hardware")]),
        ("Q-S5B2-11", [("SYN-P12", "syn_doc/p12", 0, 0, 0, ""),
                       ("SYN-P13", "syn_doc/p13", 0, 0, 0, "")]),
    ]

    pool_payload: dict[str, Any] = {
        "version": "SYNTHETIC_s5d1_pool_v1",
        "is_synthetic": True,
        "queries": [],
    }
    for qid, rows in query_specs:
        cands = []
        for idx, (pair_id, pid, *_rest) in enumerate(rows, start=1):
            cands.append({
                "pair_id": pair_id,
                "presentation_order": idx,
                "candidate_passage_id": pid,
                "passage_sha256": _sha256_text(passages[pid]),
            })
        pool_payload["queries"].append({"query_id": qid, "candidates": cands})

    pool_path = target_dir / "SYNTHETIC_pool.json"
    pool_bytes = (json.dumps(pool_payload, indent=2) + "\n").encode("utf-8")
    pool_path.write_bytes(pool_bytes)
    pool_sha = _sha256_bytes(pool_bytes)

    passages_path = target_dir / "SYNTHETIC_passages.json"
    passages_path.write_text(json.dumps(passages, indent=2) + "\n", encoding="utf-8")

    def _ranked(pids: list[str]) -> list[dict[str, Any]]:
        return [{"rank": i, "passage_id": p, "score": round(10.0 - i, 2)} for i, p in enumerate(pids, start=1)]

    rankings_payload: dict[str, Any] = {
        "report_name": "SYNTHETIC Frozen Ranked Results",
        "is_synthetic": True,
        "systems": {
            "bm25": {
                "queries": [
                    {"query_id": "Q-S5B2-01", "ranked_top10": _ranked(["syn_doc/p1", "syn_doc/p4", "syn_doc/p2", "syn_doc/p3"]), "meta": {"is_fallback": False, "actual_hop_count": "N/A"}},
                    {"query_id": "Q-S5B2-02", "ranked_top10": _ranked(["syn_doc/p6", "syn_doc/p5", "syn_doc/p7"]), "meta": {"is_fallback": False, "actual_hop_count": "N/A"}},
                    {"query_id": "Q-S5B2-03", "ranked_top10": _ranked(["syn_doc/p8", "syn_doc/p9"]), "meta": {"is_fallback": False, "actual_hop_count": "N/A"}},
                    {"query_id": "Q-S5B2-08", "ranked_top10": _ranked(["syn_doc/p10", "syn_doc/p11"]), "meta": {"is_fallback": False, "actual_hop_count": "N/A"}},
                    {"query_id": "Q-S5B2-11", "ranked_top10": _ranked(["syn_doc/p12", "syn_doc/p13"]), "meta": {"is_fallback": False, "actual_hop_count": "N/A"}},
                ]
            },
            SYSTEM_BASELINE_1HOP: {
                "queries": [
                    {"query_id": "Q-S5B2-01", "ranked_top10": _ranked(["syn_doc/p4", "syn_doc/p1"]), "meta": {"is_fallback": True, "actual_hop_count": 0}},
                    {"query_id": "Q-S5B2-02", "ranked_top10": _ranked(["syn_doc/p6"]), "meta": {"is_fallback": False, "actual_hop_count": 1}},
                    {"query_id": "Q-S5B2-03", "ranked_top10": _ranked(["syn_doc/p8"]), "meta": {"is_fallback": False, "actual_hop_count": 1}},
                    {"query_id": "Q-S5B2-08", "ranked_top10": _ranked(["syn_doc/p10"]), "meta": {"is_fallback": False, "actual_hop_count": 1}},
                    {"query_id": "Q-S5B2-11", "ranked_top10": _ranked(["syn_doc/p12"]), "meta": {"is_fallback": False, "actual_hop_count": 1}},
                ]
            },
            SYSTEM_REPAIRED_1HOP: {
                "queries": [
                    {"query_id": "Q-S5B2-01", "ranked_top10": _ranked(["syn_doc/p2", "syn_doc/p1", "syn_doc/p3", "syn_doc/p4"]), "meta": {"is_fallback": True, "actual_hop_count": 0}},
                    {"query_id": "Q-S5B2-02", "ranked_top10": _ranked(["syn_doc/p7", "syn_doc/p5", "syn_doc/p6"]), "meta": {"is_fallback": False, "actual_hop_count": 1}},
                    {"query_id": "Q-S5B2-03", "ranked_top10": _ranked(["syn_doc/p8", "syn_doc/p9"]), "meta": {"is_fallback": True, "actual_hop_count": 0}},
                    {"query_id": "Q-S5B2-08", "ranked_top10": _ranked(["syn_doc/p10", "syn_doc/p11"]), "meta": {"is_fallback": False, "actual_hop_count": 1}},
                    {"query_id": "Q-S5B2-11", "ranked_top10": _ranked(["syn_doc/p12", "syn_doc/p13"]), "meta": {"is_fallback": True, "actual_hop_count": 0}},
                ]
            },
            SYSTEM_REPAIRED_2HOP: {
                "queries": [
                    {"query_id": "Q-S5B2-01", "ranked_top10": _ranked(["syn_doc/p1", "syn_doc/p3", "syn_doc/p2", "syn_doc/p4"]), "meta": {"is_fallback": True, "actual_hop_count": 0}},
                    {"query_id": "Q-S5B2-02", "ranked_top10": _ranked(["syn_doc/p5", "syn_doc/p7", "syn_doc/p6"]), "meta": {"is_fallback": False, "actual_hop_count": 2}},
                    {"query_id": "Q-S5B2-03", "ranked_top10": _ranked(["syn_doc/p8", "syn_doc/p9"]), "meta": {"is_fallback": True, "actual_hop_count": 0}},
                    {"query_id": "Q-S5B2-08", "ranked_top10": _ranked(["syn_doc/p11", "syn_doc/p10"]), "meta": {"is_fallback": False, "actual_hop_count": 2}},
                    {"query_id": "Q-S5B2-11", "ranked_top10": _ranked(["syn_doc/p12", "syn_doc/p13"]), "meta": {"is_fallback": True, "actual_hop_count": 0}},
                ]
            },
        },
    }
    rankings_path = target_dir / "SYNTHETIC_rankings.json"
    rankings_bytes = (json.dumps(rankings_payload, indent=2) + "\n").encode("utf-8")
    rankings_path.write_bytes(rankings_bytes)
    rankings_sha = _sha256_bytes(rankings_bytes)

    neg_classes = {
        "Q-S5B2-03": "NO_ANSWER_IN_FROZEN_CORPUS",
        "Q-S5B2-08": "NO_ANSWER_IN_FROZEN_CORPUS",
        "Q-S5B2-11": "NO_ANSWER_IN_FROZEN_CORPUS",
    }
    if neg_control_overrides:
        neg_classes.update(neg_control_overrides)

    neg_verifications = {
        qid: {
            "human_answerability_classification": cls,
            "verifier_id": "SYNTHETIC_HUMAN_VERIFIER",
            "provenance_class": "INDEPENDENT_HUMAN",
            "human_attestation_signed": True,
            "signed_timestamp_utc": "2026-11-19T00:00:00Z",
        }
        for qid, cls in neg_classes.items()
    }

    judgments: list[dict[str, Any]] = []
    for qid, rows in query_specs:
        for pair_id, pid, g_a, g_c, g_final, quote in rows:
            is_agree = g_a == g_c
            src = (
                ("DUAL_HUMAN_AC_AGREEMENT" if is_agree else "ADJUDICATED_HUMAN_AC")
                if schema_mode == "ac_v2"
                else ("DUAL_HUMAN_AGREEMENT" if is_agree else "THIRD_PARTY_ADJUDICATION")
            )
            judgments.append({
                "pair_id": pair_id,
                "query_id": qid,
                "passage_id": pid,
                "passage_sha256": _sha256_text(passages[pid]),
                "reviewer_a_grade": g_a,
                "reviewer_c_grade": g_c,
                "final_grade": g_final,
                "adjudication_source": src,
                "supporting_quotation": quote,
                "adjudication_rationale": "" if is_agree else "SYNTHETIC human adjudication rationale confirming direct answer.",
                "adjudicator_id": "" if is_agree else "SYNTHETIC_HUMAN_ADJUDICATOR",
            })

    if schema_mode == "v1":
        gold_payload: dict[str, Any] = {
            "schema_version": LEGACY_V1_SCHEMA_VERSION,
            "status": "ADJUDICATED_HUMAN_GOLD_FINAL",
            "pool_version": pool_payload["version"],
            "pool_sha256": pool_sha,
            "reviewer_b_independence_confirmed": True,
            "all_disagreements_adjudicated": True,
            "negative_control_verifications": neg_verifications,
            "judgments": judgments,
        }
    else:
        gold_payload = {
            "schema_version": "s5d1_adjudicated_gold_ac_v2",
            "status": "ADJUDICATED_HUMAN_GOLD_AC_V2_FINAL",
            "pool_version": pool_payload["version"],
            "pool_sha256": pool_sha,
            "primary_human_assessor_pair": ["REV_A", "REV_C"],
            "historical_reviewer_b_excluded_from_gold": True,
            "legacy_reviewer_b_provenance": {
                "provenance_class": "AI_ASSISTED_OR_GENERATED",
                "excluded_from_gold": True,
                "legacy_v1_contract_preserved": True,
            },
            "reviewer_a_provenance": {
                "reviewer_id": "SYNTHETIC_REV_A",
                "provenance_class": "INDEPENDENT_HUMAN",
                "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
                "prior_exposure_disclosure": "NONE",
                "human_attestation_signed": True,
                "attestation_signer": "SYNTHETIC_REV_A",
                "signed_timestamp_utc": "2026-11-19T00:00:00Z",
                "submission_sha256": "0" * 64,
            },
            "reviewer_c_provenance": {
                "reviewer_id": "SYNTHETIC_REV_C",
                "provenance_class": "INDEPENDENT_HUMAN",
                "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
                "prior_exposure_disclosure": "NONE",
                "human_attestation_signed": True,
                "attestation_signer": "SYNTHETIC_REV_C",
                "signed_timestamp_utc": "2026-11-19T00:00:00Z",
                "submission_sha256": "1" * 64,
            },
            "adjudication_summary": {
                "all_ac_disagreements_adjudicated": True,
                "total_disagreements": 1,
                "adjudicated_count": 1,
                "adjudication_worksheet_sha256": "2" * 64,
                "adjudicator_provenance": {
                    "provenance_class": "ADJUDICATED_HUMAN",
                    "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
                    "human_attestation_signed": True,
                    "attestation_signer": "SYNTHETIC_HUMAN_ADJUDICATOR",
                    "signed_timestamp_utc": "2026-11-19T00:00:00Z",
                },
            },
            "investigator_signoff": {
                "investigator_id": "SYNTHETIC_PI_HUMAN",
                "approval_declaration": "SYNTHETIC test signoff for unit testing only.",
                "human_signoff_confirmed": True,
                "signed_timestamp_utc": "2026-11-19T00:00:00Z",
            },
            "negative_control_verifications": neg_verifications,
            "judgments": judgments,
        }

    gold_path = target_dir / f"SYNTHETIC_gold_{schema_mode}.json"
    gold_bytes = (json.dumps(gold_payload, indent=2) + "\n").encode("utf-8")
    gold_path.write_bytes(gold_bytes)
    gold_sha = _sha256_bytes(gold_bytes)

    auth_payload = {
        "schema_version": AUTH_SCHEMA_VERSION,
        "authorization_status": AUTH_APPROVED_STATUS,
        "investigator_id": "SYNTHETIC_PI_HUMAN",
        "explicit_approval_declaration": "SYNTHETIC unit-test approval of validated gold and negative-control hashes.",
        "approved_at_utc": "2026-11-19T12:00:00Z",
        "gold_labels_sha256": gold_sha,
        "negative_control_sha256": gold_sha,
        "pool_sha256": pool_sha,
        "rankings_sha256": rankings_sha,
    }
    auth_path = target_dir / "SYNTHETIC_auth_artifact.json"
    auth_path.write_text(json.dumps(auth_payload, indent=2) + "\n", encoding="utf-8")

    return {
        "pool": pool_path,
        "rankings": rankings_path,
        "passages": passages_path,
        "gold": gold_path,
        "auth": auth_path,
    }
