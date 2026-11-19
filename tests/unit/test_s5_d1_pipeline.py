"""Comprehensive synthetic unit tests for S5-D1 Preflight, Authorization Gate, Evaluation, Tables & Figures.

All fixtures are 100% synthetic and written to pytest tmp_path.
Never touches real reviewer workbooks, frozen reports, or legacy evaluate_gold_labels_readonly.py.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5D0_SCRIPTS = ROOT / "research" / "s5-d0-experimental-analysis-prep" / "scripts"
if str(S5D0_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(S5D0_SCRIPTS))

from d1_pipeline.auth_gate import (  # noqa: E402
    AuthorizationError,
    authorization_template,
    validate_investigator_authorization,
)
from d1_pipeline.constants import (  # noqa: E402
    SYSTEM_BASELINE_1HOP,
    SYSTEM_REPAIRED_1HOP,
    SYSTEM_REPAIRED_2HOP,
)
from d1_pipeline.figures import generate_all_figures  # noqa: E402
from d1_pipeline.metrics import compute_d1_evaluation, evaluate_query_ranking_extended  # noqa: E402
from d1_pipeline.preflight import PreflightError, validate_d1_preflight  # noqa: E402
from d1_pipeline.synthetic import build_synthetic_bundle  # noqa: E402
from d1_pipeline.tables import generate_all_tables  # noqa: E402
import s5_d1_evaluate  # noqa: E402
import s5_d1_preflight  # noqa: E402
import s5_d1_tables_figures  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# --- 1. Preflight happy paths (both A/C v2 and legacy v1) ---


def test_preflight_passes_valid_ac_v2_and_legacy_v1(tmp_path: Path) -> None:
    b_v2 = build_synthetic_bundle(tmp_path / "v2", schema_mode="ac_v2")
    res_v2 = validate_d1_preflight(
        gold_labels_path=b_v2["gold"],
        frozen_pool_path=b_v2["pool"],
        frozen_rankings_path=b_v2["rankings"],
        corpus_passages_path=b_v2["passages"],
        schema_mode="auto",
        is_synthetic=True,
    )
    assert res_v2.passed is True
    assert res_v2.schema_mode == "ac_v2"
    assert res_v2.verified_negative_controls == ["Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11"]

    b_v1 = build_synthetic_bundle(tmp_path / "v1", schema_mode="v1")
    res_v1 = validate_d1_preflight(
        gold_labels_path=b_v1["gold"],
        frozen_pool_path=b_v1["pool"],
        frozen_rankings_path=b_v1["rankings"],
        corpus_passages_path=b_v1["passages"],
        schema_mode="auto",
        is_synthetic=True,
    )
    assert res_v1.passed is True
    assert res_v1.schema_mode == "v1"


# --- 2. All 10 preflight failure / reclassification conditions ---


def test_preflight_rejects_missing_source_file(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    res = validate_d1_preflight(
        gold_labels_path=tmp_path / "nonexistent_gold.json",
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
    )
    assert res.passed is False
    assert any(e.category == "MISSING_SOURCE_FILE" for e in res.errors)


def test_preflight_rejects_invalid_gold_schema(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    gold = _load_json(b["gold"])
    gold["schema_version"] = "unknown_schema_v99"
    gold["status"] = "DRAFT_PROVISIONAL"
    _save_json(b["gold"], gold)
    res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
    )
    assert res.passed is False
    assert any(e.category == "INVALID_GOLD_SCHEMA" for e in res.errors)


def test_preflight_rejects_pair_id_and_hash_misalignment(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    gold = _load_json(b["gold"])
    gold["pool_sha256"] = "deadbeef" * 8
    gold["judgments"][0]["passage_sha256"] = "cafebabe" * 8
    gold["judgments"][1]["passage_id"] = "syn_doc/wrong_passage"
    _save_json(b["gold"], gold)
    res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
    )
    assert res.passed is False
    cats = {e.category for e in res.errors}
    assert "PAIR_ID_HASH_MISALIGNMENT" in cats


def test_preflight_rejects_invalid_human_provenance_and_legacy_b_bypass(tmp_path: Path) -> None:
    # A/C v2 rejects AI provenance
    b_v2 = build_synthetic_bundle(tmp_path / "v2", schema_mode="ac_v2")
    gold = _load_json(b_v2["gold"])
    gold["reviewer_c_provenance"]["provenance_class"] = "AI_ASSISTED_OR_GENERATED"
    gold["reviewer_a_provenance"]["human_attestation_signed"] = False
    _save_json(b_v2["gold"], gold)
    res_v2 = validate_d1_preflight(
        gold_labels_path=b_v2["gold"],
        frozen_pool_path=b_v2["pool"],
        frozen_rankings_path=b_v2["rankings"],
    )
    assert res_v2.passed is False
    assert any(e.category == "INVALID_HUMAN_PROVENANCE" for e in res_v2.errors)

    # Legacy v1 still refuses reviewer_b_independence_confirmed=False
    b_v1 = build_synthetic_bundle(tmp_path / "v1", schema_mode="v1")
    gold_v1 = _load_json(b_v1["gold"])
    gold_v1["reviewer_b_independence_confirmed"] = False
    _save_json(b_v1["gold"], gold_v1)
    res_v1 = validate_d1_preflight(
        gold_labels_path=b_v1["gold"],
        frozen_pool_path=b_v1["pool"],
        frozen_rankings_path=b_v1["rankings"],
        schema_mode="v1",
    )
    assert res_v1.passed is False
    assert any(e.category == "INVALID_HUMAN_PROVENANCE" for e in res_v1.errors)


def test_preflight_rejects_missing_judgments_and_inconsistent_grades(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    gold = _load_json(b["gold"])
    gold["judgments"].pop()  # missing 1 pair
    gold["judgments"][0]["final_grade"] = 1  # conflicts with DUAL_HUMAN_AC_AGREEMENT (A=2, C=2)
    _save_json(b["gold"], gold)
    res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
    )
    assert res.passed is False
    cats = {e.category for e in res.errors}
    assert "MISSING_JUDGMENTS" in cats
    assert "INCONSISTENT_GRADES" in cats


def test_preflight_rejects_quote_mismatch_and_incomplete_adjudication(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    gold = _load_json(b["gold"])
    gold["adjudication_summary"]["all_ac_disagreements_adjudicated"] = False
    gold["judgments"][0]["supporting_quotation"] = "fabricated non-verbatim quote"
    gold["judgments"][2]["adjudication_rationale"] = ""
    _save_json(b["gold"], gold)
    res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
        corpus_passages_path=b["passages"],
    )
    assert res.passed is False
    cats = {e.category for e in res.errors}
    assert "QUOTE_MISMATCH" in cats
    assert "INCOMPLETE_ADJUDICATION" in cats


def test_preflight_rejects_unverified_negative_controls(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    gold = _load_json(b["gold"])
    del gold["negative_control_verifications"]["Q-S5B2-11"]
    _save_json(b["gold"], gold)
    res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
    )
    assert res.passed is False
    assert any(e.category == "UNVERIFIED_NEGATIVE_CONTROLS" for e in res.errors)


def test_preflight_handles_negative_control_reclassification_explicitly(tmp_path: Path) -> None:
    b = build_synthetic_bundle(
        tmp_path,
        schema_mode="ac_v2",
        neg_control_overrides={
            "Q-S5B2-08": "answerable_in_corpus",
            "Q-S5B2-11": "AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION",
        },
    )
    res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
        is_synthetic=True,
    )
    assert res.passed is True
    assert res.verified_negative_controls == ["Q-S5B2-03"]
    assert res.reclassified_answerable_controls == ["Q-S5B2-08"]
    assert res.excluded_negative_controls == ["Q-S5B2-11"]

    report = compute_d1_evaluation(
        frozen_rankings_path=b["rankings"],
        gold_labels_path=b["gold"],
        preflight=res,
    )
    strat = report["query_stratification"]
    assert strat["answerable_queries"] == ["Q-S5B2-01", "Q-S5B2-02", "Q-S5B2-08"]
    assert strat["verified_negative_controls"] == ["Q-S5B2-03"]
    assert strat["reclassified_as_answerable"] == ["Q-S5B2-08"]
    assert strat["excluded_negative_controls"] == ["Q-S5B2-11"]
    assert report["systems"]["bm25"]["per_query_strict"]["Q-S5B2-08"]["reclassified_from_provisional_neg_control"] is True
    assert "Q-S5B2-11" in report["systems"]["bm25"]["excluded_negative_control_behavior"]


# --- 3. Explicit Investigator-Authorization Gate ---


def test_authorization_gate_refusal_and_acceptance(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    preflight_real = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
        is_synthetic=False,
    )
    assert preflight_real.passed is True

    # Refusal 1: missing CLI flag
    with pytest.raises(AuthorizationError, match="--authorize-real-d1"):
        validate_investigator_authorization(
            authorize_real_d1_flag=False,
            auth_artifact_path=b["auth"],
            preflight=preflight_real,
        )

    # Refusal 2: synthetic preflight cannot authorize real D1
    preflight_syn = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
        is_synthetic=True,
    )
    with pytest.raises(AuthorizationError, match="synthetic"):
        validate_investigator_authorization(
            authorize_real_d1_flag=True,
            auth_artifact_path=b["auth"],
            preflight=preflight_syn,
        )

    # Refusal 3: hash mismatch in auth artifact
    bad_auth = tmp_path / "bad_auth.json"
    auth_data = _load_json(b["auth"])
    auth_data["gold_labels_sha256"] = "0" * 64
    _save_json(bad_auth, auth_data)
    with pytest.raises(AuthorizationError, match="gold_labels_sha256 mismatch"):
        validate_investigator_authorization(
            authorize_real_d1_flag=True,
            auth_artifact_path=bad_auth,
            preflight=preflight_real,
        )

    # Refusal 4: blank template cannot pass
    blank_auth = tmp_path / "blank_auth.json"
    _save_json(blank_auth, authorization_template())
    with pytest.raises(AuthorizationError):
        validate_investigator_authorization(
            authorize_real_d1_flag=True,
            auth_artifact_path=blank_auth,
            preflight=preflight_real,
        )

    # Acceptance: valid flag + valid non-synthetic preflight + matching hashes
    rec = validate_investigator_authorization(
        authorize_real_d1_flag=True,
        auth_artifact_path=b["auth"],
        preflight=preflight_real,
    )
    assert rec["authorized"] is True
    assert rec["investigator_id"] == "SYNTHETIC_PI_HUMAN"


# --- 4. Hand-calculated exact metric assertions ---


def test_exact_hand_calculated_metrics_strict_and_lenient() -> None:
    # Pool grades: p1=2, p2=1, p3=2, p4=0
    # Ranking: [p4(0), p2(1), p1(2), p3(2)]
    qrels = {"p1": 2, "p2": 1, "p3": 2, "p4": 0}
    ranking = ["p4", "p2", "p1", "p3"]

    strict = evaluate_query_ranking_extended(ranking, qrels, rel_threshold=2)
    assert strict["pooled_recall_denominator"] == 2
    assert strict["precision_at_5"] == round(2 / 5.0, 4)
    assert strict["precision_at_10"] == round(2 / 10.0, 4)
    assert strict["pooled_recall_at_5"] == 1.0
    assert strict["pooled_recall_at_10"] == 1.0
    assert strict["mrr_at_10"] == round(1 / 3.0, 4)  # first grade==2 is p1 at rank 3
    assert strict["returned_count"] == 4
    assert strict["missing_slots_at_5"] == 1
    assert strict["missing_slots_at_10"] == 6
    assert strict["is_short_list"] is True

    # DCG = 0/log2(2) + (2^1-1)/log2(3) + (2^2-1)/log2(4) + (2^2-1)/log2(5)
    # IDCG = 3/log2(2) + 3/log2(3) + 1/log2(4) + 0/log2(5)
    dcg = 1.0 / math.log2(3) + 3.0 / math.log2(4) + 3.0 / math.log2(5)
    idcg = 3.0 / math.log2(2) + 3.0 / math.log2(3) + 1.0 / math.log2(4)
    assert strict["ndcg_at_5"] == round(dcg / idcg, 4)
    assert strict["ndcg_at_10"] == round(dcg / idcg, 4)

    lenient = evaluate_query_ranking_extended(ranking, qrels, rel_threshold=1)
    assert lenient["pooled_recall_denominator"] == 3
    assert lenient["precision_at_5"] == round(3 / 5.0, 4)
    assert lenient["precision_at_10"] == round(3 / 10.0, 4)
    assert lenient["pooled_recall_at_5"] == 1.0
    assert lenient["pooled_recall_at_10"] == 1.0
    assert lenient["mrr_at_10"] == round(1 / 2.0, 4)  # first grade>=1 is p2 at rank 2

    # Unjudged passage raises PreflightError
    with pytest.raises(PreflightError, match="unjudged"):
        evaluate_query_ranking_extended(["p1", "p_unknown"], qrels, rel_threshold=2)


# --- 5. Full evaluation: fallback, short-list, neg-control, 1-hop vs 2-hop ---


def test_full_evaluation_fallback_shortlist_negcontrol_and_hop_comparison(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    preflight = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
        corpus_passages_path=b["passages"],
        is_synthetic=True,
    )
    report = compute_d1_evaluation(
        frozen_rankings_path=b["rankings"],
        gold_labels_path=b["gold"],
        preflight=preflight,
    )
    assert report["is_synthetic"] is True
    assert "SYNTHETIC" in report["watermark"]

    # Fallback split on repaired_graph_1hop_ablation: Q-S5B2-01 is fallback, Q-S5B2-02 is non-fallback
    fb = report["systems"][SYSTEM_REPAIRED_1HOP]["fallback_analysis"]
    assert fb["fallback_query_ids"] == ["Q-S5B2-01"]
    assert fb["non_fallback_query_ids"] == ["Q-S5B2-02"]
    assert fb["fallback_count"] == 1
    assert fb["non_fallback_count"] == 1

    # Short-list accounting on baseline_graph_1hop: lengths [2, 1, 1, 1, 1] -> total 6 of 50 slots
    sl = report["systems"][SYSTEM_BASELINE_1HOP]["short_list_accounting"]
    assert sl["short_list_queries_count"] == 5
    assert sl["total_returned_slots_top10"] == 6
    assert sl["missing_slots_at_10"] == 44

    # Negative-control behavior: Q-S5B2-08 has p11(grade=1) in top10 for bm25
    neg = report["systems"]["bm25"]["negative_control_behavior"]
    assert set(neg.keys()) == {"Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11"}
    assert neg["Q-S5B2-03"]["any_grade_ge_1_in_top10"] is False
    assert neg["Q-S5B2-08"]["any_grade_ge_1_in_top10"] is True
    assert neg["Q-S5B2-08"]["any_grade_eq_2_in_top10"] is False

    # 1-hop vs 2-hop comparison: 2-hop ranks p1,p3 above p2 on Q01 and p5 above p7 on Q02 -> positive delta
    hop = report["one_hop_vs_two_hop_comparison"]
    assert hop["available"] is True
    assert hop["one_hop_system"] == SYSTEM_REPAIRED_1HOP
    assert hop["two_hop_system"] == SYSTEM_REPAIRED_2HOP
    assert hop["macro_strict_delta_2hop_minus_1hop"]["mrr_at_10"] == 0.5  # 1.0 - 0.5
    assert hop["macro_strict_delta_2hop_minus_1hop"]["ndcg_at_10"] > 0.0


# --- 6. Table & figure generation + SYNTHETIC watermarking + CLI smoke tests ---


def test_tables_figures_and_cli_synthetic_watermarks(tmp_path: Path) -> None:
    eval_out = tmp_path / "eval_report.json"
    rc_pre = s5_d1_preflight.main(["--synthetic-demo", "--output", str(tmp_path / "preflight.json")])
    assert rc_pre == 0

    rc_eval = s5_d1_evaluate.main(["--synthetic-only", "--output", str(eval_out)])
    assert rc_eval == 0
    syn_eval_path = tmp_path / "SYNTHETIC_eval_report.json"
    assert syn_eval_path.exists()

    # Refusing real gold without --authorize-real-d1
    b = build_synthetic_bundle(tmp_path / "refusal", schema_mode="ac_v2")
    rc_refuse = s5_d1_evaluate.main(["--gold-labels", str(b["gold"])])
    assert rc_refuse == 3

    out_dir = tmp_path / "artifacts"
    rc_tf = s5_d1_tables_figures.main(["--eval-report", str(syn_eval_path), "--output-dir", str(out_dir)])
    assert rc_tf == 0

    report = _load_json(syn_eval_path)
    tables = generate_all_tables(report, out_dir / "tables")
    figures = generate_all_figures(report, out_dir / "figures")

    for path_str in (*tables.values(), *figures.values()):
        p = Path(path_str)
        assert p.exists()
        assert p.name.startswith("SYNTHETIC_")
        text = p.read_text(encoding="utf-8")
        assert "SYNTHETIC" in text

    svg_text = Path(figures["fig1_system_effectiveness_svg"]).read_text(encoding="utf-8")
    assert svg_text.startswith("<svg")
    assert "[SYNTHETIC]" in svg_text


def test_preflight_validates_module4_neg_control_worksheet_schema(tmp_path: Path) -> None:
    b = build_synthetic_bundle(tmp_path, schema_mode="ac_v2")
    neg_ws = {
        "schema_version": "s5_negative_control_verification_v1",
        "is_synthetic": True,
        "queries": [
            {
                "query_id": qid,
                "human_answerability_classification": "NO_ANSWER_IN_FROZEN_CORPUS",
                "d1_evaluation_impact": "RETAIN_AS_VERIFIED_NEGATIVE_CONTROL",
                "human_provenance": {
                    "verifier_id": "SYNTHETIC_VERIFIER_M4",
                    "provenance_class": "INDEPENDENT_HUMAN",
                    "human_attestation_confirmed": True,
                },
            }
            for qid in ("Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11")
        ],
    }
    neg_path = tmp_path / "SYNTHETIC_m4_neg_control.json"
    _save_json(neg_path, neg_ws)

    ok_res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
        neg_control_path=neg_path,
        is_synthetic=True,
    )
    assert ok_res.passed is True
    assert ok_res.verified_negative_controls == ["Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11"]

    # HOLD_UNVERIFIED_NEGATIVE_CONTROL must fail preflight
    neg_ws["queries"][0]["d1_evaluation_impact"] = "HOLD_UNVERIFIED_NEGATIVE_CONTROL"
    _save_json(neg_path, neg_ws)
    hold_res = validate_d1_preflight(
        gold_labels_path=b["gold"],
        frozen_pool_path=b["pool"],
        frozen_rankings_path=b["rankings"],
        neg_control_path=neg_path,
        is_synthetic=True,
    )
    assert hold_res.passed is False
    assert any(e.category == "UNVERIFIED_NEGATIVE_CONTROLS" for e in hold_res.errors)
