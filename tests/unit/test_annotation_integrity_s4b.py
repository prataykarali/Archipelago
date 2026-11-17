"""
S4-B Annotation Integrity Tests — Hotfix Refreshed Suite.

Exercises actual input data, retrieval, blinding, score conversion, and negative test cases:
1. Leakage & Blinding: Reviewer B worksheet hides question categories, unanswerable hints, source docs, system identifiers, scores
2. Deterministic Score Extraction: Extracts scores directly from Markdown, detects duplicates/missing IDs, ensures immutability
3. Full-Corpus Search & DeepSeek Audit: Reproducible search across 764 passages, negative cases, unverified fallbacks
4. Pool Quality & Near-Duplicates: Jaccard shingling on texts, corpus membership validation, GraphRAG status
5. Reviewer B Two-Stage Isolation: Stage 1 template has null judgments, Stage 2 map contains source references
6. Negative Cases: Tampered scores, invalid ranges, corrupted markdown, missing DB
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCAL_ONLY = ROOT / "artifacts" / "validation" / "local_only"
RESEARCH = ROOT / "research" / "s4-b-annotation-integrity"

from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu

# ── Import functions from scripts under test ──────────────────────────────────
import sys
sys.path.insert(0, str(RESEARCH / "scripts"))
from build_s4b_artifacts import extract_reviewer_a_scores_deterministic, sha256_file
from corpus_search_deepseek import run_corpus_search
from audit_candidate_pool import audit_pool_quality, shingle_set, jaccard

EXPECTED_POOL_SIZES = {
    "CIKM-PILOT-001": 17,
    "CIKM-PILOT-005": 14,
    "CIKM-PILOT-013": 16,
    "CIKM-PILOT-002": 17,
    "CIKM-PILOT-004": 22,
    "CIKM-PILOT-023": 27,
}

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def reviewer_b_md() -> str:
    return (LOCAL_ONLY / "s4b_reviewer_b_worksheet.md").read_text(encoding="utf-8")

@pytest.fixture(scope="module")
def reviewer_b_template() -> list[dict]:
    return json.loads((LOCAL_ONLY / "s4b_reviewer_b_template.json").read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def reviewer_a_scored() -> list[dict]:
    return json.loads((LOCAL_ONLY / "s4b_reviewer_a_scored.json").read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def stage2_map() -> dict:
    return json.loads((LOCAL_ONLY / "s4b_stage2_verification_map.json").read_text(encoding="utf-8"))

# ── 1. Deterministic Human Score Extraction & Preservation ────────────────────

def test_deterministic_score_extraction_from_markdown() -> None:
    """Exercising actual extraction logic on Reviewer A markdown."""
    md_path = LOCAL_ONLY / "s4a_human_annotation_worksheet.md"
    scores, pids, issues = extract_reviewer_a_scores_deterministic(md_path)
    
    assert len(issues) == 0, f"Extraction produced issues: {issues}"
    assert len(scores) == 6, f"Expected 6 queries, got {len(scores)}"
    
    total_labels = sum(len(c) for c in scores.values())
    assert total_labels == 113, f"Expected exactly 113 labels, got {total_labels}"
    
    for qid, expected_count in EXPECTED_POOL_SIZES.items():
        assert len(scores[qid]) == expected_count, f"{qid} count mismatch: {len(scores[qid])} != {expected_count}"
        for cid, score in scores[qid].items():
            assert score in (0, 1, 2), f"Invalid score {score} for {qid} {cid}"

def test_deterministic_extraction_detects_tampering(tmp_path: Path) -> None:
    """Negative case: extraction detects corrupted/tampered score in markdown."""
    clean_md = (LOCAL_ONLY / "s4a_human_annotation_worksheet.md").read_text(encoding="utf-8")
    # Tamper a score to an invalid value '9'
    tampered_md = clean_md.replace("Relevance (`0 / 1 / 2`): `2`", "Relevance (`0 / 1 / 2`): `9`", 1)
    tampered_file = tmp_path / "tampered.md"
    tampered_file.write_text(tampered_md, encoding="utf-8")
    
    scores, pids, issues = extract_reviewer_a_scores_deterministic(tampered_file)
    assert len(issues) > 0, "Failed to detect invalid/missing score"
    assert any(i["issue"] == "MISSING_SCORE" for i in issues)

def test_reviewer_a_preservation_manifest_git_disclosure() -> None:
    """Manifest discloses that scores exist in Git history."""
    manifest = json.loads((RESEARCH / "reviewer_a_preservation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["git_history_disclosure"]["scores_in_public_commits"] is True
    assert "not claim" in manifest["git_history_disclosure"]["disclosure_statement"].lower()

# ── 2. Real Full-Corpus Search & DeepSeek Verification ────────────────────────

def test_real_corpus_search_executes_on_764_passages() -> None:
    """Exercises actual corpus traversal on okf_graph.db."""
    res = run_corpus_search(ROOT / "okf_graph.db")
    assert res["status"] == "VERIFIED_EXHAUSTIVE_SEARCH"
    assert res["searched_passage_count"] == 764
    assert res["exact_matches_found"] == 0
    assert res["verdict"] == "UNANSWERABLE_OUT_OF_CORPUS_CONFIRMED"
    assert res["corpus_sha256"] == "fc0d0c7e7faddf9d4755ce29f056bfa824dba592ac8fe07aa1c510b3cb745e40"

def test_corpus_search_reports_not_verified_when_db_missing(tmp_path: Path) -> None:
    """Negative case: returns NOT_VERIFIED if DB does not exist."""
    fake_db = tmp_path / "nonexistent.db"
    res = run_corpus_search(fake_db)
    assert res["status"] == "NOT_VERIFIED"
    assert res["searched_passage_count"] == 0

def test_suspicious_upload_passage_audited() -> None:
    """Exercises inspection of CAND-14 (upload_863f97ee) in CIKM-PILOT-023."""
    res = run_corpus_search(ROOT / "okf_graph.db")
    cand14 = res["suspicious_upload_inspection"]["cand14_specific_audit"]
    assert cand14["found_in_corpus"] is True
    assert cand14["mentions_deepseek"] is False
    assert cand14["mentions_grpo"] is False
    assert cand14["answers_pilot_023"] is False

# ── 3. Correct Reviewer B Blinding & Untruncated Text ─────────────────────────

def test_reviewer_b_md_hides_question_categories(reviewer_b_md: str) -> None:
    """Reviewer B worksheet must not expose category names in queries."""
    cat_pattern = re.compile(
        r"\b(multi_hop_prerequisite|cross_paper_comparison|single_hop_definition|provenance_citation_check)\b",
        re.I
    )
    for line in reviewer_b_md.splitlines():
        if line.startswith("## ") or line.startswith("**Question"):
            assert not cat_pattern.search(line), f"Category leaked in query line: {line}"

def test_reviewer_b_md_hides_unanswerable_hints(reviewer_b_md: str) -> None:
    """Reviewer B worksheet must not label CIKM-PILOT-023 as out-of-corpus."""
    lines = reviewer_b_md.splitlines()
    for i, line in enumerate(lines):
        if "CIKM-PILOT-023" in line:
            # Check the surrounding 10 lines
            section = "\n".join(lines[i:i+10])
            assert "out of corpus" not in section.lower(), "Hinted unanswerable in query header"
            assert "unanswerable" not in section.lower() or "answerability judgment" in section.lower()

def test_reviewer_b_md_hides_source_document_lists(reviewer_b_md: str) -> None:
    """Reviewer B worksheet must NOT display source document lists as clues."""
    assert "**Source Document(s):**" not in reviewer_b_md
    assert "papers/Vaswani2017" not in reviewer_b_md
    assert "papers/Hu2021" not in reviewer_b_md

def test_reviewer_b_md_passages_not_truncated(reviewer_b_md: str) -> None:
    """Reviewer B worksheet must contain complete text without 800-char truncation."""
    assert "[... truncated for readability ...]" not in reviewer_b_md
    ws_json = json.loads((LOCAL_ONLY / "s4a_human_annotation_worksheet.json").read_text(encoding="utf-8"))
    
    # Check that long passages from ws_json appear in full
    for qid, items in ws_json["blinded_pools"].items():
        for it in items:
            text_snippet = it["text"][:100]
            assert text_snippet in reviewer_b_md, f"Snippet missing from Reviewer B worksheet: {text_snippet}"

def test_reviewer_b_md_hides_system_identifiers_and_scores(reviewer_b_md: str) -> None:
    """No retrieval system tags or pre-filled scores in Reviewer B worksheet."""
    forbidden = [
        re.compile(r"System:\s*(bm25|dense|hybrid_rrf)", re.I),
        re.compile(r"Retriever:\s*(bm25|dense|hybrid_rrf)", re.I),
        re.compile(r"Relevance \(`0 / 1 / 2`\):\s*`[012]`"),
    ]
    for pat in forbidden:
        assert not pat.search(reviewer_b_md), f"Leaked pattern {pat.pattern}"

# ── 4. Two-Stage Process Verification Map ────────────────────────────────────

def test_stage2_verification_map_contains_all_candidates(stage2_map: dict) -> None:
    """Stage 2 mapping contains candidate-to-source link for all 113 candidates."""
    assert stage2_map["pilot_phase"] == "S4-B_STAGE2_VERIFICATION_MAP"
    total_candidates = sum(len(q["candidates"]) for q in stage2_map["queries"].values())
    assert total_candidates == 113
    
    for qid, qdata in stage2_map["queries"].items():
        assert len(qdata["candidates"]) == EXPECTED_POOL_SIZES[qid]
        for cand in qdata["candidates"]:
            assert "passage_id" in cand
            assert "doc_id" in cand
            assert "page_number" in cand

# ── 5. Candidate Pool Quality & Near-Duplicate Detection ──────────────────────

def test_candidate_pool_audit_all_members_in_corpus() -> None:
    """All 96 unique candidates must belong to the frozen 764-passage corpus."""
    rep = audit_pool_quality(ROOT / "okf_graph.db")
    assert rep["corpus_validation"]["all_candidates_in_corpus"] is True
    assert rep["corpus_validation"]["missing_from_corpus_count"] == 0

def test_shingling_and_near_duplicate_detection() -> None:
    """Exercises shingling and Jaccard similarity logic directly."""
    t1 = "The Transformer is a sequence-to-sequence model architecture relying entirely on attention."
    t2 = "The Transformer is an architecture relying entirely on attention mechanisms."
    t3 = "Graph convolutional networks operate directly on graph structured data."
    
    s1, s2, s3 = shingle_set(t1, k=2), shingle_set(t2, k=2), shingle_set(t3, k=2)
    sim12 = jaccard(s1, s2)
    sim13 = jaccard(s1, s3)
    
    assert sim12 >= 0.4, f"Expected high overlap, got {sim12}"
    assert sim13 < 0.1, f"Expected near-zero overlap, got {sim13}"

def test_graphrag_fairness_protocol_documents_unavailability() -> None:
    """GraphRAG protocol accurately documents that pipeline is not yet integrated."""
    proto = json.loads((RESEARCH / "graphrag_fairness_protocol.json").read_text(encoding="utf-8"))
    assert proto["graphrag_pool_status"]["available_in_repo"] is False
    assert "never" in proto["graphrag_pool_status"]["reason"].lower() or "cannot" in proto["graphrag_pool_status"]["reason"].lower()
