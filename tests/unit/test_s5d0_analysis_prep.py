"""Unit tests for S5-D0 Experimental Analysis Preparation.

Verifies:
1. Frozen artifact preservation (SHA-256 exact matches, zero modifications).
2. Deterministic reproducibility of S5-D0 six-system technical diagnostics.
3. Strict read-only guardrails & metric computation on synthetic toy inputs in
   evaluate_gold_labels_readonly.py (never touches real reviewer submissions).
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5D0_DIR = ROOT / "research" / "s5-d0-experimental-analysis-prep"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


diag_mod = _load_module("generate_s5d0_diagnostics", S5D0_DIR / "scripts" / "generate_s5d0_diagnostics.py")
eval_mod = _load_module("evaluate_gold_labels_readonly", S5D0_DIR / "scripts" / "evaluate_gold_labels_readonly.py")


def test_preserved_artifacts_match_frozen_hashes() -> None:
    manifest = diag_mod.verify_preserved_artifacts(ROOT)
    assert manifest["all_checks_passed"] is True
    assert manifest["mismatches"] == []
    assert manifest["verified_exact_matches"] >= 10  # 10 tracked + 2 local when present


def test_diagnostics_reproducible_and_relevance_free() -> None:
    committed = json.loads((S5D0_DIR / "reports" / "s5d0_technical_diagnostics.json").read_text(encoding="utf-8"))
    recomputed = diag_mod.compute_diagnostics(ROOT)
    assert recomputed == committed
    assert recomputed["relevance_metrics_computed"] is False
    assert recomputed["active_queries_count"] == 10
    assert recomputed["total_pooled_pairs"] == 254
    assert recomputed["query_coverage_diagnostics"]["total_missing_slots_out_of_100_by_system"]["baseline_graph_1hop"] == 31
    assert recomputed["fallback_diagnostics"]["repaired_graph_1hop_ablation"]["fallback_count"] == 4
    assert recomputed["fallback_diagnostics"]["repaired_graph_2hop_full"]["fallback_count"] == 4


def test_readonly_pipeline_rejects_unvalidated_gold_labels() -> None:
    pool_path = ROOT / "research" / "s5-b2-benchmark-correction" / "proposed_package_v2_1" / "retrieval_query_pool_blinded.json"
    pool_index, exp_ver, exp_sha = eval_mod.load_frozen_pool_index(pool_path)

    bad_payload = eval_mod.expected_gold_label_schema()
    bad_payload["status"] = "PROVISIONAL"
    bad_payload["reviewer_b_independence_confirmed"] = False
    bad_payload["all_disagreements_adjudicated"] = False
    bad_payload["judgments"] = []

    with pytest.raises(eval_mod.GoldLabelValidationError) as exc_info:
        eval_mod.validate_adjudicated_gold_labels(bad_payload, pool_index, exp_ver, exp_sha)

    msg = str(exc_info.value)
    assert "ADJUDICATED_HUMAN_GOLD_FINAL" in msg
    assert "reviewer_b_independence_confirmed" in msg
    assert "all_disagreements_adjudicated" in msg
    assert "Missing 254 required pair_id" in msg


def test_readonly_pipeline_refuses_unjudged_passage_in_top10() -> None:
    with pytest.raises(eval_mod.GoldLabelValidationError, match="unjudged passage"):
        eval_mod.evaluate_query_ranking(
            ["p1", "p_unjudged"],
            {"p1": 2},
            rel_threshold=2,
        )


def test_readonly_pipeline_exact_metrics_on_synthetic_fixture() -> None:
    # Purely synthetic fixture: 3 passages in pool, grades {p1: 2, p2: 1, p3: 0}
    # Ranking: [p3, p1, p2]
    qrels = {"p1": 2, "p2": 1, "p3": 0}
    res = eval_mod.evaluate_query_ranking(["p3", "p1", "p2"], qrels, rel_threshold=2)

    assert res["unjudged_at_5"] == 0
    assert res["unjudged_at_10"] == 0
    assert res["recall_at_5"] == 1.0
    assert res["recall_at_10"] == 1.0
    assert res["precision_at_5"] == 0.2
    assert res["precision_at_10"] == 0.1
    assert res["mrr_at_10"] == 0.5  # p1 at rank 2

    # DCG@5 = (2^0 - 1)/log2(2) + (2^2 - 1)/log2(3) + (2^1 - 1)/log2(4) = 0 + 3/log2(3) + 1/2
    # IDCG@5 = (2^2 - 1)/log2(2) + (2^1 - 1)/log2(3) + 0 = 3 + 1/log2(3)
    dcg = 3.0 / math.log2(3) + 1.0 / math.log2(4)
    idcg = 3.0 / math.log2(2) + 1.0 / math.log2(3)
    assert res["ndcg_at_5"] == round(dcg / idcg, 4)
    assert res["ndcg_at_10"] == round(dcg / idcg, 4)
