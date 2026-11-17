"""
S4-D Human Evidence Audit vs AI Annotations Integrity Tests.

Verifies:
1. Exact preservation of human scores from original audit Markdown and CSV
2. Matching of all 24 items to queries and corpus passage IDs
3. Reviewer A coverage (100%) and Reviewer B status (0% present, no fabrication)
4. Exact agreement rate (62.50%), binary agreement rate (87.50%), and weighted Cohen's kappa
5. Disagreement structure (100% are AI = Human + 1, no 2-point deviations)
6. Separate tracking of uncertain judgments (5/24)
7. Perfect true-negative handling on out-of-corpus query CIKM-PILOT-023
8. Tamper detection on modified scores
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "research" / "s4-b-annotation-integrity"
LOCAL_ONLY = ROOT / "artifacts" / "validation" / "local_only"

import sys
sys.path.insert(0, str(RESEARCH_DIR / "scripts"))
from run_s4d_human_comparison import run_comparison, compute_cohen_kappa


@pytest.fixture(scope="module")
def human_csv_path() -> Path:
    p = RESEARCH_DIR / "human_audit_labels_24.csv"
    assert p.exists(), f"Missing human audit CSV at {p}"
    return p


@pytest.fixture(scope="module")
def human_md_path() -> Path:
    p = RESEARCH_DIR / "human_audit_original.md"
    assert p.exists(), f"Missing human audit MD at {p}"
    return p


@pytest.fixture(scope="module")
def rev_a_json_path() -> Path:
    p = LOCAL_ONLY / "s4b_reviewer_a_scored.json"
    assert p.exists(), f"Missing Reviewer A scored JSON at {p}"
    return p


@pytest.fixture(scope="module")
def rev_b_json_path() -> Path:
    p = LOCAL_ONLY / "s4b_reviewer_b_template.json"
    assert p.exists(), f"Missing Reviewer B template JSON at {p}"
    return p


@pytest.fixture(scope="module")
def comparison_results(human_csv_path: Path, rev_a_json_path: Path, rev_b_json_path: Path) -> dict:
    return run_comparison(human_csv_path, rev_a_json_path, rev_b_json_path)


def test_human_audit_sample_size_and_queries(human_csv_path: Path) -> None:
    with human_csv_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 24, f"Expected exactly 24 human audit rows, got {len(rows)}"

    queries = [r["query_id"] for r in rows]
    unique_queries = list(dict.fromkeys(queries))
    assert len(unique_queries) == 6, f"Expected 6 unique queries, got {len(unique_queries)}"

    expected_queries = [
        "CIKM-PILOT-001",
        "CIKM-PILOT-005",
        "CIKM-PILOT-013",
        "CIKM-PILOT-002",
        "CIKM-PILOT-004",
        "CIKM-PILOT-023",
    ]
    assert unique_queries == expected_queries, f"Query sequence mismatch: {unique_queries}"

    for qid in expected_queries:
        q_rows = [r for r in rows if r["query_id"] == qid]
        assert len(q_rows) == 4, f"Query {qid} should have 4 candidates, got {len(q_rows)}"


def test_original_human_answers_preserved(human_csv_path: Path, human_md_path: Path) -> None:
    with human_csv_path.open("r", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))

    md_text = human_md_path.read_text(encoding="utf-8")
    for r in csv_rows:
        cid = r["candidate_id"]
        score = r["human_score"]
        # Check that score in CSV appears in the markdown
        assert cid in md_text, f"Candidate {cid} missing from original markdown"
        assert f"score (0 / 1 / 2): {score}" in md_text or f"score (0 / 1 / 2):{score}" in md_text, (
            f"Candidate {cid} score {score} not found in original markdown"
        )


def test_all_24_candidates_match_valid_corpus_passages(comparison_results: dict) -> None:
    records = comparison_results["matched_records"]
    assert len(records) == 24
    for r in records:
        assert r["passage_id"] != "UNKNOWN", f"Unmatched passage ID for {r['query_id']} {r['candidate_id']}"
        assert "::" in r["passage_id"], f"Malformed passage ID: {r['passage_id']}"
        assert r["ai_reviewer_a_score"] in (0, 1, 2), f"Invalid AI score for {r['candidate_id']}"
        assert r["human_score"] in (0, 1, 2), f"Invalid Human score for {r['candidate_id']}"


def test_ai_reviewer_a_complete_and_reviewer_b_missing(comparison_results: dict) -> None:
    records = comparison_results["matched_records"]
    # All 24 have Reviewer A scores
    assert all(r["ai_reviewer_a_score"] is not None for r in records)
    # All 24 have Reviewer B missing (null)
    assert all(r["ai_reviewer_b_score"] is None for r in records)
    assert comparison_results["rev_b_missing_count"] == 24


def test_agreement_rates_and_cohen_kappa_reproducibility(comparison_results: dict) -> None:
    res = comparison_results
    assert res["exact_agreements"] == 15
    assert res["disagreement_count"] == 9
    assert abs(res["exact_agreement_rate"] - 0.625) < 1e-6
    assert abs(res["disagreement_rate"] - 0.375) < 1e-6

    assert res["binary_agreements"] == 21
    assert abs(res["binary_agreement_rate"] - 0.875) < 1e-6

    assert abs(res["cohen_kappa_unweighted"] - 0.4433) < 1e-3
    assert abs(res["cohen_kappa_linear_weighted"] - 0.6029) < 1e-3
    assert abs(res["cohen_kappa_quadratic_weighted"] - 0.7477) < 1e-3
    assert abs(res["cohen_kappa_binary"] - 0.7500) < 1e-3


def test_all_disagreements_are_single_point_ai_lenience(comparison_results: dict) -> None:
    disagreements = comparison_results["disagreements"]
    assert len(disagreements) == 9

    for d in disagreements:
        h = d["human_score"]
        a = d["ai_reviewer_a_score"]
        diff = d["diff_human_minus_ai_a"]
        # AI score is strictly human_score + 1
        assert diff == -1, f"Expected diff -1 (AI = Human + 1), got {diff} for {d['query_id']} {d['candidate_id']}"
        assert a == h + 1

    # Zero cases where human was higher than AI
    records = comparison_results["matched_records"]
    assert all(r["human_score"] <= r["ai_reviewer_a_score"] for r in records)

    # 3 cases of 0 vs 1
    assert sum(1 for d in disagreements if d["human_score"] == 0 and d["ai_reviewer_a_score"] == 1) == 3
    # 6 cases of 1 vs 2
    assert sum(1 for d in disagreements if d["human_score"] == 1 and d["ai_reviewer_a_score"] == 2) == 6


def test_uncertain_judgments_flagged_and_isolated(comparison_results: dict) -> None:
    unc = comparison_results["uncertain_records"]
    assert len(unc) == 5

    unc_cids = [(u["query_id"], u["candidate_id"]) for u in unc]
    expected_unc = [
        ("CIKM-PILOT-001", "CAND-03"),
        ("CIKM-PILOT-005", "CAND-03"),
        ("CIKM-PILOT-004", "CAND-07"),
        ("CIKM-PILOT-004", "CAND-16"),
        ("CIKM-PILOT-023", "CAND-15"),
    ]
    assert unc_cids == expected_unc

    # 2 agreements, 3 disagreements among uncertain
    assert sum(1 for u in unc if u["exact_match_ai_a"]) == 2
    assert sum(1 for u in unc if not u["exact_match_ai_a"]) == 3

    # Certain subset (N=19)
    cert = comparison_results["certain_stats"]
    assert cert["total"] == 19
    assert cert["exact_agreements"] == 13
    assert abs(cert["exact_agreement_rate"] - (13 / 19)) < 1e-6
    assert cert["binary_agreements"] == 16
    assert abs(cert["binary_agreement_rate"] - (16 / 19)) < 1e-6


def test_out_of_corpus_negative_query_true_negative_rejection(comparison_results: dict) -> None:
    records = [r for r in comparison_results["matched_records"] if r["query_id"] == "CIKM-PILOT-023"]
    assert len(records) == 4
    for r in records:
        assert r["human_score"] == 0, f"Expected human score 0 for negative query, got {r['human_score']}"
        assert r["ai_reviewer_a_score"] == 0, f"Expected AI score 0 for negative query, got {r['ai_reviewer_a_score']}"
        assert r["exact_match_ai_a"] is True


def test_tamper_detection_in_comparison() -> None:
    cm = [
        [9, 3, 0],
        [0, 2, 6],
        [0, 0, 4],
    ]
    k_orig, _, _ = compute_cohen_kappa(cm, "quadratic")
    assert abs(k_orig - 0.7477) < 1e-3

    # Mutate confusion matrix (simulating score tampering)
    cm_tampered = [
        [7, 3, 2],  # added severe 2-point disagreement
        [0, 2, 6],
        [0, 0, 4],
    ]
    k_tampered, _, _ = compute_cohen_kappa(cm_tampered, "quadratic")
    assert k_tampered < k_orig
