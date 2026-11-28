"""Unit tests for D14 Reader & Provenance Contract.

Covers:
1. Unified 4-state source provenance contract across backend & API responses:
   ``verified_full_text_passage``, ``metadata_only_record``,
   ``institutional_licensed``, ``unavailable_document``.
2. Page-bounds validation and printed-page-to-PDF-page mapping so
   ``/read?doc=...&page=...`` never points to invalid pages or ``/chat``.
3. All 68 ``corpus_v3_d14`` open-access sources resolve to valid, license-compliant
   reader or canonical external OA URLs.
4. All 12 excluded commercial holdings are strictly non-clickable
   ``metadata_only_record`` entries under SIGIR ``open_access_only=true``.
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys
from typing import Any

from flask import Flask
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "host_inference") not in sys.path:
    sys.path.append(str(ROOT / "host_inference"))

from engine.access_profile import (  # noqa: E402
    ACCESS_PROFILE_ENV,
    ACCESS_PROFILE_INSTITUTIONAL,
    ACCESS_PROFILE_OPEN_ACCESS,
    d14_canonical_oa_url,
    is_d14_approved_oa,
    is_d14_excluded_commercial,
    is_pearson_url,
    load_d14_source_registry,
)
from engine.citation_format import (  # noqa: E402
    SOURCE_KIND_INSTITUTIONAL,
    SOURCE_KIND_METADATA_ONLY,
    SOURCE_KIND_UNAVAILABLE,
    SOURCE_KIND_VERIFIED_FULL_TEXT,
    citation_link,
    classify_source_kind,
    sanitize_citation_record,
    sanitize_citations,
)
from engine.citations import assign_canonical_citations  # noqa: E402
from engine.evidence_export import build_evidence_export  # noqa: E402
from engine.links import source_links  # noqa: E402
from engine.provenance import (  # noqa: E402
    ALL_SOURCE_KINDS,
    EVIDENCE_STATE_METADATA_ONLY,
    EVIDENCE_STATE_UNAVAILABLE,
    build_grounding_trace,
    printed_to_pdf_page,
    resolve_page_provenance,
    summarize_evidence_states,
    verify_chunk_provenance,
)
from hostapp.routes import library as library_routes  # noqa: E402
from hostapp.routes import reader as reader_routes  # noqa: E402

pytestmark = pytest.mark.unit

INVENTORY_CSV = ROOT / "docs" / "reports" / "d14" / "D14_SOURCE_INVENTORY.csv"
LICENSE_CSV = ROOT / "docs" / "reports" / "d14" / "D14_SOURCE_LICENSE_REGISTER.csv"
EXPECTED_OA_COUNT = 68
EXPECTED_EXCLUDED_COUNT = 12


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class _DummyAuth:
    def principal(self) -> tuple[None, str]:
        return None, "unauthenticated"


class _DummyCtx:
    auth = _DummyAuth()
    inventory = None


def _make_reader_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    reader_routes.register(app, _DummyCtx())  # type: ignore[arg-type]
    library_routes.register(app, _DummyCtx())  # type: ignore[arg-type]
    return app


def test_d14_inventory_and_license_register_counts() -> None:
    """Verify D14 registry loads all 68 approved OA sources and 12 excluded holdings."""
    inv_rows = _load_csv_rows(INVENTORY_CSV)
    lic_rows = _load_csv_rows(LICENSE_CSV)
    assert len(inv_rows) == len(lic_rows)

    registry = load_d14_source_registry()
    oa_entries = [e for e in registry.values() if e["is_approved_oa"]]
    excluded_entries = [e for e in registry.values() if e["is_excluded_commercial"]]

    assert len(oa_entries) == EXPECTED_OA_COUNT
    assert len(excluded_entries) == EXPECTED_EXCLUDED_COUNT
    for entry in oa_entries:
        assert is_d14_approved_oa(entry["doc_id"])
        assert not is_d14_excluded_commercial(entry["doc_id"])
        assert d14_canonical_oa_url(entry["doc_id"]).startswith("https://")
    for entry in excluded_entries:
        assert is_d14_excluded_commercial(entry["doc_id"])
        assert not is_d14_approved_oa(entry["doc_id"])
        assert d14_canonical_oa_url(entry["doc_id"]) == ""


def test_four_state_source_provenance_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enforce the unified 4-state contract across sanitizer, citations, and trace."""
    expected_kinds = {
        SOURCE_KIND_VERIFIED_FULL_TEXT,
        SOURCE_KIND_METADATA_ONLY,
        SOURCE_KIND_INSTITUTIONAL,
        SOURCE_KIND_UNAVAILABLE,
    }
    assert expected_kinds == ALL_SOURCE_KINDS
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_INSTITUTIONAL)

    verified = sanitize_citation_record(
        {
            "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            "page_number": 3,
            "chunk_id": "chunk_007",
            "url": "/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=3",
            "text_passage": "Scaled dot-product attention computes softmax(QK^T / sqrt(d_k))V.",
        },
        open_access_only=False,
    )
    assert verified["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT
    assert verified["clickable"] is True
    assert verified["url"].startswith("/read?doc=")

    metadata = sanitize_citation_record(
        {
            "source_id": "excluded_clrs_algorithms",
            "doc_id": "metadata_only/clrs_algorithms",
            "title": "Introduction to Algorithms (CLRS 4e)",
            "url": "/read?doc=metadata_only/clrs_algorithms&page=1",
        },
        open_access_only=False,
    )
    assert metadata["source_kind"] == SOURCE_KIND_METADATA_ONLY
    assert metadata["clickable"] is False
    assert metadata["url"] == ""

    institutional = sanitize_citation_record(
        {
            "doc_id": "pearson-book-uuid",
            "title": "Computer Networks (Pearson)",
            "is_pearson": True,
            "source_category": "pearson_catalogue_only",
            "url": "/open/pearson-book-uuid?page=10",
        },
        open_access_only=False,
    )
    assert institutional["source_kind"] == SOURCE_KIND_INSTITUTIONAL
    assert institutional["clickable"] is True
    assert institutional["url"] == "/open/pearson-book-uuid"

    unavailable = sanitize_citation_record(
        {
            "doc_id": "papers/NonExistentDocument_2099.pdf",
            "page_number": 5,
            "url": "/chat",
        },
        open_access_only=False,
    )
    assert unavailable["source_kind"] == SOURCE_KIND_UNAVAILABLE
    assert unavailable["clickable"] is False
    assert unavailable["url"] == ""
    assert unavailable["evidence_state"] == EVIDENCE_STATE_UNAVAILABLE

    canonical = assign_canonical_citations([verified, metadata, institutional, unavailable])
    assert {c["source_kind"] for c in canonical} == ALL_SOURCE_KINDS
    summary = summarize_evidence_states(canonical)
    assert summary["turn_source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT
    assert summary["source_kind_counts"][SOURCE_KIND_VERIFIED_FULL_TEXT] == 1
    assert summary["source_kind_counts"][SOURCE_KIND_METADATA_ONLY] == 1

    trace = build_grounding_trace(
        route="CONCEPT_EXPLANATION",
        anchor_id="self_attention",
        anchor_label="Self-Attention",
        hops=1,
        citations=canonical,
        provider="deterministic",
        latency_s=0.1,
        latency_ms=100,
    )
    assert trace["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT
    bundle = build_evidence_export("Explain attention", "Attention maps Q, K, V.", {"citations": canonical, "trace": trace})
    assert bundle["evidence_summary"]["turn_source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT


def test_printed_page_mapping_and_page_bounds_validation() -> None:
    """Validate printed-page-to-PDF mapping and rejection of out-of-bounds or /chat URLs."""
    deisenroth = "books/textbooks/Deisenroth_Math_For_ML.pdf"
    assert printed_to_pdf_page(deisenroth, 1) == 17
    assert printed_to_pdf_page(deisenroth, 10) == 26
    assert printed_to_pdf_page(deisenroth, 9999) is None
    assert printed_to_pdf_page(deisenroth, 0) is None

    prov = resolve_page_provenance(deisenroth, None, printed_page=10)
    assert prov["pdf_page"] == 26
    assert prov["printed_page"] == 10
    assert prov["pages_differ"] is True
    assert prov["page_in_bounds"] is True
    assert prov["page_display"] == "PDF p. 26 (printed p. 10)"

    oob_prov = resolve_page_provenance(deisenroth, 9999)
    assert oob_prov["page_in_bounds"] is False

    # Out-of-bounds page in /read URL must be stripped, never left as &page=9999.
    sanitized_oob = sanitize_citation_record(
        {
            "doc_id": deisenroth,
            "page_number": 9999,
            "url": f"/read?doc={deisenroth}&page=9999",
            "text_passage": "Matrix decomposition overview.",
        },
        open_access_only=True,
    )
    assert sanitized_oob["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT
    assert "page=9999" not in sanitized_oob["url"]
    assert sanitized_oob["page_verified"] is False
    assert sanitized_oob["page_number"] is None

    # Printed page with missing PDF page maps cleanly to PDF page 26.
    sanitized_printed = sanitize_citation_record(
        {
            "doc_id": deisenroth,
            "printed_page": 10,
            "url": f"/read?doc={deisenroth}",
            "text_passage": "Linear algebra vector spaces.",
        },
        open_access_only=True,
    )
    assert sanitized_printed["pdf_page"] == 26
    assert sanitized_printed["printed_page"] == 10
    assert "&page=26" in sanitized_printed["url"]

    # /chat URL is never emitted as clickable.
    chat_rec = sanitize_citation_record(
        {"doc_id": "papers/Unknown.pdf", "url": "/chat?q=foo"},
        open_access_only=True,
    )
    assert chat_rec["clickable"] is False
    assert chat_rec["url"] == ""
    assert not chat_rec["url"].startswith("/chat")


def test_all_68_d14_oa_sources_have_valid_license_compliant_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every one of the 68 approved corpus_v3_d14 OA sources must produce a valid OA URL."""
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)
    registry = load_d14_source_registry()
    oa_entries = [e for e in registry.values() if e["is_approved_oa"]]
    assert len(oa_entries) == EXPECTED_OA_COUNT

    for entry in oa_entries:
        rec = {
            "source_id": entry["source_id"],
            "doc_id": entry["doc_id"],
            "title": entry["title"],
            "page_number": 1,
            "text_passage": "Verified open-access passage.",
            "url": (
                f"/read?doc={entry['doc_id']}&page=1"
                if entry["origin"] == "baseline_v2_hf_cache"
                else entry["canonical_url"]
            ),
        }
        sanitized = sanitize_citation_record(rec, open_access_only=True)
        assert sanitized["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT, entry["source_id"]
        assert sanitized["clickable"] is True, entry["source_id"]
        assert sanitized["reader_resolvable"] is True, entry["source_id"]
        url = sanitized["url"]
        assert url, f"Empty URL for {entry['source_id']}"
        assert not url.startswith("/chat"), f"/chat URL for {entry['source_id']}"
        assert not is_pearson_url(url), f"Pearson URL leaked for {entry['source_id']}"
        if entry["origin"] == "d14_oa_acquisition":
            assert url.startswith("https://"), f"Expected canonical external OA HTTPS URL for {entry['source_id']}"
        else:
            assert url.startswith("/read?doc="), f"Expected /read URL for baseline HF PDF {entry['source_id']}"


def test_all_12_excluded_commercial_holdings_strictly_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All 12 excluded commercial holdings must be non-clickable metadata_only_record."""
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)
    registry = load_d14_source_registry()
    excluded_entries = [e for e in registry.values() if e["is_excluded_commercial"]]
    assert len(excluded_entries) == EXPECTED_EXCLUDED_COUNT

    raw_records: list[dict[str, Any]] = []
    for entry in excluded_entries:
        raw = {
            "source_id": entry["source_id"],
            "doc_id": entry["doc_id"],
            "title": entry["title"],
            "label": f"[S1: {entry['title']}]",
            "url": f"/open/{entry['source_id']}",
            "pdf_url": f"/read?doc={entry['doc_id']}&page=1",
            "page_number": 5,
        }
        raw_records.append(raw)
        assert classify_source_kind(raw, open_access_only=True) == SOURCE_KIND_METADATA_ONLY
        sanitized = sanitize_citation_record(raw, open_access_only=True)
        assert sanitized["source_kind"] == SOURCE_KIND_METADATA_ONLY
        assert sanitized["evidence_state"] == EVIDENCE_STATE_METADATA_ONLY
        assert sanitized["clickable"] is False
        assert sanitized["reader_resolvable"] is False
        assert sanitized["url"] == ""
        assert sanitized["pdf_url"] == ""
        assert source_links(sanitized, None) == ""
        assert citation_link(raw) == raw["label"]
        prov = verify_chunk_provenance(
            raw_doc_id=entry["doc_id"],
            canonical_doc_id=entry["doc_id"],
            chunk_id="chunk_001",
            page_number=1,
            hf_url="",
            text_passage="",
            all_withdrawn=False,
        )
        assert prov["source_kind"] == SOURCE_KIND_METADATA_ONLY

    batch = sanitize_citations(raw_records, open_access_only=True)
    assert len(batch) == EXPECTED_EXCLUDED_COUNT
    assert all(
        c["source_kind"] == SOURCE_KIND_METADATA_ONLY and not c["clickable"] and c["url"] == ""
        for c in batch
    )
    canonical = assign_canonical_citations(raw_records)
    assert all(
        c["source_kind"] == SOURCE_KIND_METADATA_ONLY and not c["clickable"] and "url" not in c
        for c in canonical
    )


def test_reader_and_catalog_routes_enforce_d14_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify /api/page-view, /api/reader/info, and /api/catalog/all under open_access."""
    monkeypatch.setenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_OPEN_ACCESS)
    monkeypatch.setattr(library_routes, "load_hf_paths", lambda: [])
    monkeypatch.setattr(library_routes, "load_books", lambda: [])
    monkeypatch.setattr(reader_routes, "load_books", lambda: [])
    monkeypatch.setattr(reader_routes, "resolve_hf_path", lambda p: p if p.endswith(".pdf") and "Deisenroth" in p else None)

    client = _make_reader_app().test_client()

    # 1. Printed page -> PDF page mapping + page bounds on Deisenroth.
    resp_printed = client.get(
        "/api/page-view?doc_id=books/textbooks/Deisenroth_Math_For_ML.pdf&printed_page=10&format=json"
    )
    assert resp_printed.status_code == 200
    data_printed = resp_printed.get_json()
    assert data_printed["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT
    assert data_printed["pdf_page"] == 26
    assert data_printed["printed_page"] == 10
    assert data_printed["page_valid"] is True
    assert not data_printed["url"].startswith("/chat")

    resp_oob = client.get(
        "/api/page-view?doc_id=books/textbooks/Deisenroth_Math_For_ML.pdf&page=9999&format=json"
    )
    assert resp_oob.status_code == 200
    data_oob = resp_oob.get_json()
    assert data_oob["page_valid"] is False
    assert data_oob["page"] == 417

    # 2. All 27 d14_oa/* sources (PDF, HTML, TXT) resolve via /api/page-view and /api/reader/info.
    registry = load_d14_source_registry()
    d14_new = [e for e in registry.values() if e["is_approved_oa"] and e["origin"] == "d14_oa_acquisition"]
    assert len(d14_new) == 27
    for entry in d14_new:
        resp = client.get(f"/api/page-view?doc_id={entry['doc_id']}&page=1&format=json")
        assert resp.status_code == 200, entry["source_id"]
        payload = resp.get_json()
        assert payload["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT
        assert payload["url"].startswith("https://")
        assert payload["clickable"] is True

    # 3. All 12 excluded commercial holdings return 404 metadata_only_record on reader APIs.
    excluded = [e for e in registry.values() if e["is_excluded_commercial"]]
    for entry in excluded:
        resp = client.get(f"/api/page-view?doc_id={entry['doc_id']}&format=json")
        assert resp.status_code == 404, entry["source_id"]
        payload = resp.get_json()
        assert payload["source_kind"] == SOURCE_KIND_METADATA_ONLY
        assert payload["clickable"] is False
        assert payload["url"] == ""

    # 4. /api/catalog/all under open_access_only=true exposes 68 clickable OA + 12 non-clickable metadata-only.
    cat_resp = client.get("/api/catalog/all")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.get_json()
    assert cat_data["open_access_only"] is True
    oa_docs = [d for d in cat_data["documents"] if d["source_kind"] == SOURCE_KIND_VERIFIED_FULL_TEXT]
    meta_docs = [d for d in cat_data["documents"] if d["source_kind"] == SOURCE_KIND_METADATA_ONLY]
    assert len(oa_docs) == EXPECTED_OA_COUNT
    assert len(meta_docs) == EXPECTED_EXCLUDED_COUNT
    assert all(d["clickable"] is True and d["open_url"] and not is_pearson_url(d["open_url"]) for d in oa_docs)
    assert all(d["clickable"] is False and d["open_url"] == "" for d in meta_docs)
