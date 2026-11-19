"""Unit tests for S5-v3.1 Corpus v3.1 expansion (Stages A & B)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import zipfile

import fitz
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-1-oa-corpus-expansion" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from corpus_v31.builder import build_corpus_v31  # noqa: E402
from corpus_v31.constants import (  # noqa: E402
    DEFAULT_V31_CORPUS_MANIFEST,
    DEFAULT_V31_LICENSE_MANIFEST,
    PRIOR_V3_EXPECTED_ELIGIBLE_COUNT,
    PROVENANCE_EPUB_OA_EXTRACTED,
    PROVENANCE_HTML_OA_EXTRACTED,
    PROVENANCE_LATEX_OA_EXTRACTED,
    PROVENANCE_PDF_EXTRACTED,
)
from corpus_v31.extractors import (  # noqa: E402
    ForbiddenSourceError,
    check_not_forbidden,
    compute_directory_sha256,
    compute_file_sha256,
)
from corpus_v31.models import SourceLicenseRecord  # noqa: E402
from corpus_v31.quality_dedup import (  # noqa: E402
    classify_chunk_rejection,
    compute_normalized_sha256,
    compute_passage_sha256,
)

PDF_FONT_SIZE = 11
PDF_TEXT_X = 72
PDF_TEXT_Y = 72


def _write_fake_prior_v3_jsonl(path: Path) -> None:
    """Create a small synthetic prior v3 JSONL with 1 usable and 1 unusable record."""
    usable_text = (
        "Linear regression estimates a continuous target variable by minimizing "
        "squared residuals across observed feature vectors in a training dataset."
    )
    unusable_text = "Short stub."
    rows = [
        {
            "passage_id": "s5v3_local_oa_001_p0001_c0000",
            "source_doc_id": "local_oa_001",
            "source_title": "D2L Ch.3",
            "domain": "Machine Learning",
            "provenance_class": "markdown_oa_extracted",
            "license_id": "CC-BY-SA-4.0",
            "redistribution_permission": "share_alike_with_attribution",
            "source_sha256": "a" * 64,
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 0,
            "section_heading": "Linear Regression",
            "text": usable_text,
            "char_count": len(usable_text),
            "token_count": len(usable_text.split()),
            "normalized_text_sha256": compute_normalized_sha256(usable_text),
            "passage_sha256": compute_passage_sha256(usable_text),
            "quality_flags": [],
            "quality_score": 1.0,
            "is_usable": True,
            "is_exact_duplicate": False,
            "canonical_passage_id": "s5v3_local_oa_001_p0001_c0000",
            "split_assignment": "corpus_shared",
        },
        {
            "passage_id": "s5v3_local_oa_003_p0001_c0000",
            "source_doc_id": "local_oa_003",
            "source_title": "MML",
            "domain": "Mathematics for Machine Learning",
            "provenance_class": "pdf_extracted",
            "license_id": "Free PDF",
            "redistribution_permission": "local_research_only_no_republishing",
            "source_sha256": "b" * 64,
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 0,
            "section_heading": "",
            "text": unusable_text,
            "char_count": len(unusable_text),
            "token_count": 2,
            "normalized_text_sha256": compute_normalized_sha256(unusable_text),
            "passage_sha256": compute_passage_sha256(unusable_text),
            "quality_flags": ["EMPTY_OR_TOO_SHORT"],
            "quality_score": 0.55,
            "is_usable": False,
            "is_exact_duplicate": False,
            "canonical_passage_id": "s5v3_local_oa_003_p0001_c0000",
            "split_assignment": "corpus_shared",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n",
        encoding="utf-8",
    )


def _create_fixture_sources(tmp_path: Path) -> list[SourceLicenseRecord]:
    """Create minimal EPUB, HTML, PDF, and LaTeX OA fixture sources."""
    epub_path = tmp_path / "os.epub"
    xhtml = (
        "<html><body><h1>Processes</h1>"
        "<p>An operating system manages process scheduling, virtual memory, and "
        "kernel isolation so multiple programs share hardware resources safely and "
        "efficiently across concurrent workloads while enforcing protection domains "
        "and deterministic context switches between user space and kernel space.</p>"
        "</body></html>"
    )
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("OEBPS/text/ch1.xhtml", xhtml)

    html_dir = tmp_path / "db_html"
    html_dir.mkdir()
    (html_dir / "ch01.html").write_text(
        "<html><body><h1>Normalization</h1><section class='mt-content-container'>"
        "<h2>Third Normal Form</h2><p>Database normalization decomposes relational "
        "tables to eliminate update anomalies and transitive functional dependencies "
        "while preserving lossless join properties and dependency preservation across "
        "structured relational schemas in enterprise database systems.</p>"
        "</section></body></html>",
        encoding="utf-8",
    )

    pdf_path = tmp_path / "net.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(PDF_TEXT_X, PDF_TEXT_Y, 520, 400),
        "TCP congestion control adjusts the sender congestion window using slow "
        "start, additive increase, and multiplicative decrease to prevent network "
        "collapse across shared bottleneck links while maintaining fair bandwidth "
        "allocation among competing transport flows.",
        fontsize=PDF_FONT_SIZE,
    )
    doc.save(str(pdf_path))
    doc.close()

    tex_path = tmp_path / "ds.tex"
    tex_path.write_text(
        "\\section{Consensus}\n"
        "Distributed consensus algorithms such as Raft and Paxos allow replicated "
        "state machines to agree on a total order of log entries despite crash "
        "faults and asynchronous network message delays.\n",
        encoding="utf-8",
    )

    return [
        SourceLicenseRecord(
            doc_id="oa_os_001",
            domain="Operating Systems",
            title="Test OS",
            authors="Test Authors",
            publisher="Test Pub",
            version_or_commit="v1",
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            license_exceptions="None",
            redistribution_permission="open_attribution_required",
            official_url="https://example.org/os",
            download_url="https://example.org/os.epub",
            download_timestamp_utc="2026-11-19T00:00:00Z",
            local_raw_path=str(epub_path),
            source_sha256=compute_file_sha256(epub_path),
            source_format="epub",
            provenance_class=PROVENANCE_EPUB_OA_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status="RETRIEVED_VERIFIED",
        ),
        SourceLicenseRecord(
            doc_id="oa_db_001",
            domain="Databases",
            title="Test DB",
            authors="Test Authors",
            publisher="Test Pub",
            version_or_commit="v2",
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            license_exceptions="None",
            redistribution_permission="open_attribution_required",
            official_url="https://example.org/db",
            download_url="https://example.org/db",
            download_timestamp_utc="2026-11-19T00:00:00Z",
            local_raw_path=str(html_dir),
            source_sha256=compute_directory_sha256(html_dir, "ch*.html"),
            source_format="html_chapters",
            provenance_class=PROVENANCE_HTML_OA_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status="RETRIEVED_VERIFIED",
        ),
        SourceLicenseRecord(
            doc_id="oa_net_001",
            domain="Computer Networks",
            title="Test Net",
            authors="Test Authors",
            publisher="Test Pub",
            version_or_commit="v3",
            license_id="CC-BY-SA-3.0",
            license_url="https://creativecommons.org/licenses/by-sa/3.0/",
            license_exceptions="None",
            redistribution_permission="share_alike_with_attribution",
            official_url="https://example.org/net",
            download_url="https://example.org/net.pdf",
            download_timestamp_utc="2026-11-19T00:00:00Z",
            local_raw_path=str(pdf_path),
            source_sha256=compute_file_sha256(pdf_path),
            source_format="pdf",
            provenance_class=PROVENANCE_PDF_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status="RETRIEVED_VERIFIED",
        ),
        SourceLicenseRecord(
            doc_id="oa_ds_001",
            domain="Distributed Systems",
            title="Test DS",
            authors="Test Authors",
            publisher="Test Pub",
            version_or_commit="v4",
            license_id="CC-BY-SA-4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_exceptions="None",
            redistribution_permission="share_alike_with_attribution",
            official_url="https://example.org/ds",
            download_url="https://example.org/ds.tex",
            download_timestamp_utc="2026-11-19T00:00:00Z",
            local_raw_path=str(tex_path),
            source_sha256=compute_file_sha256(tex_path),
            source_format="latex",
            provenance_class=PROVENANCE_LATEX_OA_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status="RETRIEVED_VERIFIED",
        ),
    ]


@pytest.mark.unit
def test_v31_build_determinism_honest_pages_and_no_raw_text_in_manifests(
    tmp_path: Path,
) -> None:
    """Repeated builds are byte-identical, never fabricate pages, and keep manifests metadata-only."""
    prior_jsonl = tmp_path / "prior_v3.jsonl"
    _write_fake_prior_v3_jsonl(prior_jsonl)
    sources = _create_fixture_sources(tmp_path)

    p1, cm1, _lm1 = build_corpus_v31(
        repo_root=tmp_path,
        output_jsonl=tmp_path / "r1" / "corpus.jsonl",
        output_corpus_manifest=tmp_path / "r1" / "corpus_manifest.json",
        output_license_manifest=tmp_path / "r1" / "license_manifest.json",
        prior_v3_jsonl=prior_jsonl,
        new_sources=sources,
        verify_prior_sha256=False,
    )
    p2, cm2, _lm2 = build_corpus_v31(
        repo_root=tmp_path,
        output_jsonl=tmp_path / "r2" / "corpus.jsonl",
        output_corpus_manifest=tmp_path / "r2" / "corpus_manifest.json",
        output_license_manifest=tmp_path / "r2" / "license_manifest.json",
        prior_v3_jsonl=prior_jsonl,
        new_sources=sources,
        verify_prior_sha256=False,
    )

    assert len(p1) == 5
    assert len(p1) == len(p2)
    assert (tmp_path / "r1" / "corpus.jsonl").read_bytes() == (
        tmp_path / "r2" / "corpus.jsonl"
    ).read_bytes()
    assert cm1["private_corpus_jsonl"]["sha256"] == cm2["private_corpus_jsonl"]["sha256"]
    assert cm1["contains_raw_passage_text"] is False
    assert cm1["okf_graph_db_dependency"] is False

    manifest_text = (tmp_path / "r1" / "corpus_manifest.json").read_text(encoding="utf-8")
    assert "TCP congestion control" not in manifest_text

    by_doc = {p.source_doc_id: p for p in p1}
    assert by_doc["oa_net_001"].page_start == 1
    assert by_doc["oa_os_001"].page_start is None
    assert by_doc["oa_db_001"].page_start is None
    assert by_doc["oa_ds_001"].page_start is None


@pytest.mark.unit
def test_forbidden_source_guard_blocks_mixu_and_okf_db() -> None:
    """Forbidden source guard strictly blocks mixu/distsysbook and okf_graph.db."""
    with pytest.raises(ForbiddenSourceError):
        check_not_forbidden("https://github.com/mixu/distsysbook")
    with pytest.raises(ForbiddenSourceError):
        check_not_forbidden("/home/user/archipelago/okf_graph.db")
    with pytest.raises(ForbiddenSourceError):
        check_not_forbidden("predictive_analytics_and_data_mining/ch1.pdf")


@pytest.mark.unit
def test_boilerplate_bibliography_and_malformed_rejection() -> None:
    """Quality filter rejects navigation boilerplate, bibliography-only, and malformed chunks."""
    assert classify_chunk_rejection("Bibliography", "A long bibliography section.") == (
        "boilerplate_or_bib"
    )
    assert (
        classify_chunk_rejection(
            "Chapter 1",
            "Skip to main content. Previous chapter. Next chapter. Back to top.",
        )
        == "boilerplate_or_bib"
    )
    bib_block = "\n".join(
        [
            "[RFC793] Postel, J., Transmission Control Protocol, 1981, pp. 1-85.",
            "[RFC791] Postel, J., Internet Protocol, 1981, pp. 1-45.",
            "[RFC2460] Deering, S., IPv6 Specification, 1998, pp. 1-39.",
            "[RFC2616] Fielding, R., HTTP/1.1, IEEE/ACM 1999, pp. 1-176.",
            "[RFC4271] Rekhter, Y., BGP-4, 2006, pp. 1-104.",
        ]
    )
    assert classify_chunk_rejection("Page 270", bib_block) == "boilerplate_or_bib"
    assert classify_chunk_rejection("Ch 1", "Broken \ufffd encoding text.") == (
        "malformed_or_short"
    )


@pytest.mark.unit
def test_built_corpus_v31_manifests_exist_and_are_valid() -> None:
    """Public Corpus v3.1 manifests exist, cover all 8 domains, and contain zero raw text."""
    corpus_manifest_path = REPO_ROOT / DEFAULT_V31_CORPUS_MANIFEST
    license_manifest_path = REPO_ROOT / DEFAULT_V31_LICENSE_MANIFEST
    assert corpus_manifest_path.is_file()
    assert license_manifest_path.is_file()

    cm = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    lm = json.loads(license_manifest_path.read_text(encoding="utf-8"))

    assert cm["contains_raw_passage_text"] is False
    assert lm["contains_raw_passage_text"] is False
    assert cm["okf_graph_db_dependency"] is False
    assert cm["summary"]["retained_v3_passages"] == PRIOR_V3_EXPECTED_ELIGIBLE_COUNT
    assert cm["summary"]["domain_count"] == 8
    assert cm["summary"]["source_document_count"] == 8
    assert cm["summary"]["total_passages"] > PRIOR_V3_EXPECTED_ELIGIBLE_COUNT

    for domain in (
        "Operating Systems",
        "Databases",
        "Computer Networks",
        "Distributed Systems",
    ):
        assert cm["summary"]["domain_passage_counts"][domain] > 0

    raw_lm_text = license_manifest_path.read_text(encoding="utf-8")
    assert "mixu/distsysbook (strictly excluded" in raw_lm_text
    assert hashlib.sha256(corpus_manifest_path.read_bytes()).hexdigest()
