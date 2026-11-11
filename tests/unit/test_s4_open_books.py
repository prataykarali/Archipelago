"""DOAB/OAPEN resolution must verify identity and per-file rights before any ingestion."""

from __future__ import annotations

from hashlib import md5
from pathlib import Path

import pytest

from archipelago.academic_automation import open_books
from archipelago.academic_automation.store import AcademicStore

pytestmark = pytest.mark.unit

PDF = b"%PDF-1.4\n" + b"open textbook body " * 40
PDF_MD5 = md5(PDF).hexdigest()


def _record(handle: int, *, title: str, isbn: str, rights_uri: str, rights: str, kind: str = "book", pdf: bool = True) -> str:
    stream = (
        f'<element name="bundles"><element name="bundle"><field name="name">ORIGINAL</field>'
        f'<element name="bitstreams"><element name="bitstream">'
        f'<field name="format">application/pdf</field><field name="size">{len(PDF)}</field>'
        f'<field name="url">https://library.oapen.org/bitstream/20.500.12657/{handle}/1/book.pdf</field>'
        f'<field name="checksum">{PDF_MD5}</field><field name="checksumAlgorithm">MD5</field>'
        f'<field name="rightsuri">{rights_uri}</field><field name="rights">{rights}</field>'
        "</element></element></element></element>"
        if pdf
        else ""
    )
    return (
        "<record><header><identifier>oai:library.oapen.org:20.500.12657/%d</identifier>"
        "<datestamp>2026-01-01T00:00:00Z</datestamp></header><metadata>"
        '<metadata xmlns="http://www.lyncode.com/xoai">'
        '<element name="dc"><element name="title"><element name="none"><field name="value">%s</field></element></element>'
        '<element name="type"><element name="none"><field name="value">%s</field></element></element>'
        '<element name="contributor"><element name="author"><element name="none"><field name="value">Knuth, Donald</field></element></element></element>'
        '<element name="identifier"><element name="uri"><element name="none"><field name="value">https://library.oapen.org/handle/20.500.12657/%d</field></element></element></element>'
        "</element>"
        '<element name="oapen"><element name="relation"><element name="isbn"><element name="none"><field name="value">%s</field></element></element>'
        '<element name="hasChapter"><element name="none"><field name="value">Chapter 1 Sorting</field></element></element></element></element>'
        "%s</metadata></metadata></record>"
    ) % (handle, title, kind, handle, isbn, stream)


def _page(*records: str, token: str = "") -> bytes:
    node = f"<resumptionToken>{token}</resumptionToken>" if token else ""
    return (
        '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>'
        + "".join(records)
        + node
        + "</ListRecords></OAI-PMH>"
    ).encode()


CC_BY = "https://creativecommons.org/licenses/by/4.0/"
CC_NC_ND = "https://creativecommons.org/licenses/by-nc-nd/4.0/"


@pytest.fixture()
def store(tmp_path: Path) -> AcademicStore:
    return AcademicStore(tmp_path / "state.sqlite3")


def _index(store: AcademicStore, *records: str) -> None:
    open_books.harvest(store, "oapen", max_pages=1, fetch=lambda *_: _page(*records), pause=0)


def test_license_mapping_blocks_noncommercial_and_noderivative() -> None:
    assert open_books.license_from_uri(CC_BY) == "CC-BY-4.0"
    assert open_books.license_from_uri("https://creativecommons.org/licenses/by-sa/4.0") == "CC-BY-SA-4.0"
    assert open_books.license_from_uri("https://creativecommons.org/publicdomain/zero/1.0/") == "CC0-1.0"
    assert open_books.license_from_uri(CC_NC_ND) == ""
    assert open_books.license_from_uri("All rights reserved") == ""


def test_exact_isbn_and_title_enable_extraction_only_with_file_license(store: AcademicStore) -> None:
    _index(
        store,
        _record(1, title="Algorithms Open Textbook", isbn="9781234567897", rights_uri=CC_BY, rights="CC-BY"),
        _record(2, title="Restricted Networks Handbook", isbn="9780000000002", rights_uri=CC_NC_ND, rights="CC-BY-NC-ND"),
    )
    hit = open_books.find_open_book(store, "opac_live:1", "Algorithms open textbook", "978-1-234-56789-7", "Knuth")[0]
    assert hit["eligible_extraction"] == 1 and hit["content_status"] == "open_full_text"
    assert hit["has_toc"] == 1 and hit["has_full_text"] == 1 and hit["chapter_count"] == 1
    blocked = open_books.find_open_book(store, "opac_live:2", "Restricted Networks Handbook", "9780000000002")[0]
    assert blocked["eligible_extraction"] == 0 and blocked["content_status"] == "restricted_license"


def test_isbn_with_conflicting_title_and_missing_isbn_never_match(store: AcademicStore) -> None:
    _index(store, _record(3, title="Quantum Gardening Basics", isbn="9781111111111", rights_uri=CC_BY, rights="CC-BY"))
    assert open_books.find_open_book(store, "opac_live:3", "Database Systems Concepts", "9781111111111") == []
    assert open_books.find_open_book(store, "opac_live:3", "Quantum Gardening Basics", "") == []
    with store._connect() as db:
        assert db.execute("SELECT count(*) FROM audit WHERE action='isbn_title_conflict'").fetchone()[0] == 1


def test_non_book_items_and_deleted_records_are_not_indexed_or_are_removed(store: AcademicStore) -> None:
    _index(store, _record(4, title="Just A Chapter Here", isbn="9782222222222", rights_uri=CC_BY, rights="CC-BY", kind="chapter"))
    with store._connect() as db:
        assert db.execute("SELECT count(*) FROM open_book_index").fetchone()[0] == 0
    _index(store, _record(5, title="Linear Algebra Open Text", isbn="9783333333333", rights_uri=CC_BY, rights="CC-BY"))
    deleted = '<record><header status="deleted"><identifier>oai:library.oapen.org:20.500.12657/5</identifier></header></record>'
    _index(store, deleted)
    with store._connect() as db:
        assert db.execute("SELECT count(*) FROM open_book_index").fetchone()[0] == 0


def test_harvest_resumes_from_saved_token_after_outage(store: AcademicStore) -> None:
    calls: list[dict[str, str]] = []

    def flaky(provider: str, params: dict[str, str]) -> bytes:
        calls.append(params)
        if len(calls) == 1:
            return _page(_record(6, title="Operating Systems Open Book", isbn="9784444444444", rights_uri=CC_BY, rights="CC-BY"), token="T1")
        if len(calls) == 2:
            raise OSError("network down")
        return _page()

    first = open_books.harvest(store, "oapen", max_pages=5, fetch=flaky, pause=0)
    assert first["status"].startswith("error") and first["books_in_index"] == 1 and not first["complete"]
    second = open_books.harvest(store, "oapen", max_pages=5, fetch=flaky, pause=0)
    assert second["complete"] and second["books_in_index"] == 1  # outage never erased the index
    assert calls[2] == {"verb": "ListRecords", "resumptionToken": "T1"}


def test_queue_requires_eligibility_checksum_and_oapen_host(store: AcademicStore, tmp_path: Path) -> None:
    _index(store, _record(7, title="Computer Networks Open Text", isbn="9785555555555", rights_uri=CC_BY, rights="CC-BY"))
    store.observe(
        {"provider": "opac_live", "source_id": "7", "title": "Computer Networks Open Text", "isbn": "9785555555555",
         "edition": "", "identity_key": "isbn:9785555555555:edition:", "revision": "r1", "availability_status": "metadata_only"},
        {"biblionumber": "7"},
    )
    hit = open_books.find_open_book(store, "opac_live:7", "Computer Networks Open Text", "9785555555555")[0]
    with pytest.raises(ValueError, match="checksum"):
        open_books.queue_open_book(store, tmp_path, hit, download=lambda _u: PDF + b"x")
    with pytest.raises(ValueError, match="approved retrieval"):
        open_books.queue_open_book(store, tmp_path, {**hit, "pdf_url": "https://evil.example/bitstream/x.pdf"}, download=lambda _u: PDF)
    with pytest.raises(ValueError, match="not eligible"):
        open_books.queue_open_book(store, tmp_path, {**hit, "eligible_extraction": 0}, download=lambda _u: PDF)
    job_id = open_books.queue_open_book(store, tmp_path, hit, download=lambda _u: PDF)
    job = store.job(job_id)
    assert job and job["rights"] == "open_permitted" and job["content_path"].endswith(".pdf")
    sidecar = Path(job["content_path"]).with_suffix(".source.json")
    assert '"source_kind": "open_book_pdf"' in sidecar.read_text()
