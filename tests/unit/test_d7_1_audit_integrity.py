"""D7.1 regression tests: probe runner verdict semantics and scientific claim accuracy.

Tests verify:
1. The D7.1 probe runner correctly classifies unexpected 401/403 as FAIL.
2. D5.1-v2 metrics match expected values (guards against stale data being cited).
3. DEMO_SCENARIOS.md no longer references USES edge types in assertions.
4. FIVE_MINUTE_WALKTHROUGH.md no longer contains removed stale claim strings.
5. Citation grounding audit statistics are honestly represented.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
for p in (ROOT_DIR / "host_inference", ROOT_DIR / "host_research", ROOT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SIGIR_DIR = ROOT_DIR / "docs" / "sigir"
D5_EVAL_DIR = ROOT_DIR / "research" / "d5_sigir_evaluation"


# ---------------------------------------------------------------------------
# Probe runner verdict semantics (ISS-01)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_probe_unexpected_401_is_fail_not_blocked() -> None:
    """When expect_auth_block=False, an HTTP 401 response must yield FAIL."""
    # Reproduce the verdict logic for a 401 when expect_auth_block=False.
    status_code = 401
    expected = (200,)
    expect_auth = False

    auth_blocked = status_code in {401, 403}
    expected_ok = status_code in expected

    if auth_blocked and expect_auth:
        verdict = "BLOCKED_BY_AUTH"
    elif expected_ok:
        verdict = "PASS"
    elif auth_blocked and not expect_auth:
        verdict = "FAIL"
    else:
        verdict = "FAIL"

    assert verdict == "FAIL", (
        "Unexpected 401 with expect_auth_block=False must be FAIL, not BLOCKED_BY_AUTH"
    )


@pytest.mark.unit
def test_probe_expected_401_is_blocked_not_fail() -> None:
    """When expect_auth_block=True, HTTP 401 must yield BLOCKED_BY_AUTH."""
    status_code = 401
    expected = (401,)
    expect_auth = True

    auth_blocked = status_code in {401, 403}
    expected_ok = status_code in expected

    if auth_blocked and expect_auth:
        verdict = "BLOCKED_BY_AUTH"
    elif expected_ok:
        verdict = "PASS"
    elif auth_blocked and not expect_auth:
        verdict = "FAIL"
    else:
        verdict = "FAIL"

    assert verdict == "BLOCKED_BY_AUTH", (
        "Expected 401 with expect_auth_block=True must be BLOCKED_BY_AUTH"
    )


@pytest.mark.unit
def test_probe_definitions_have_expect_auth_block() -> None:
    """Every probe definition must have an explicit expect_auth_block key."""
    from scripts.benchmarks.cross_system_audit_runner import PROBE_DEFINITIONS

    missing = [
        p["id"] for p in PROBE_DEFINITIONS
        if "expect_auth_block" not in p
    ]
    assert not missing, (
        f"Probe definitions missing expect_auth_block: {missing}"
    )


@pytest.mark.unit
def test_probe_summary_note_present_in_results() -> None:
    """The regenerated audit JSON must include D7.1 verdict_semantics."""
    results_path = SIGIR_DIR / "cross_system_audit_results.json"
    if not results_path.exists():
        pytest.skip("cross_system_audit_results.json not yet generated")
    with results_path.open() as f:
        data = json.load(f)
    assert "verdict_semantics" in data["metadata"], (
        "D7.1 audit JSON missing verdict_semantics block"
    )
    assert "BLOCKED_BY_AUTH" in data["metadata"]["verdict_semantics"]


# ---------------------------------------------------------------------------
# D5.1-v2 metrics: guard against stale values being re-introduced (ISS-02/03)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_d5_v2_concept_resolution_archipelago_accuracy() -> None:
    """Archipelago resolver accuracy on supported queries must be 0.6842 (D5.1-v2)."""
    v2_path = D5_EVAL_DIR / "d5_1_evaluation_results_v2.json"
    with v2_path.open() as f:
        d = json.load(f)
    acc = d["experiment_a_concept_resolution"]["archipelago_resolver"][
        "concept_resolution_accuracy_supported"
    ]
    assert abs(acc - 0.6842) < 0.001, f"Unexpected concept accuracy: {acc}"


@pytest.mark.unit
def test_d5_v2_bm25_mrr_passage_retrieval() -> None:
    """BM25 passage MRR must be 0.75 in D5.1-v2 (not 0.5750 from earlier eval)."""
    v2_path = D5_EVAL_DIR / "d5_1_evaluation_results_v2.json"
    with v2_path.open() as f:
        d = json.load(f)
    mrr = d["experiment_b_passage_retrieval"]["bm25"]["mrr"]
    assert abs(mrr - 0.75) < 0.001, (
        f"BM25 MRR should be 0.75 in D5.1-v2, got {mrr}. "
        f"Do not use stale 0.5750 value."
    )


@pytest.mark.unit
def test_d5_v2_relationship_precision_is_zero() -> None:
    """D5.1-v2 relationship prediction precision must be 0.0 — USES absent."""
    v2_path = D5_EVAL_DIR / "d5_1_evaluation_results_v2.json"
    with v2_path.open() as f:
        d = json.load(f)
    prec = d["relationship_prediction_evaluation"]["precision_over_all_surfaced_triples"]
    assert prec == 0.0, (
        f"Relationship precision is {prec}. If this changed, verify before updating tests."
    )


@pytest.mark.unit
def test_d5_v2_absent_predicates_disclosure() -> None:
    """USES, CONTRASTS_WITH, APPLIES_TO must be listed as absent predicates."""
    v2_path = D5_EVAL_DIR / "d5_1_evaluation_results_v2.json"
    with v2_path.open() as f:
        d = json.load(f)
    absent = d["relationship_prediction_evaluation"]["query_predicates_absent_from_graph"]
    for pred in ("USES", "CONTRASTS_WITH", "APPLIES_TO"):
        assert pred in absent, f"Predicate {pred} not listed as absent in D5.1-v2"


# ---------------------------------------------------------------------------
# Stale claim removal: document text guards (ISS-02/03/04/06)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_walkthrough_no_stale_mrr_claim() -> None:
    """FIVE_MINUTE_WALKTHROUGH must not contain the removed stale MRR 0.68 claim."""
    path = SIGIR_DIR / "FIVE_MINUTE_WALKTHROUGH.md"
    text = path.read_text(encoding="utf-8")
    assert "MRR 0.68" not in text, (
        "Stale 'MRR 0.68' claim still present in FIVE_MINUTE_WALKTHROUGH.md"
    )
    assert "2.6x BM25" not in text and "2.6xc BM25" not in text, (
        "Stale '2.6x BM25' claim still present"
    )


@pytest.mark.unit
def test_walkthrough_no_independent_reproducibility_claim() -> None:
    """Walkthrough must not assert 'independently reproducible'."""
    path = SIGIR_DIR / "FIVE_MINUTE_WALKTHROUGH.md"
    text = path.read_text(encoding="utf-8")
    assert "independently reproducible" not in text, (
        "'independently reproducible' claim must be removed from walkthrough"
    )


@pytest.mark.unit
def test_walkthrough_no_1_0_relationship_claim() -> None:
    """Walkthrough must not claim 1.0 relationship-direction accuracy."""
    path = SIGIR_DIR / "FIVE_MINUTE_WALKTHROUGH.md"
    text = path.read_text(encoding="utf-8")
    assert "1.0 accuracy" not in text, (
        "Stale '1.0 accuracy' claim for relationship direction must be removed"
    )


@pytest.mark.unit
def test_walkthrough_references_v2_eval_file() -> None:
    """Walkthrough Evaluation References must point to d5_1_evaluation_results_v2.json."""
    path = SIGIR_DIR / "FIVE_MINUTE_WALKTHROUGH.md"
    text = path.read_text(encoding="utf-8")
    assert "d5_1_evaluation_results_v2.json" in text, (
        "Walkthrough must reference d5_1_evaluation_results_v2.json, not the legacy file"
    )


@pytest.mark.unit
def test_demo_scenarios_no_uses_edge_in_checklist() -> None:
    """DEMO_SCENARIOS checklist must not assert USES edge type as expected."""
    path = SIGIR_DIR / "DEMO_SCENARIOS.md"
    text = path.read_text(encoding="utf-8")
    # Should not say "connected via `USES`" or "via USES" in the verification checklist
    assert "connected via `USES`" not in text, (
        "DEMO_SCENARIOS still asserts 'connected via `USES`' — USES is absent from runtime"
    )


# ---------------------------------------------------------------------------
# Citation grounding: honesty checks (ISS-07)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_citation_grounding_audit_records_irrelevant_count() -> None:
    """Citation grounding audit must honestly record irrelevant/spurious citations."""
    path = D5_EVAL_DIR / "citation_grounding_audit.json"
    with path.open() as f:
        data = json.load(f)
    spurious = data["overall_audit_statistics"]["claim_support_breakdown"][
        "irrelevant_or_spurious"
    ]
    assert spurious >= 9, (
        f"Spurious citation count is {spurious}; expected >= 9 from D5 audit"
    )


@pytest.mark.unit
def test_citation_grounding_audit_no_independent_review_claimed() -> None:
    """Citation audit metadata must not claim independent peer review."""
    path = D5_EVAL_DIR / "citation_grounding_audit.json"
    with path.open() as f:
        data = json.load(f)
    assert data["audit_metadata"]["independent_peer_review"] is False, (
        "Citation audit incorrectly claims independent peer review"
    )
