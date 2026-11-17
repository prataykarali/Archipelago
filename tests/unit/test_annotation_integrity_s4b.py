"""
S4-B Annotation Integrity Tests.

Tests for:
1. Leakage: Reviewer B worksheet must not contain question categories, system names, scores
2. Score preservation: Reviewer A scores are faithfully extracted, not silently changed
3. Completeness: All 113 expected labels present and valid
4. Source references: suspicious provenance (upload_, synthetic doc_) flagged
5. Unanswerable audit: CIKM-PILOT-023 audit logic
6. Reviewer B isolation: Reviewer B template has null judgments and no question_category key
7. No ADJUDICATED_GOLD fabrication
8. Pool sizes match expected
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCAL_ONLY = ROOT / "artifacts" / "validation" / "local_only"
RESEARCH = ROOT / "research" / "s4-b-annotation-integrity"

SYSTEM_LABEL_PATTERNS = re.compile(
    r"\b(bm25|dense|hybrid_rrf|score|rank|system)\b",
    re.IGNORECASE,
)
CATEGORY_PATTERN = re.compile(
    r"\b(multi_hop_prerequisite|unanswerable_out_of_corpus|cross_paper_comparison|"
    r"single_hop_definition|provenance_citation_check)\b",
    re.IGNORECASE,
)

EXPECTED_POOL_SIZES = {
    "CIKM-PILOT-001": 17,
    "CIKM-PILOT-005": 14,
    "CIKM-PILOT-013": 16,
    "CIKM-PILOT-002": 17,
    "CIKM-PILOT-004": 22,
    "CIKM-PILOT-023": 27,
}

# Ground-truth Reviewer A scores for verifying preservation
REVIEWER_A_KNOWN_SCORES = {
    "CIKM-PILOT-001": {"CAND-01": 0, "CAND-11": 2, "CAND-17": 2},
    "CIKM-PILOT-005": {"CAND-03": 2, "CAND-04": 2, "CAND-12": 2},
    "CIKM-PILOT-013": {"CAND-06": 2, "CAND-07": 2, "CAND-09": 2, "CAND-10": 0, "CAND-16": 0},
    "CIKM-PILOT-002": {"CAND-04": 2, "CAND-13": 2},
    "CIKM-PILOT-004": {"CAND-08": 2, "CAND-21": 2},
    "CIKM-PILOT-023": {"CAND-01": 0, "CAND-27": 0},
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def reviewer_b_md() -> str:
    return (LOCAL_ONLY / "s4b_reviewer_b_worksheet.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def reviewer_b_template() -> list[dict]:
    return json.loads((LOCAL_ONLY / "s4b_reviewer_b_template.json").read_text())


@pytest.fixture(scope="module")
def reviewer_a_scored() -> list[dict]:
    return json.loads((LOCAL_ONLY / "s4b_reviewer_a_scored.json").read_text())


@pytest.fixture(scope="module")
def score_audit() -> dict:
    return json.loads((RESEARCH / "reviewer_a_score_audit.json").read_text())


@pytest.fixture(scope="module")
def provenance_audit() -> dict:
    return json.loads((RESEARCH / "provenance_audit.json").read_text())


@pytest.fixture(scope="module")
def unanswerable_audit() -> dict:
    return json.loads((RESEARCH / "unanswerable_corpus_audit.json").read_text())


@pytest.fixture(scope="module")
def category_audit() -> dict:
    return json.loads((RESEARCH / "question_category_audit.json").read_text())


@pytest.fixture(scope="module")
def preservation_manifest() -> dict:
    return json.loads((RESEARCH / "reviewer_a_preservation_manifest.json").read_text())


# ── 1. Leakage Tests ──────────────────────────────────────────────────────────

def test_reviewer_b_md_hides_question_categories(reviewer_b_md: str) -> None:
    """Reviewer B worksheet must not expose question category labels.
    
    Category labels must not appear in section headers or query metadata.
    """
    lines = reviewer_b_md.splitlines()
    first_query_line = next(
        (i for i, l in enumerate(lines) if l.startswith("## CIKM-PILOT-")), 0
    )
    query_section = "\n".join(lines[first_query_line:])
    header_category = re.compile(
        r'^##.*\((multi_hop_prerequisite|unanswerable_out_of_corpus|'
        r'cross_paper_comparison|single_hop_definition|provenance_citation_check)\)',
        re.MULTILINE | re.IGNORECASE,
    )
    matches = header_category.findall(query_section)
    assert not matches, (
        f"Reviewer B worksheet leaks question categories in section headers: {set(matches)}"
    )
    # Also ensure CATEGORY_PATTERN does not appear in query headers/metadata
    for line in query_section.splitlines():
        if line.startswith("## ") or line.startswith("**Question") or line.startswith("**Source"):
            cat_matches = CATEGORY_PATTERN.findall(line)
            assert not cat_matches, f"Category leaked in query header/metadata line: {line}"


def test_reviewer_b_md_hides_retrieval_system_names(reviewer_b_md: str) -> None:
    """Reviewer B worksheet must not expose retrieval system names, ranks, or scores as metadata."""
    forbidden_metadata_patterns = [
        re.compile(r'retrieved_by.*bm25', re.IGNORECASE),
        re.compile(r'retrieved_by.*dense', re.IGNORECASE),
        re.compile(r'retrieved_by.*hybrid_rrf', re.IGNORECASE),
        re.compile(r'System:\s*(bm25|dense|hybrid_rrf)', re.IGNORECASE),
        re.compile(r'Retriever:\s*(bm25|dense|hybrid_rrf)', re.IGNORECASE),
        re.compile(r'- Rank:', re.IGNORECASE),
        re.compile(r'- Score:\s*[0-9]', re.IGNORECASE),
    ]
    for pat in forbidden_metadata_patterns:
        matches = pat.findall(reviewer_b_md)
        assert not matches, (
            f"Reviewer B worksheet leaks retrieval metadata pattern '{pat.pattern}': {matches[:2]}"
        )


def test_reviewer_b_json_has_no_question_category_key(reviewer_b_template: list[dict]) -> None:
    """The question_category field must be absent from Reviewer B JSON template."""
    for rec in reviewer_b_template:
        assert "question_category" not in rec, (
            f"question_category key found in Reviewer B record for {rec['query_id']}"
        )


def test_reviewer_b_md_hides_reviewer_a_scores(reviewer_b_md: str) -> None:
    """Reviewer A's numeric scores must not appear in Reviewer B worksheet."""
    # The worksheet shows "Relevance (`0 / 1 / 2`): ___" — the blank marker, not a number
    # Ensure no "): `2`" or "): `1`" score-fill pattern from Reviewer A
    filled_score_pattern = re.compile(r'Relevance \(`0 / 1 / 2`\): `[012]`')
    matches = filled_score_pattern.findall(reviewer_b_md)
    assert not matches, (
        f"Reviewer B worksheet contains pre-filled scores: {matches[:5]}"
    )


def test_reviewer_b_md_does_not_expose_passage_ids(reviewer_b_md: str) -> None:
    """Passage IDs (doc_id::chunk_id) must not be shown to Reviewer B."""
    # Passage IDs follow pattern like papers/vaswani2017...pdf::chunk_NNN
    passage_id_pattern = re.compile(r'\w[\w/.-]+\.pdf::\w+')
    matches = passage_id_pattern.findall(reviewer_b_md)
    assert not matches, (
        f"Reviewer B worksheet exposes passage IDs: {matches[:3]}"
    )


# ── 2. Score Preservation Tests ───────────────────────────────────────────────

def test_reviewer_a_all_scores_valid(score_audit: dict) -> None:
    """All 113 Reviewer A labels must be 0, 1, or 2."""
    assert score_audit["all_values_valid"] is True
    assert score_audit["invalid_values"] == 0
    assert len(score_audit["extraction_issues"]) == 0


def test_reviewer_a_total_label_count(score_audit: dict) -> None:
    """Exactly 113 labels expected across the 6 queries."""
    assert score_audit["total_labels_extracted"] == 113


def test_reviewer_a_score_values_match_known(reviewer_a_scored: list[dict]) -> None:
    """Spot-check that known Reviewer A scores are faithfully preserved."""
    scored_by_qid = {r["query_id"]: r for r in reviewer_a_scored}
    for qid, cand_scores in REVIEWER_A_KNOWN_SCORES.items():
        rec = scored_by_qid[qid]
        for cand, expected in cand_scores.items():
            actual = rec["passage_relevance_judgments"][cand]
            assert actual == expected, (
                f"Score mismatch for {qid}/{cand}: expected {expected}, got {actual}"
            )


def test_reviewer_a_no_fabricated_gold(reviewer_a_scored: list[dict]) -> None:
    """Reviewer A records must not be marked ADJUDICATED_GOLD."""
    for rec in reviewer_a_scored:
        assert rec["review_status"] != "ADJUDICATED_GOLD", (
            f"{rec['query_id']} is ADJUDICATED_GOLD — this must not be pre-set"
        )


def test_reviewer_a_pending_fields_remain_null(reviewer_a_scored: list[dict]) -> None:
    """answerability, quote/page, prereq fields must be null — human must fill these."""
    for rec in reviewer_a_scored:
        assert rec["answerability_assessment"] is None, (
            f"{rec['query_id']}: answerability_assessment must be null (pending human)"
        )
        assert rec["quote_and_page_verified"] is None
        assert rec["prerequisite_dependency_verified"] is None
        assert rec["requires_multiple_supporting_passages"] is None


# ── 3. Completeness Tests ─────────────────────────────────────────────────────

def test_reviewer_b_template_has_all_six_queries(reviewer_b_template: list[dict]) -> None:
    assert len(reviewer_b_template) == 6
    qids = {r["query_id"] for r in reviewer_b_template}
    assert qids == set(EXPECTED_POOL_SIZES.keys())


def test_reviewer_b_pool_sizes_match_expected(reviewer_b_template: list[dict]) -> None:
    """Reviewer B gets same number of candidates per query as Reviewer A."""
    for rec in reviewer_b_template:
        qid = rec["query_id"]
        actual = len(rec["passage_relevance_judgments"])
        expected = EXPECTED_POOL_SIZES[qid]
        assert actual == expected, (
            f"{qid}: expected {expected} candidates, got {actual}"
        )


def test_reviewer_b_all_judgments_null(reviewer_b_template: list[dict]) -> None:
    """Reviewer B template must start with all null judgments."""
    for rec in reviewer_b_template:
        for cand, val in rec["passage_relevance_judgments"].items():
            assert val is None, (
                f"{rec['query_id']}/{cand} is pre-filled with {val!r} — must be null"
            )


def test_reviewer_a_scored_has_all_six_queries(reviewer_a_scored: list[dict]) -> None:
    assert len(reviewer_a_scored) == 6


def test_reviewer_a_pool_sizes_match_expected(reviewer_a_scored: list[dict]) -> None:
    for rec in reviewer_a_scored:
        qid = rec["query_id"]
        actual = len(rec["passage_relevance_judgments"])
        expected = EXPECTED_POOL_SIZES[qid]
        assert actual == expected, (
            f"{qid}: expected {expected} labels, got {actual}"
        )


# ── 4. Source References / Provenance Tests ───────────────────────────────────

def test_provenance_audit_flags_upload_docs(provenance_audit: dict) -> None:
    """Upload docs that are not in the frozen corpus must be flagged."""
    upload_flag = next(
        (f for f in provenance_audit["flags_for_adjudication"]
         if f["type"] == "UPLOAD_DOCS_IN_POOL"),
        None,
    )
    assert upload_flag is not None, "Upload docs not flagged in provenance audit"
    assert len(upload_flag["affected_passage_ids"]) > 0


def test_provenance_audit_flags_synthetic_docs(provenance_audit: dict) -> None:
    """Synthetic doc_ summary passages must be flagged."""
    synth_flag = next(
        (f for f in provenance_audit["flags_for_adjudication"]
         if f["type"] == "SYNTHETIC_SUMMARY_DOCS_IN_POOL"),
        None,
    )
    assert synth_flag is not None, "Synthetic docs not flagged in provenance audit"
    assert len(synth_flag["affected_passage_ids"]) > 0


def test_provenance_audit_cross_query_reuse_documented(provenance_audit: dict) -> None:
    """Cross-query passage reuse must be documented (not silently used)."""
    # doc_attention_is_all_you_need::doc_attention_is_all_you_need_p3_1 appears in multiple queries
    reuse = provenance_audit["cross_query_passage_reuse"]
    assert len(reuse) > 0, "Cross-query passage reuse should be detected and documented"


# ── 5. Unanswerable Query Audit ───────────────────────────────────────────────

def test_unanswerable_audit_covers_corpus_not_just_pool(unanswerable_audit: dict) -> None:
    """Unanswerable determination must come from full-corpus search, not just pool."""
    assert unanswerable_audit["query_id"] == "CIKM-PILOT-023"
    assert "UNANSWERABLE_OUT_OF_CORPUS_SUPPORTED_BY_CORPUS_SEARCH" in unanswerable_audit["verdict"]
    # Must document uncertainty, not make a blind claim
    assert len(unanswerable_audit["uncertainty"]) > 0


def test_unanswerable_audit_no_deepseek_in_corpus(unanswerable_audit: dict) -> None:
    """DeepSeek-R1 and GRPO must be absent from documented corpus docs."""
    assert unanswerable_audit["deepseek_docs_in_corpus"] == []
    assert unanswerable_audit["grpo_mentions_in_corpus"] == []
    assert unanswerable_audit["deepseek_r1_mentions_in_corpus"] == []


def test_unanswerable_audit_flags_upload_doc_for_manual_verification(
    unanswerable_audit: dict,
) -> None:
    """upload_863f97ee must be flagged for manual content inspection."""
    actions = " ".join(unanswerable_audit["action_required"])
    assert "upload_863f97ee" in actions


def test_unanswerable_audit_explains_all_zero_vs_full_search(unanswerable_audit: dict) -> None:
    """Audit must explain why all-zero pool scores alone don't prove unanswerability."""
    assert "note_on_all_zero_scores" in unanswerable_audit
    assert "27 pooled candidates" in unanswerable_audit["note_on_all_zero_scores"]


# ── 6. Question Category Validity ────────────────────────────────────────────

def test_category_audit_flags_pilot005_as_borderline(category_audit: dict) -> None:
    """PILOT-005 (LoRA) should be flagged as potentially single-hop."""
    q005 = next(
        q for q in category_audit["questions_audited"]
        if q["query_id"] == "CIKM-PILOT-005"
    )
    assert "CATEGORY_OVERSTATED_MAY_BE_SINGLE_HOP" in q005["flags"]


def test_category_audit_does_not_silently_rewrite(category_audit: dict) -> None:
    """Audit must be advisory only — it must not change the actual question set."""
    assert "advisory" in category_audit["summary"]["action"].lower()


def test_category_audit_validates_all_six_queries(category_audit: dict) -> None:
    audited_ids = {q["query_id"] for q in category_audit["questions_audited"]}
    assert audited_ids == set(EXPECTED_POOL_SIZES.keys())


# ── 7. Preservation Manifest ──────────────────────────────────────────────────

def test_preservation_manifest_records_leakage(preservation_manifest: dict) -> None:
    """Manifest must honestly record that Reviewer A saw category labels."""
    leak = preservation_manifest["leakage_disclosure"]
    assert leak["leakage_in_header"] is True
    assert "multi_hop_prerequisite" in leak["leakage_values_seen_by_reviewer_a"]
    assert "unanswerable_out_of_corpus" in leak["leakage_values_seen_by_reviewer_a"]


def test_preservation_manifest_does_not_claim_full_blinding(
    preservation_manifest: dict,
) -> None:
    """Manifest must NOT claim Reviewer A was fully blinded."""
    text = json.dumps(preservation_manifest).lower()
    assert "fully blinded" not in text or "not fully blinded" in text or "not claim" in text


def test_preservation_manifest_has_sha256_hashes(preservation_manifest: dict) -> None:
    for src in preservation_manifest["source_files"]:
        assert "sha256" in src
        # At least the first two files should have real hashes (not "TEMPLATE_BLANK")
        if "worksheet" in src["path"]:
            assert len(src["sha256"]) == 64, f"Invalid SHA256 for {src['path']}"


# ── 8. Reviewer B Does Not Leak Reviewer A's Scores via Mapping ───────────────

def test_reviewer_b_pool_mapping_present_but_scores_null(
    reviewer_b_template: list[dict],
) -> None:
    """Reviewer B has pool_item_to_passage_id for coordinator use,
    but all passage_relevance_judgments must be null."""
    for rec in reviewer_b_template:
        assert "pool_item_to_passage_id" in rec, f"Missing pool_item_to_passage_id in {rec['query_id']}"
        for cand, val in rec["passage_relevance_judgments"].items():
            assert val is None


# ── 9. GraphRAG Fairness Protocol Documented ─────────────────────────────────

def test_graphrag_protocol_exists_and_forbids_silent_irrelevance() -> None:
    protocol = json.loads((RESEARCH / "graphrag_fairness_protocol.json").read_text())
    anti = " ".join(protocol["anti_patterns"])
    assert "unjudged" in anti.lower() or "not infer" in anti.lower()
    assert "relevance-0" in anti.lower() or "relevance 0" in anti.lower()
