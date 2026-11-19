"""Unit tests for S5-v3 Corpus v3 builder: determinism, quality, dedup, provenance, leakage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import fitz
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-benchmark-expansion" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from corpus_v3.builder import LeakageGuardError, build_corpus_v3  # noqa: E402
from corpus_v3.constants import (  # noqa: E402
    DEFAULT_OUTPUT_MANIFEST,
    FLAG_BROKEN_ENCODING,
    FLAG_EMPTY_OR_TOO_SHORT,
    FLAG_HEADER_FOOTER_ONLY,
    FLAG_MATH_EXTRACTION_NOISE,
    FLAG_TOC_OR_INDEX_LIKE,
    FLAG_TRUNCATED_END,
    FLAG_TRUNCATED_START,
    PROVENANCE_MARKDOWN_OA_EXTRACTED,
    PROVENANCE_PDF_EXTRACTED,
    REDIST_LOCAL_RESEARCH_ONLY,
    REDIST_SHARE_ALIKE,
    SPLIT_DEV,
    SPLIT_TEST,
)
from corpus_v3.dedup import (  # noqa: E402
    compute_normalized_sha256,
    detect_duplicates,
)
from corpus_v3.extractors import (  # noqa: E402
    SourceEligibilityError,
    compute_file_sha256,
    validate_source_eligibility,
)
from corpus_v3.leakage import verify_leakage_guard  # noqa: E402
from corpus_v3.models import DuplicatePair, PassageRecord, SourceDocumentSpec  # noqa: E402
from corpus_v3.quality import assess_passage_quality  # noqa: E402

FIXTURE_FONT_SIZE = 11
FIXTURE_TEXT_ORIGIN_X = 72
FIXTURE_TEXT_ORIGIN_Y = 72


def _create_test_pdf(path: Path, page_texts: list[str]) -> str:
    """Create a real multi-page PDF using PyMuPDF and return its SHA-256."""
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text(
            (FIXTURE_TEXT_ORIGIN_X, FIXTURE_TEXT_ORIGIN_Y),
            text,
            fontsize=FIXTURE_FONT_SIZE,
        )
    doc.save(str(path))
    doc.close()
    return compute_file_sha256(path)


def _create_test_markdown(path: Path, text: str) -> str:
    """Create a UTF-8 Markdown source file >= 1024 bytes and return its SHA-256."""
    path.write_text(text, encoding="utf-8")
    return compute_file_sha256(path)


def _make_passage(
    passage_id: str,
    doc_id: str,
    text: str,
    split_assignment: str,
) -> PassageRecord:
    """Helper to construct a minimal PassageRecord for leakage tests."""
    norm_sha = compute_normalized_sha256(text)
    raw_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return PassageRecord(
        passage_id=passage_id,
        source_doc_id=doc_id,
        source_title="Test Source",
        domain="Machine Learning",
        provenance_class=PROVENANCE_PDF_EXTRACTED,
        license_id="CC-BY-4.0",
        redistribution_permission=REDIST_SHARE_ALIKE,
        source_sha256="a" * 64,
        page_start=1,
        page_end=1,
        chunk_index=0,
        section_heading="",
        text=text,
        char_count=len(text),
        token_count=len(text.split()),
        normalized_text_sha256=norm_sha,
        passage_sha256=raw_sha,
        quality_flags=(),
        quality_score=1.0,
        is_usable=True,
        is_exact_duplicate=False,
        canonical_passage_id=passage_id,
        split_assignment=split_assignment,
    )


@pytest.mark.unit
def test_build_determinism_and_page_provenance(tmp_path: Path) -> None:
    """Repeated builds produce byte-identical JSONL/manifest SHA-256 and exact page refs."""
    pdf_path = tmp_path / "sample_oa_paper.pdf"
    p1_text = "Gradient descent minimizes a differentiable loss function iteratively.\n" * 12
    p2_text = "Regularization penalizes model complexity to reduce variance on unseen data.\n" * 12
    pdf_sha = _create_test_pdf(pdf_path, [p1_text, p2_text])

    md_path = tmp_path / "sample_oa_chapter.md"
    md_text = (
        "# Linear Regression\n\n"
        + (
            "Linear regression models a continuous target as a weighted sum of input "
            "features plus an intercept term.\n\n"
        )
        * 15
    )
    md_sha = _create_test_markdown(md_path, md_text)

    specs = [
        SourceDocumentSpec(
            doc_id="test_md_001",
            path=str(md_path),
            title="Test OA Markdown",
            source_format="markdown",
            domain="Machine Learning",
            provenance_class=PROVENANCE_MARKDOWN_OA_EXTRACTED,
            license_id="CC-BY-SA-4.0",
            redistribution_permission=REDIST_SHARE_ALIKE,
            expected_sha256=md_sha,
            source_url="https://example.org/md",
        ),
        SourceDocumentSpec(
            doc_id="test_pdf_002",
            path=str(pdf_path),
            title="Test OA PDF",
            source_format="pdf",
            domain="Mathematics for Machine Learning",
            provenance_class=PROVENANCE_PDF_EXTRACTED,
            license_id="arXiv-perpetual-nonexclusive",
            redistribution_permission=REDIST_LOCAL_RESEARCH_ONLY,
            expected_sha256=pdf_sha,
            source_url="https://example.org/pdf",
        ),
    ]

    out_jsonl_1 = tmp_path / "run1" / "passages.jsonl"
    out_manifest_1 = tmp_path / "run1" / "manifest.json"
    out_jsonl_2 = tmp_path / "run2" / "passages.jsonl"
    out_manifest_2 = tmp_path / "run2" / "manifest.json"

    passages_1, manifest_1 = build_corpus_v3(
        repo_root=tmp_path,
        output_jsonl=out_jsonl_1,
        output_manifest=out_manifest_1,
        sources=specs,
    )
    passages_2, manifest_2 = build_corpus_v3(
        repo_root=tmp_path,
        output_jsonl=out_jsonl_2,
        output_manifest=out_manifest_2,
        sources=specs,
    )

    assert len(passages_1) == len(passages_2)
    assert out_jsonl_1.read_bytes() == out_jsonl_2.read_bytes()
    assert (
        manifest_1["private_corpus_jsonl"]["sha256"]
        == (manifest_2["private_corpus_jsonl"]["sha256"])
    )
    assert manifest_1["contains_raw_passage_text"] is False
    assert "Gradient descent minimizes" not in out_manifest_1.read_text(encoding="utf-8")

    pdf_passages = [p for p in passages_1 if p.source_doc_id == "test_pdf_002"]
    md_passages = [p for p in passages_1 if p.source_doc_id == "test_md_001"]
    assert pdf_passages
    assert md_passages
    assert all(p.provenance_class == PROVENANCE_PDF_EXTRACTED for p in pdf_passages)
    assert all(p.provenance_class == PROVENANCE_MARKDOWN_OA_EXTRACTED for p in md_passages)
    assert all(p.source_sha256 == pdf_sha for p in pdf_passages)
    assert any(p.page_start == 1 for p in pdf_passages)
    assert any(p.page_end == 2 for p in pdf_passages)
    assert all(p.page_start == 1 and p.page_end == 1 for p in md_passages)


@pytest.mark.unit
def test_quality_inspector_flags_truncation_and_malformation() -> None:
    """Quality inspector detects short, broken encoding, headers, TOC, math, truncation."""
    too_short = assess_passage_quality("Short snippet.")
    assert FLAG_EMPTY_OR_TOO_SHORT in too_short.flags
    assert not too_short.is_usable

    broken_enc = assess_passage_quality(
        "This passage contains replacement glyph \ufffd and (cid:42) encoding damage "
        "repeated across enough words to exceed the minimum length threshold easily."
    )
    assert FLAG_BROKEN_ENCODING in broken_enc.flags
    assert not broken_enc.is_usable

    header_only = assess_passage_quality(
        "Chapter 3\nLinear Algebra\nPage 42\nSection 3.1\n42\nLinear Algebra"
    )
    assert FLAG_HEADER_FOOTER_ONLY in header_only.flags
    assert not header_only.is_usable

    toc_like = assess_passage_quality(
        "1.1 Introduction ............ 12\n"
        "1.2 Vectors ................. 18\n"
        "1.3 Matrices ................ 25\n"
        "1.4 Eigenvalues ............. 40\n"
        "2.1 Probability ............. 55\n"
    )
    assert FLAG_TOC_OR_INDEX_LIKE in toc_like.flags

    math_noise = assess_passage_quality(
        "x + y = z * w - u + v / k + m - n + p * q + r - s + t * b + c - d + e * f + g - h."
    )
    assert FLAG_MATH_EXTRACTION_NOISE in math_noise.flags

    truncated = assess_passage_quality(
        "continues from the previous page without a capital letter and then explains "
        "how matrix multiplication composes linear transformations across finite "
        "dimensional vector spaces without ending cleanly"
    )
    assert FLAG_TRUNCATED_START in truncated.flags
    assert FLAG_TRUNCATED_END in truncated.flags


@pytest.mark.unit
def test_exact_and_near_duplicate_detection() -> None:
    """Dedup detects exact normalized SHA-256 duplicates and high-Jaccard near-duplicates."""
    base_text = (
        "Linear regression estimates the conditional expectation of a target variable "
        "given input features by minimizing the sum of squared residuals over training data."
    )
    exact_variant = (
        "  LINEAR regression estimates the conditional expectation of a target variable "
        "given input features by minimizing the sum of squared residuals over training data! "
    )
    near_variant = (
        "Linear regression estimates the conditional expectation of a target variable "
        "given input features by minimizing the sum of squared residuals over validation data."
    )
    distinct_text = (
        "Convolutional neural networks apply shared spatial filters across image tensors "
        "to learn translation equivariant hierarchical feature representations."
    )

    items = [
        ("p_001", base_text, compute_normalized_sha256(base_text)),
        ("p_002", exact_variant, compute_normalized_sha256(exact_variant)),
        ("p_003", near_variant, compute_normalized_sha256(near_variant)),
        ("p_004", distinct_text, compute_normalized_sha256(distinct_text)),
    ]
    report, canonical_map = detect_duplicates(items, near_dup_threshold=0.75)

    assert report.exact_duplicate_count == 1
    assert report.exact_duplicate_pairs[0].passage_id == "p_002"
    assert report.exact_duplicate_pairs[0].matched_passage_id == "p_001"
    assert canonical_map["p_002"] == "p_001"
    assert report.near_duplicate_count == 1
    assert report.near_duplicate_pairs[0].passage_id == "p_003"
    assert report.near_duplicate_pairs[0].matched_passage_id == "p_001"
    assert report.near_duplicate_pairs[0].similarity >= 0.75


@pytest.mark.unit
def test_leakage_guard_catches_cross_split_and_forbidden_overlaps() -> None:
    """Leakage guard fails on exact hash, near-dup, doc straddling, and forbidden hashes."""
    text_a = (
        "Eigenvalues characterize scalar stretching factors of a linear operator "
        "acting along invariant eigenvector subspaces."
    )
    text_b = (
        "Singular value decomposition factors any real or complex matrix into "
        "orthogonal rotations and nonnegative singular scaling values."
    )
    p_dev = _make_passage("p_dev_1", "doc_1", text_a, SPLIT_DEV)
    p_test_same_hash = _make_passage("p_test_1", "doc_2", text_a, SPLIT_TEST)
    p_test_same_doc = _make_passage("p_test_2", "doc_1", text_b, SPLIT_TEST)

    res_hash = verify_leakage_guard([p_dev, p_test_same_hash])
    assert not res_hash.passed
    assert res_hash.cross_split_exact_hash_overlaps == 1

    res_doc = verify_leakage_guard([p_dev, p_test_same_doc])
    assert not res_doc.passed
    assert res_doc.cross_split_doc_overlaps == 1

    p_test_clean = _make_passage("p_test_3", "doc_2", text_b, SPLIT_TEST)
    near_pair = (
        DuplicatePair(
            passage_id="p_test_3",
            matched_passage_id="p_dev_1",
            kind="near",
            similarity=0.88,
        ),
    )
    res_near = verify_leakage_guard([p_dev, p_test_clean], near_duplicate_pairs=near_pair)
    assert not res_near.passed
    assert res_near.cross_split_near_dup_overlaps == 1

    res_forbidden = verify_leakage_guard(
        [p_dev],
        forbidden_hashes=frozenset({p_dev.normalized_text_sha256}),
    )
    assert not res_forbidden.passed
    assert res_forbidden.forbidden_hash_overlaps == 1

    res_clean = verify_leakage_guard([p_dev, p_test_clean])
    assert res_clean.passed


@pytest.mark.unit
def test_exclusion_of_copyrighted_stub_and_tampered_sources(tmp_path: Path) -> None:
    """Eligibility validator rejects copyrighted, ineligible, stub, and tampered files."""
    elsevier_dir = tmp_path / "predictive_analytics_and_data_mining"
    elsevier_dir.mkdir()
    elsevier_file = elsevier_dir / "chapter1.pdf"
    elsevier_file.write_bytes(b"A" * 2048)

    elsevier_spec = SourceDocumentSpec(
        doc_id="bad_elsevier",
        path=str(elsevier_file),
        title="Copyrighted Book",
        source_format="pdf",
        domain="ML",
        provenance_class=PROVENANCE_PDF_EXTRACTED,
        license_id="All Rights Reserved",
        redistribution_permission="forbidden_excluded",
        expected_sha256="",
        source_url="",
        eligible=True,
    )
    with pytest.raises(SourceEligibilityError, match="excluded path rule"):
        validate_source_eligibility(elsevier_spec, tmp_path, verify_sha256=False)

    stub_file = tmp_path / "tiny_stub.pdf"
    stub_file.write_bytes(b"%PDF-1.4 stub")
    stub_spec = SourceDocumentSpec(
        doc_id="bad_stub",
        path=str(stub_file),
        title="Synthetic Stub",
        source_format="pdf",
        domain="ML",
        provenance_class=PROVENANCE_PDF_EXTRACTED,
        license_id="CC-BY-4.0",
        redistribution_permission=REDIST_SHARE_ALIKE,
        expected_sha256="",
        source_url="",
        eligible=True,
    )
    with pytest.raises(SourceEligibilityError, match="synthetic stub"):
        validate_source_eligibility(stub_spec, tmp_path, verify_sha256=False)

    real_md = tmp_path / "valid.md"
    real_md.write_text("# Valid\n\n" + ("Content line.\n" * 100), encoding="utf-8")
    tampered_spec = SourceDocumentSpec(
        doc_id="tampered_md",
        path=str(real_md),
        title="Tampered MD",
        source_format="markdown",
        domain="ML",
        provenance_class=PROVENANCE_MARKDOWN_OA_EXTRACTED,
        license_id="CC-BY-4.0",
        redistribution_permission=REDIST_SHARE_ALIKE,
        expected_sha256="0" * 64,
        source_url="",
        eligible=True,
    )
    with pytest.raises(SourceEligibilityError, match="SHA-256 mismatch"):
        validate_source_eligibility(tampered_spec, tmp_path, verify_sha256=True)

    ineligible_spec = SourceDocumentSpec(
        doc_id="ineligible_doc",
        path=str(real_md),
        title="Excluded",
        source_format="markdown",
        domain="ML",
        provenance_class=PROVENANCE_MARKDOWN_OA_EXTRACTED,
        license_id="Proprietary",
        redistribution_permission="forbidden_excluded",
        expected_sha256="",
        source_url="",
        eligible=False,
        exclusion_reason="copyrighted",
    )
    with pytest.raises(SourceEligibilityError, match="copyrighted"):
        validate_source_eligibility(ineligible_spec, tmp_path, verify_sha256=False)


@pytest.mark.unit
def test_builder_raises_on_forbidden_hash_leakage(tmp_path: Path) -> None:
    """build_corpus_v3 raises LeakageGuardError if a passage hits a forbidden hash."""
    md_path = tmp_path / "oa_doc.md"
    md_text = (
        "# Optimization\n\n"
        + (
            "Stochastic gradient descent updates parameters using mini-batch "
            "gradient estimates to scale optimization to large datasets.\n\n"
        )
        * 12
    )
    md_sha = _create_test_markdown(md_path, md_text)
    spec = SourceDocumentSpec(
        doc_id="leak_doc",
        path=str(md_path),
        title="Optimization OA",
        source_format="markdown",
        domain="Machine Learning",
        provenance_class=PROVENANCE_MARKDOWN_OA_EXTRACTED,
        license_id="CC-BY-4.0",
        redistribution_permission=REDIST_SHARE_ALIKE,
        expected_sha256=md_sha,
        source_url="https://example.org/opt",
    )
    passages, _manifest = build_corpus_v3(
        repo_root=tmp_path,
        output_jsonl=tmp_path / "ok.jsonl",
        output_manifest=tmp_path / "ok_manifest.json",
        sources=[spec],
    )
    assert passages
    forbidden = frozenset({passages[0].normalized_text_sha256})
    with pytest.raises(LeakageGuardError):
        build_corpus_v3(
            repo_root=tmp_path,
            output_jsonl=tmp_path / "fail.jsonl",
            output_manifest=tmp_path / "fail_manifest.json",
            sources=[spec],
            forbidden_hashes=forbidden,
        )


@pytest.mark.unit
def test_built_corpus_v3_manifest_integrity() -> None:
    """Public S5-v3 corpus manifest exists, is metadata-only, and passes leakage guard."""
    manifest_path = REPO_ROOT / DEFAULT_OUTPUT_MANIFEST
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["contains_raw_passage_text"] is False
    assert manifest["deterministic"] is True
    assert manifest["frozen_v2_1_corpus_status"] == "MISSING_NOT_REPAIRED_OR_FAKED"
    assert manifest["summary"]["source_document_count"] == 4
    assert manifest["summary"]["total_passages"] > 0
    assert manifest["leakage_guard"]["passed"] is True
    assert (
        manifest["multi_domain_coverage_gap"]["sufficient_for_full_cs_multidomain_claims"] is False
    )
    assert len(manifest["multi_domain_coverage_gap"]["missing_domains"]) >= 4
