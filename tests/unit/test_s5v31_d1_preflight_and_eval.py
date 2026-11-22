"""Unit tests for Task 1 (preflight silent-bypass fix) & Task 4 (versioned S5-v3.1 D1 evaluator)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
D0_SCRIPTS_DIR = REPO_ROOT / "research" / "s5-d0-experimental-analysis-prep" / "scripts"
V31_SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-1-oa-corpus-expansion" / "scripts"
for entry in (str(V31_SCRIPTS_DIR), str(D0_SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from d1_pipeline.preflight_checks import validate_negative_controls  # noqa: E402
from d1_pipeline.preflight_models import PreflightResult  # noqa: E402
from eval_v31 import (  # noqa: E402
    AUTH_APPROVED_STATUS_V31,
    BENCHMARK_VERSION_V31,
    GOLD_SCHEMA_VERSION_V31,
    GOLD_STATUS_FINAL,
    GOLD_STATUS_SYNTHETIC,
    SYNTHETIC_BANNER,
    V31AuthorizationError,
    V31PreflightError,
    build_v31_authorization_template,
    compute_v31_d1_evaluation,
    evaluate_v31_query_ranking,
    sha256_file,
    validate_v31_authorization_gate,
    validate_v31_preflight,
    write_results_tables,
)
from s5v31_d1_evaluate import main as cli_main  # noqa: E402

HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64
HEX_E = "e" * 64
HEX_F = "f" * 64


def _build_synthetic_v31_fixture(
    tmp_path: Path, *, pool_depth_k: int = 5, is_synthetic: bool = True
) -> dict[str, Path]:
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text(
        json.dumps({"passage_id": "p1", "text": "alpha"}) + "\n", encoding="utf-8"
    )
    corpus_sha = sha256_file(corpus_path)

    query_manifest_path = tmp_path / "queries.json"
    query_manifest = {
        "queries": [
            {"query_id": "S5V31-Q-01", "split": "test", "domain": "Operating Systems"},
            {"query_id": "S5V31-Q-02", "split": "test", "domain": "Math for ML"},
            {"query_id": "S5V31-NC-01", "split": "test", "domain": "Negative Control"},
            {"query_id": "S5V31-NC-02", "split": "test", "domain": "Negative Control"},
        ]
    }
    query_manifest_path.write_text(json.dumps(query_manifest), encoding="utf-8")
    qm_sha = sha256_file(query_manifest_path)

    sys_hashes = {"v31_lexical_bm25": HEX_A, "v31_graph_1hop_backfill": HEX_B, "v31_graph_2hop_backfill": HEX_C}
    retrieval_manifest_path = tmp_path / "ret_manifest.json"
    retrieval_manifest_path.write_text(json.dumps({"variant_config_hashes": sys_hashes}), encoding="utf-8")
    rm_sha = sha256_file(retrieval_manifest_path)

    def _diag_entry(qid: str, pids: list[str], fb: bool, hops: int) -> dict[str, Any]:
        return {
            "query_id": qid,
            "results": [
                {"passage_id": pid, "rank": i, "score": 1.0 / i, "source": "graph"}
                for i, pid in enumerate(pids, start=1)
            ],
            "provenance": {"fallback_triggered": fb, "observed_hop_depth": hops},
        }

    p_order = ["p1", "p2", "p3", "p4", "p5"]
    retrieval_diag = {
        "inputs": {"corpus_sha256": corpus_sha},
        "variant_config_hashes": sys_hashes,
        "variants": {
            "v31_lexical_bm25": {
                "per_query_diagnostics": [
                    _diag_entry("S5V31-Q-01", p_order, False, 0),
                    _diag_entry("S5V31-Q-02", p_order, False, 0),
                    _diag_entry("S5V31-NC-01", p_order, False, 0),
                    _diag_entry("S5V31-NC-02", p_order, False, 0),
                ]
            },
            "v31_graph_1hop_backfill": {
                "per_query_diagnostics": [
                    _diag_entry("S5V31-Q-01", p_order, True, 0),
                    _diag_entry("S5V31-Q-02", list(reversed(p_order)), False, 1),
                    _diag_entry("S5V31-NC-01", p_order, True, 0),
                    _diag_entry("S5V31-NC-02", p_order, True, 0),
                ]
            },
            "v31_graph_2hop_backfill": {
                "per_query_diagnostics": [
                    _diag_entry("S5V31-Q-01", p_order, True, 0),
                    _diag_entry("S5V31-Q-02", p_order, False, 2),
                    _diag_entry("S5V31-NC-01", p_order, True, 0),
                    _diag_entry("S5V31-NC-02", p_order, True, 0),
                ]
            },
        },
    }
    diag_path = tmp_path / "diagnostics.json"
    diag_path.write_text(json.dumps(retrieval_diag), encoding="utf-8")

    # Build judgments covering all 4 queries x 5 passages = 20 pairs
    judgments: list[dict[str, Any]] = []
    pool_pairs: list[dict[str, Any]] = []
    idx = 0
    for qid in ("S5V31-Q-01", "S5V31-Q-02", "S5V31-NC-01", "S5V31-NC-02"):
        for pid in p_order:
            idx += 1
            pair_id = f"SYN-PAIR-{idx:03d}"
            pool_pairs.append({"pair_id": pair_id, "query_id": qid, "passage_id": pid})
            if qid == "S5V31-NC-01":
                ga = gc = fg = 0
            elif pid == "p1":
                ga = gc = fg = 2
            elif pid == "p2":
                ga, gc, fg = 1, 2, 1
            else:
                ga = gc = fg = 0
            is_dis = ga != gc
            judgments.append(
                {
                    "pair_id": pair_id,
                    "query_id": qid,
                    "passage_id": pid,
                    "passage_sha256": HEX_D,
                    "reviewer_a_grade": ga,
                    "reviewer_c_grade": gc,
                    "final_grade": fg,
                    "adjudication_source": "ADJUDICATED_HUMAN" if is_dis else "DUAL_HUMAN_AGREEMENT",
                    "supporting_quotation": "alpha" if fg > 0 else "",
                    "adjudication_rationale": "Resolved by adjudicator" if is_dis else "",
                    "adjudicator_id": "HUMAN_ADJ_01" if is_dis else "",
                }
            )

    pool_path = tmp_path / "pool.json"
    pool_path.write_text(json.dumps({"pool_id": "s5v31_syn_pool", "pairs": pool_pairs}), encoding="utf-8")
    pool_sha = sha256_file(pool_path)

    nc_path = tmp_path / "nc.json"
    nc_records = {
        "S5V31-NC-01": {
            "query_id": "S5V31-NC-01",
            "human_nc_classification": "confirmed_unanswerable",
            "verifier_id": "HUMAN_VER_01",
            "provenance_class": "INDEPENDENT_HUMAN",
            "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
            "human_attestation_signed": True,
            "attestation_signer": "HUMAN_VER_01",
            "signed_timestamp_utc": "2026-11-19T18:00:00Z",
            "corpus_sha256": corpus_sha,
            "rationale": "Verified absent across corpus.",
        },
        "S5V31-NC-02": {
            "query_id": "S5V31-NC-02",
            "human_nc_classification": "answerable_in_corpus",
            "verifier_id": "HUMAN_VER_01",
            "provenance_class": "INDEPENDENT_HUMAN",
            "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
            "human_attestation_signed": True,
            "attestation_signer": "HUMAN_VER_01",
            "signed_timestamp_utc": "2026-11-19T18:00:00Z",
            "corpus_sha256": corpus_sha,
            "rationale": "Reclassified as answerable in corpus.",
        },
    }
    nc_path.write_text(json.dumps(nc_records), encoding="utf-8")
    nc_sha = sha256_file(nc_path)

    disagreements = sum(1 for j in judgments if j["reviewer_a_grade"] != j["reviewer_c_grade"])
    gold = {
        "schema_version": GOLD_SCHEMA_VERSION_V31,
        "status": GOLD_STATUS_SYNTHETIC if is_synthetic else GOLD_STATUS_FINAL,
        "benchmark_config": {
            "benchmark_version": BENCHMARK_VERSION_V31,
            "corpus_id": "corpus_v31_syn",
            "corpus_sha256": corpus_sha,
            "query_manifest_id": "qm_v31_syn",
            "query_manifest_sha256": qm_sha,
            "split": "test",
            "approved_query_ids": ["S5V31-Q-01", "S5V31-Q-02", "S5V31-NC-01", "S5V31-NC-02"],
            "approved_negative_control_ids": ["S5V31-NC-01", "S5V31-NC-02"],
            "pool_id": "s5v31_syn_pool",
            "pool_sha256": pool_sha,
            "pool_depth_k": pool_depth_k,
            "expected_pair_count": len(judgments),
            "retrieval_manifest_sha256": rm_sha,
            "system_hashes": sys_hashes,
        },
        "reviewer_a_provenance": {
            "reviewer_id": "HUMAN_REV_A",
            "domain_group": "cs_systems",
            "provenance_class": "INDEPENDENT_HUMAN",
            "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
            "prior_exposure_disclosure": "NONE",
            "human_attestation_signed": True,
            "attestation_signer": "HUMAN_REV_A",
            "signed_timestamp_utc": "2026-11-19T18:00:00Z",
            "submission_sha256": HEX_E,
        },
        "reviewer_c_provenance": {
            "reviewer_id": "HUMAN_REV_C",
            "domain_group": "cs_systems",
            "provenance_class": "INDEPENDENT_HUMAN",
            "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
            "prior_exposure_disclosure": "NONE",
            "human_attestation_signed": True,
            "attestation_signer": "HUMAN_REV_C",
            "signed_timestamp_utc": "2026-11-19T18:00:00Z",
            "submission_sha256": HEX_F,
        },
        "inter_annotator_agreement": {
            "total_pairs": len(judgments),
            "exact_agreement_count": len(judgments) - disagreements,
            "disagreement_count": disagreements,
            "exact_agreement_rate": (len(judgments) - disagreements) / len(judgments),
            "cohens_kappa_unweighted": 0.8,
            "cohens_kappa_quadratic_weighted": 0.85,
        },
        "adjudication_summary": {
            "all_disagreements_adjudicated": True,
            "total_disagreements": disagreements,
            "adjudicated_count": disagreements,
            "adjudication_worksheet_sha256": HEX_E,
            "adjudicator_provenance": {
                "adjudicator_id": "HUMAN_ADJ_01",
                "provenance_class": "ADJUDICATED_HUMAN",
                "assistance_declaration": "NONE_INDEPENDENT_HUMAN",
                "human_attestation_signed": True,
                "attestation_signer": "HUMAN_ADJ_01",
                "signed_timestamp_utc": "2026-11-19T18:00:00Z",
            },
        },
        "negative_control_verifications": nc_records,
        "investigator_signoff": {
            "investigator_id": "HUMAN_PI_01",
            "approval_declaration": "Approved synthetic S5-v3.1 gold assembly for unit tests.",
            "human_signoff_confirmed": True,
            "signed_timestamp_utc": "2026-11-19T18:00:00Z",
            "corpus_sha256": corpus_sha,
            "query_manifest_sha256": qm_sha,
            "pool_sha256": pool_sha,
            "retrieval_manifest_sha256": rm_sha,
            "nc_verification_sha256": nc_sha,
        },
        "judgments": judgments,
    }
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")

    return {
        "corpus": corpus_path,
        "queries": query_manifest_path,
        "ret_manifest": retrieval_manifest_path,
        "diagnostics": diag_path,
        "pool": pool_path,
        "nc": nc_path,
        "gold": gold_path,
    }


@pytest.mark.unit
def test_legacy_preflight_blocks_silent_nc_bypass_on_v31_ids_and_empty_spec() -> None:
    """Task 1 regression: legacy preflight MUST fail closed instead of silently skipping NCs."""
    # Case 1: v3.1 query IDs fed into legacy v2.1 preflight -> must FAIL CLOSED
    res_v31 = PreflightResult(passed=False, schema_mode="ac_v2")
    validate_negative_controls(
        neg_records=None,
        pool_query_ids={"S5V31-Q-01", "S5V31-NC-01"},
        schema_mode="ac_v2",
        result=res_v31,
    )
    assert any(e.code == "UNVERIFIED_NEGATIVE_CONTROLS" for e in res_v31.errors)

    # Case 2: empty explicit expected_nc_ids -> must FAIL CLOSED
    res_empty = PreflightResult(passed=False, schema_mode="ac_v2")
    validate_negative_controls(
        neg_records={},
        pool_query_ids={"S5V31-Q-01"},
        schema_mode="ac_v2",
        result=res_empty,
        expected_nc_ids=[],
        benchmark_version="s5v3.1",
    )
    assert any(e.code == "UNVERIFIED_NEGATIVE_CONTROLS" for e in res_empty.errors)

    # Case 3: legacy Q-S5B2 pool missing all 3 provisional NC IDs -> must FAIL CLOSED
    res_missing = PreflightResult(passed=False, schema_mode="ac_v2")
    validate_negative_controls(
        neg_records={},
        pool_query_ids={"Q-S5B2-01", "Q-S5B2-02"},
        schema_mode="ac_v2",
        result=res_missing,
    )
    assert any(e.code == "UNVERIFIED_NEGATIVE_CONTROLS" for e in res_missing.errors)


@pytest.mark.unit
def test_v31_metrics_k5_k10_exact_values_and_unjudged_rejection() -> None:
    """Exact strict/lenient metrics at k=5 and fail-closed rejection on unjudged Top-K."""
    qrels = {"p1": 2, "p2": 1, "p3": 0, "p4": 0, "p5": 0}
    m_strict = evaluate_v31_query_ranking(
        ["p1", "p2", "p3", "p4", "p5"], qrels, pool_depth_k=5, rel_threshold=2
    )
    assert m_strict["precision_at_5"] == 0.2
    assert m_strict["pooled_recall_denominator"] == 1
    assert m_strict["pooled_recall_at_5"] == 1.0
    assert m_strict["mrr_at_5"] == 1.0
    assert m_strict["ndcg_at_5"] == 1.0
    assert m_strict["precision_at_10"] is None

    m_lenient = evaluate_v31_query_ranking(
        ["p1", "p2", "p3", "p4", "p5"], qrels, pool_depth_k=5, rel_threshold=1
    )
    assert m_lenient["precision_at_5"] == 0.4
    assert m_lenient["pooled_recall_denominator"] == 2
    assert m_lenient["pooled_recall_at_5"] == 1.0

    # Fail closed on unjudged Top-K passage
    with pytest.raises(V31PreflightError, match="unjudged passage"):
        evaluate_v31_query_ranking(
            ["p1", "p_UNJUDGED", "p3", "p4", "p5"], qrels, pool_depth_k=5, rel_threshold=2
        )


@pytest.mark.unit
def test_v31_preflight_and_eval_synthetic_end_to_end(tmp_path: Path) -> None:
    """Full synthetic S5-v3.1 preflight, NC reclassification, domain/fallback splits, and tables."""
    fx = _build_synthetic_v31_fixture(tmp_path, pool_depth_k=5, is_synthetic=True)
    pf = validate_v31_preflight(
        gold_labels_path=fx["gold"],
        retrieval_diagnostics_path=fx["diagnostics"],
        corpus_path=fx["corpus"],
        query_manifest_path=fx["queries"],
        pool_path=fx["pool"],
        retrieval_manifest_path=fx["ret_manifest"],
        nc_verification_path=fx["nc"],
        is_synthetic=True,
    )
    assert pf.passed is True, pf.errors
    assert pf.verified_negative_controls == ["S5V31-NC-01"]
    assert pf.reclassified_answerable_controls == ["S5V31-NC-02"]

    report = compute_v31_d1_evaluation(
        gold_labels_path=fx["gold"],
        retrieval_diagnostics_path=fx["diagnostics"],
        preflight=pf,
        query_manifest_path=fx["queries"],
    )
    assert report["is_synthetic"] is True
    assert report["synthetic_watermark"] == SYNTHETIC_BANNER
    assert report["pool_depth_k"] == 5
    assert "Operating Systems" in report["systems"]["v31_lexical_bm25"]["domain_breakdown"]
    assert report["systems"]["v31_graph_1hop_backfill"]["fallback_stratification"]["fallback_count"] == 2
    assert report["hop_comparison"]["available"] is True

    tables = write_results_tables(report, tmp_path / "tables")
    assert SYNTHETIC_BANNER in tables["markdown"].read_text(encoding="utf-8")
    assert SYNTHETIC_BANNER in tables["latex"].read_text(encoding="utf-8")
    assert "True," in tables["csv"].read_text(encoding="utf-8")


@pytest.mark.unit
def test_v31_authorization_gate_refuses_invalid_and_accepts_hash_pinned(tmp_path: Path) -> None:
    """Two-factor authorization gate rejects missing flag/tampered hash and accepts valid signoff."""
    fx = _build_synthetic_v31_fixture(tmp_path, pool_depth_k=5, is_synthetic=False)
    pf = validate_v31_preflight(
        gold_labels_path=fx["gold"],
        retrieval_diagnostics_path=fx["diagnostics"],
        corpus_path=fx["corpus"],
        query_manifest_path=fx["queries"],
        pool_path=fx["pool"],
        retrieval_manifest_path=fx["ret_manifest"],
        nc_verification_path=fx["nc"],
        is_synthetic=False,
    )
    assert pf.passed is True, pf.errors

    auth_file = tmp_path / "auth.json"
    tpl = build_v31_authorization_template(**pf.expected_hashes)
    auth_file.write_text(json.dumps(tpl), encoding="utf-8")

    # Missing flag -> refused
    with pytest.raises(V31AuthorizationError, match="--authorize-real-v31-d1"):
        validate_v31_authorization_gate(
            authorize_flag=False, authorization_path=auth_file, expected_hashes=pf.expected_hashes
        )

    # Unsigned template -> refused
    with pytest.raises(V31AuthorizationError, match="human_authorization_signed"):
        validate_v31_authorization_gate(
            authorize_flag=True, authorization_path=auth_file, expected_hashes=pf.expected_hashes
        )

    # Signed with exact hashes -> accepted
    tpl.update(
        {
            "status": AUTH_APPROVED_STATUS_V31,
            "investigator_id": "HUMAN_PI_01",
            "approval_declaration": "Investigator authorizes real S5-v3.1 D1 evaluation.",
            "human_authorization_signed": True,
            "signed_timestamp_utc": "2026-11-19T18:10:00Z",
        }
    )
    auth_file.write_text(json.dumps(tpl), encoding="utf-8")
    verified = validate_v31_authorization_gate(
        authorize_flag=True, authorization_path=auth_file, expected_hashes=pf.expected_hashes
    )
    assert verified["investigator_id"] == "HUMAN_PI_01"

    # CLI without --authorize-real-v31-d1 exits 3 (refused)
    rc_refused = cli_main(
        [
            "--gold-labels",
            str(fx["gold"]),
            "--retrieval-diagnostics",
            str(fx["diagnostics"]),
            "--output-dir",
            str(tmp_path / "out_refused"),
        ]
    )
    assert rc_refused == 3


@pytest.mark.unit
def test_v31_preflight_rejects_legacy_mixing_and_wrong_corpus_sha(tmp_path: Path) -> None:
    """Preflight fails closed on legacy v2.1 mixing and corpus SHA-256 mismatch."""
    fx = _build_synthetic_v31_fixture(tmp_path, pool_depth_k=5, is_synthetic=True)
    gold = json.loads(fx["gold"].read_text(encoding="utf-8"))
    gold["benchmark_config"]["benchmark_version"] = "s5v2.1"
    gold["benchmark_config"]["corpus_sha256"] = "0" * 64
    fx["gold"].write_text(json.dumps(gold), encoding="utf-8")

    pf = validate_v31_preflight(
        gold_labels_path=fx["gold"],
        retrieval_diagnostics_path=fx["diagnostics"],
        corpus_path=fx["corpus"],
        is_synthetic=True,
    )
    assert pf.passed is False
    codes = {e.code for e in pf.errors}
    assert "LEGACY_VERSION_MIXING" in codes
    assert "CORPUS_SHA_MISMATCH" in codes
