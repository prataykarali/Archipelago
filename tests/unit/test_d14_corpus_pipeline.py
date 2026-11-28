"""Unit tests for Archipelago D14.1 corpus reconstruction pipeline (corpus_v3_d14).

Verifies:
- License gating (blocks commercial textbooks & metadata-only catalog cards; allows OA).
- Extraction quality, structural classification (TOC/References/Index/FrontMatter filtering),
  and normalized deduplication.
- Physical PDF page vs printed page mapping and offset calculation.
- 12-domain coverage matrix calculation and versioned manifest emission without
  mutating the frozen corpus_v2_d10_3025 baseline.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import fitz
import pytest

from archipelago.corpus.catalog import (
    CANONICAL_DOMAINS,
    CORPUS_VERSION_V3,
    LicenseStatus,
    SourceFormat,
    SourceSpec,
    build_default_source_catalog,
)
from archipelago.corpus.enricher import ConceptMatcher, LexicalIndexAccumulator, build_jsonl_record
from archipelago.corpus.extractors import (
    compute_page_offset,
    extract_html_units,
    extract_pdf_units,
    extract_text_rfc_units,
    sha256_file,
)
from archipelago.corpus.license_gate import authorize_source, verify_license_register
from archipelago.corpus.pipeline import PipelineConfig, run_pipeline
from archipelago.corpus.segmenter import (
    StructuralClass,
    classify_structure,
    compute_quality_score,
    segment_units,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FROZEN_V2_MANIFEST = REPO_ROOT / "docs" / "reports" / "D10_S4_CANDIDATE_PASSAGE_MANIFEST.json"
EXPECTED_DOMAIN_COUNT = 12


@pytest.mark.unit
def test_license_gate_blocks_commercial_and_catalog_cards() -> None:
    """Prohibited commercial textbooks and metadata-only cards must be rejected."""
    clrs = SourceSpec(
        source_id="bad_clrs",
        doc_id="books/clrs.pdf",
        title="Introduction to Algorithms (CLRS 4e)",
        authors="Cormen, Leiserson, Rivest & Stein",
        domain="Data Structures & Algorithms",
        secondary_domains=(),
        source_format=SourceFormat.PDF,
        license_name="CC-BY-4.0",  # even if mislabeled, title/author deny-list must block
        license_status=LicenseStatus.APPROVED_OA,
        license_url="https://creativecommons.org/licenses/by/4.0/",
        canonical_url="https://example.org/clrs.pdf",
        origin="d14_oa_acquisition",
        independent_group="clrs",
    )
    decision_clrs = authorize_source(clrs)
    assert not decision_clrs.allowed
    assert "prohibited_commercial_work" in decision_clrs.reason

    tanenbaum = SourceSpec(
        source_id="bad_tanenbaum",
        doc_id="metadata_only/tanenbaum",
        title="Computer Networks (6e)",
        authors="Andrew S. Tanenbaum",
        domain="Computer Networks",
        secondary_domains=(),
        source_format=SourceFormat.CATALOG_CARD,
        license_name="All Rights Reserved",
        license_status=LicenseStatus.PROHIBITED_COMMERCIAL,
        license_url="",
        canonical_url="",
        origin="excluded_commercial",
        independent_group="tanenbaum",
    )
    decision_tan = authorize_source(tanenbaum)
    assert not decision_tan.allowed
    assert decision_tan.license_status == LicenseStatus.METADATA_ONLY


@pytest.mark.unit
def test_license_gate_approves_verified_oa_catalog() -> None:
    """Every non-excluded source in the default catalog passes the license gate."""
    catalog = build_default_source_catalog()
    approved, decisions = verify_license_register(catalog)
    expected_oa = [s for s in catalog if s.origin != "excluded_commercial"]
    expected_excluded = [s for s in catalog if s.origin == "excluded_commercial"]

    assert len(approved) == len(expected_oa)
    assert len(decisions) == len(catalog)
    assert len(expected_excluded) >= EXPECTED_DOMAIN_COUNT

    # Verify all 12 canonical domains have >=2 independent OA source groups in catalog.
    for domain in CANONICAL_DOMAINS:
        groups = {s.independent_group for s in approved if s.domain == domain}
        assert len(groups) >= 2, f"Domain {domain} has fewer than 2 independent OA sources"


@pytest.mark.unit
def test_structural_classifier_filters_toc_references_index_and_tiny_chunks() -> None:
    """TOC, References, Index, and low-quality stubs must not be classified as BODY."""
    toc_text = (
        "Table of Contents\n"
        "1. Introduction .......................... 1\n"
        "2. Paging ................................ 15\n"
        "3. Virtual Memory ........................ 32\n"
    )
    assert classify_structure(toc_text) == StructuralClass.TOC

    refs_text = (
        "References\n"
        "[1] Vaswani et al. (2017). Attention Is All You Need.\n"
        "[2] Devlin et al. (2018). BERT: Pre-training of Deep Bidirectional Transformers.\n"
        "[3] Lewis et al. (2020). Retrieval-Augmented Generation.\n"
        "[4] Hu et al. (2021). LoRA: Low-Rank Adaptation.\n"
    )
    assert classify_structure(refs_text) == StructuralClass.REFERENCES

    index_text = (
        "Index\n"
        "Address space, 12, 45-48\n"
        "B+ tree, 102, 114\n"
        "Cache coherence, 210-215\n"
        "Deadlock, 88, 91\n"
    )
    assert classify_structure(index_text) == StructuralClass.INDEX

    assert classify_structure("tiny stub") == StructuralClass.LOW_QUALITY
    assert compute_quality_score("tiny stub") < 0.50

    body_text = (
        "Paging divides a process address space into fixed-sized units called pages, "
        "while physical memory is divided into an array of fixed-sized slots called page frames. "
        "To translate a virtual address into a physical address, the operating system maintains "
        "a per-process page table that maps each virtual page number to its corresponding "
        "physical frame number and protection bits."
    )
    assert classify_structure(body_text) == StructuralClass.BODY
    assert compute_quality_score(body_text) >= 0.70


@pytest.mark.unit
def test_pdf_physical_vs_printed_page_mapping_and_dedup(tmp_path: Path) -> None:
    """Physical PDF pages map cleanly to printed page labels and offsets."""
    pdf_path = tmp_path / "sample_textbook.pdf"
    body_para = (
        "Chapter 4: Virtual Memory and Paging\n"
        "Virtual memory separates the logical memory seen by a process from\n"
        "physical RAM. A page table stores translations from virtual page\n"
        "numbers to physical frame numbers, enabling isolation and demand\n"
        "paging across concurrent processes in modern operating system kernels.\n"
        "Translation Lookaside Buffers cache recent virtual-to-physical\n"
        "mappings in hardware to accelerate memory access latency."
    )
    with fitz.open() as doc:
        # Page 1 (physical index 0): Roman numeral front matter "i"
        p0 = doc.new_page()
        p0.insert_text(
            (72, 72), "Preface\nAll rights reserved. ISBN 0-000-00000-0\nCopyright © 2026"
        )
        p0.insert_text((72, 750), "i")
        # Page 2 (physical index 1): Printed page "1" (offset = 2 - 1 = 1)
        p1 = doc.new_page()
        p1.insert_text((72, 72), f"{body_para}\n1")
        # Page 3 (physical index 2): Duplicate body text on printed page "2"
        p2 = doc.new_page()
        p2.insert_text((72, 72), f"{body_para}\n2")
        doc.save(pdf_path)

    units = extract_pdf_units(pdf_path)
    assert len(units) == 3
    assert units[1].page_number == 2
    assert units[1].pdf_page_index == 1
    assert units[1].printed_page == "1"
    assert units[1].page_offset == 1
    assert compute_page_offset(2, "1") == 1
    assert compute_page_offset(1, "i") is None

    passages, stats = segment_units(
        units,
        doc_id="d14_oa/os/sample_textbook.pdf",
        source_id="sample_tb",
        file_sha256=sha256_file(pdf_path),
    )
    assert stats.kept_passages == 1
    assert stats.filtered_duplicates == 1
    assert passages[0].printed_page == "1"
    assert passages[0].page_offset == 1


@pytest.mark.unit
def test_html_and_rfc_extractors_and_pipeline_end_to_end(tmp_path: Path) -> None:
    """Mini end-to-end pipeline emits all 5 artifacts without touching baseline v2."""
    html_file = tmp_path / "db_doc.html"
    html_file.write_text(
        "<html><head><title>DB Internals</title></head><body>"
        "<nav>Navigation links</nav>"
        "<main><h2>B-Tree Indexing</h2>"
        "<p>A B+ tree maintains balanced search paths from root to leaf pages so that "
        "range queries and point lookups execute in logarithmic disk I/O operations. "
        "Write-ahead logging guarantees atomicity and durability across crash recovery "
        "by recording redo and undo log records before modifying heap pages on disk.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )
    rfc_file = tmp_path / "rfc_sample.txt"
    rfc_file.write_text(
        "RFC 9999                        TCP Sample                      Nov 2026\n\n"
        "1. Congestion Control\n"
        "TCP congestion control uses slow start, congestion avoidance, fast retransmit, "
        "and fast recovery to adapt the sender congestion window to network bandwidth "
        "and packet loss signals without overwhelming intermediate routers.\n"
        "Eddy                         Standards Track                    [Page 4]\n\x0c",
        encoding="utf-8",
    )

    html_units = extract_html_units([html_file])
    assert len(html_units) == 1
    assert html_units[0].section_title == "B-Tree Indexing"

    rfc_units = extract_text_rfc_units(rfc_file)
    assert len(rfc_units) == 1
    assert rfc_units[0].printed_page == "4"

    # Verify ConceptMatcher and LexicalIndexAccumulator work on extracted passages.
    graph_file = tmp_path / "okf_graph.json"
    graph_file.write_text(
        json.dumps({"nodes": [{"id": "b_plus_tree", "label": "B+ Tree"}]}),
        encoding="utf-8",
    )
    matcher = ConceptMatcher.from_graph_path(graph_file)
    passages, _ = segment_units(
        html_units,
        doc_id="d14_oa/db/db_doc.html",
        source_id="db_doc",
        file_sha256=sha256_file(html_file),
    )
    concepts = matcher.match_concepts(passages[0].text)
    assert "b_plus_tree" in concepts

    acc = LexicalIndexAccumulator()
    acc.add(passages[0].text, concepts)
    summary = acc.summary()
    assert summary["lexical_index"]["indexed_passages"] == 1
    assert summary["lexical_index"]["concept_linked_passages"] == 1

    # Run mini pipeline offline using pre-cached local files.
    out_dir = tmp_path / "out"
    reports_dir = tmp_path / "reports"
    raw_dir = out_dir / "raw" / "db_doc"
    raw_dir.mkdir(parents=True)
    (raw_dir / "db_doc_part00.html").write_text(
        html_file.read_text(encoding="utf-8"), encoding="utf-8"
    )

    mini_spec = SourceSpec(
        source_id="db_doc",
        doc_id="d14_oa/database_systems/db_doc.html",
        title="DB Internals Sample",
        authors="Open Author",
        domain="Database Systems",
        secondary_domains=(),
        source_format=SourceFormat.HTML,
        license_name="CC-BY-4.0",
        license_status=LicenseStatus.APPROVED_OA,
        license_url="https://creativecommons.org/licenses/by/4.0/",
        canonical_url="https://example.org/db_doc.html",
        origin="d14_oa_acquisition",
        independent_group="db_sample",
    )
    record = build_jsonl_record(passages[0], mini_spec, concepts, CORPUS_VERSION_V3)
    assert record["corpus_version"] == CORPUS_VERSION_V3
    assert record["domain"] == "Database Systems"

    manifest = run_pipeline(
        PipelineConfig(
            repo_root=REPO_ROOT,
            output_dir=out_dir,
            reports_dir=reports_dir,
            graph_path=graph_file,
            allow_network=False,
        ),
        specs=[mini_spec],
    )
    assert manifest["corpus_version"] == CORPUS_VERSION_V3
    assert manifest["totals"]["total_passages"] == 1
    assert (reports_dir / "D14_SOURCE_INVENTORY.csv").is_file()
    assert (reports_dir / "D14_SOURCE_LICENSE_REGISTER.csv").is_file()
    assert (reports_dir / "D14_CORPUS_COVERAGE_MATRIX.csv").is_file()
    assert (reports_dir / "D14_INGESTION_REPORT.md").is_file()
    assert (reports_dir / "D14_CORPUS_MANIFEST.json").is_file()
    assert (reports_dir / "D14_CORPUS_V3_MANIFEST.json").is_file()

    with (reports_dir / "D14_CORPUS_COVERAGE_MATRIX.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == EXPECTED_DOMAIN_COUNT


@pytest.mark.unit
def test_frozen_baseline_v2_manifest_remains_untouched() -> None:
    """Verify corpus_v2_d10_3025 baseline manifest is intact and unchanged."""
    assert FROZEN_V2_MANIFEST.is_file()
    payload = json.loads(FROZEN_V2_MANIFEST.read_text(encoding="utf-8"))
    assert payload["document_count"] == 43
    assert payload["passage_count"] == 3025
    assert (
        payload["passage_index_sha256"]
        == "93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52"
    )


@pytest.mark.unit
def test_committed_d14_reports_and_12_domain_coverage_matrix() -> None:
    """Verify all committed D14.1 reports and 12-domain coverage invariants."""
    reports_dir = REPO_ROOT / "docs" / "reports" / "d14"
    manifest_path = reports_dir / "D14_CORPUS_MANIFEST.json"
    v3_alias_path = reports_dir / "D14_CORPUS_V3_MANIFEST.json"
    matrix_path = reports_dir / "D14_CORPUS_COVERAGE_MATRIX.csv"
    license_path = reports_dir / "D14_SOURCE_LICENSE_REGISTER.csv"
    inventory_path = reports_dir / "D14_SOURCE_INVENTORY.csv"
    report_md = reports_dir / "D14_INGESTION_REPORT.md"

    for artifact in (
        manifest_path,
        v3_alias_path,
        matrix_path,
        license_path,
        inventory_path,
        report_md,
    ):
        assert artifact.is_file(), f"Missing D14.1 deliverable: {artifact}"

    assert manifest_path.read_text(encoding="utf-8") == v3_alias_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["corpus_version"] == CORPUS_VERSION_V3
    assert manifest["totals"]["domains_covered"] == EXPECTED_DOMAIN_COUNT
    assert manifest["totals"]["domains_meeting_target"] == EXPECTED_DOMAIN_COUNT
    assert manifest["totals"]["excluded_commercial_sources"] >= EXPECTED_DOMAIN_COUNT

    with matrix_path.open(encoding="utf-8") as handle:
        matrix_rows = list(csv.DictReader(handle))
    assert len(matrix_rows) == EXPECTED_DOMAIN_COUNT
    for row in matrix_rows:
        assert int(row["d14_v3_fulltext_passages"]) > 0
        assert int(row["d14_v3_independent_sources"]) >= 2
        assert row["meets_2_source_target"] == "true"

    with license_path.open(encoding="utf-8") as handle:
        lic_rows = list(csv.DictReader(handle))
    blocked_rows = [r for r in lic_rows if r["gate_allowed"] == "false"]
    assert len(blocked_rows) >= EXPECTED_DOMAIN_COUNT
    for row in lic_rows:
        if row["gate_allowed"] == "true":
            assert row["license_status"] == LicenseStatus.APPROVED_OA.value
