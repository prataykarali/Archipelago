"""Unit tests for D14.9 B1 end-to-end citation provenance and C4 rights isolation."""

from __future__ import annotations

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "host_inference") not in sys.path:
    sys.path.append(str(_REPO / "host_inference"))

from engine.access_profile import is_unauthorized_stub  # noqa: E402
from engine.citation_format import (  # noqa: E402
    SOURCE_KIND_METADATA_ONLY,
    SOURCE_KIND_UNAVAILABLE,
    SOURCE_KIND_VERIFIED_FULL_TEXT,
    sanitize_citation_record,
    sanitize_citations,
)
from engine.citations import assign_canonical_citations  # noqa: E402
from engine.evidence_selection import _build_catalog_citation  # noqa: E402
from engine.provenance import (  # noqa: E402
    CLAIM_SUPPORT_NOT_ASSESSED,
    EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
    EVIDENCE_STATE_METADATA_ONLY,
    verify_chunk_provenance,
)
from engine.source_resolution import resolve_source_target  # noqa: E402


def test_d14_oa_source_resolution_populates_external_and_reader_urls() -> None:
    resolved = resolve_source_target(
        raw_doc_id="d14_oa/dsa/erickson_algorithms.pdf",
        canonical_doc_id="d14_oa/dsa/erickson_algorithms.pdf",
        page_number=45,
        title="Algorithms",
    )
    assert resolved["reader_resolvable"] is True
    assert resolved["external_url"].startswith("https://jeffe.cs.illinois.edu/")
    assert "#page=45" in resolved["external_url"]
    assert resolved["reader_url"] == resolved["external_url"]


def test_d14_catalog_citation_preserves_canonical_passage_id_and_urls() -> None:
    entry = {
        "doc_id": "d14_oa/computer_networks/rfc5681_tcp_congestion.txt",
        "passage_id": "d14:abc123def456:p12:c1",
        "source_title": "RFC 5681: TCP Congestion Control",
        "page_number": 12,
        "printed_page": "12",
        "text": "Fast retransmit and fast recovery algorithms reduce congestion window.",
        "domain": "Computer Networks",
        "corpus_version": "corpus_v3_d14",
    }
    raw_cite = _build_catalog_citation(entry, "fast_recovery", 1, None)
    assert raw_cite["canonical_passage_id"] == "d14_oa/computer_networks/rfc5681_tcp_congestion.txt::d14:abc123def456:p12:c1"
    assert raw_cite["external_url"] == "https://www.rfc-editor.org/rfc/rfc5681.txt"
    assert raw_cite["reader_url"] == "https://www.rfc-editor.org/rfc/rfc5681.txt"
    assert raw_cite["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED

    sanitized = assign_canonical_citations(sanitize_citations([raw_cite], open_access_only=True))
    assert len(sanitized) == 1
    c0 = sanitized[0]
    assert c0["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT
    assert c0["evidence_state"] == EVIDENCE_STATE_AVAILABLE_FULL_TEXT
    assert c0["clickable"] is True
    assert c0["external_url"] == "https://www.rfc-editor.org/rfc/rfc5681.txt"
    assert c0["reader_url"] == "https://www.rfc-editor.org/rfc/rfc5681.txt"
    assert c0["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED


def test_legacy_and_commercial_stubs_rejected_under_oa_mode() -> None:
    for stub in (
        "pilot/silberschatz_3nf_card.txt",
        "doc_computer_networks_6_e",
        "doc_introduction_to_the_design_and",
        "textbooks/computer_networks_tanenbaum.pdf",
    ):
        assert is_unauthorized_stub(stub) is True
        rec = sanitize_citation_record({"doc_id": stub, "page_number": 5}, open_access_only=True)
        expected_kind = SOURCE_KIND_UNAVAILABLE if stub.endswith(".pdf") else SOURCE_KIND_METADATA_ONLY
        assert rec["source_kind"] == expected_kind
        assert rec["clickable"] is False
        assert rec["external_url"] == ""
        assert rec["reader_url"] == ""

    sanitized_stubs = sanitize_citations(
        [{"doc_id": "pilot/silberschatz_3nf_card.txt"}, {"doc_id": "doc_computer_networks_6_e"}],
        open_access_only=True,
    )
    assert all(
        c["source_kind"] == SOURCE_KIND_METADATA_ONLY and not c["clickable"] and c["external_url"] == ""
        for c in sanitized_stubs
    )


def test_metadata_only_never_promoted_to_directly_supported() -> None:
    prov = verify_chunk_provenance(
        raw_doc_id="textbooks/database_management_systems_ramakrishnan.pdf",
        canonical_doc_id="textbooks/database_management_systems_ramakrishnan.pdf",
        chunk_id="chunk_1",
        page_number=10,
        hf_url="",
        text_passage="3NF eliminates transitive dependencies.",
        all_withdrawn=False,
        source_category="missing_or_unsupported_source",
        reader_resolvable=False,
    )
    assert prov["evidence_state"] == EVIDENCE_STATE_METADATA_ONLY
    assert prov["claim_support_status"] == CLAIM_SUPPORT_NOT_ASSESSED
