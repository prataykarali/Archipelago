"""Real local regressions for remaining code repairs, independent of private corpus."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
sys.path.insert(0, str(HOST))

from engine import adaptive_session  # noqa: E402
from engine.gap_resources import gap_resources  # noqa: E402
from hostapp.learning_memory import LearningMemory  # noqa: E402
from hostapp.routes.diagnostics import register  # noqa: E402
from hostapp.routes.learning_settings import register as register_staff  # noqa: E402

from archipelago.inference.outbound_context import minimal_context  # noqa: E402
from archipelago.ingestion import spreadsheet  # noqa: E402
from archipelago.ingestion.table_reader import read_table  # noqa: E402

pytestmark = pytest.mark.unit


def test_context_excludes_history_inventory_and_secrets():
    result = minimal_context(
        [
            {
                "evidence_id": "S1",
                "topic": "A",
                "text_span": "Safe. secret=redactme\nmail a@example.com",
            },
            {"evidence_id": "S2", "private": True, "text_span": "Never send"},
            {"evidence_id": "S3", "text_span": "Useful.", "barcode": "inventory"},
        ],
        "student_history=never send; raw records",
    )
    assert "Useful" in result and "Safe" in result
    assert not any(
        s in result
        for s in ("redactme", "a@example.com", "Never send", "inventory", "student_history")
    )
    assert minimal_context(None, "PRIVATE RAW NOTES") == ""
    assert len(minimal_context([{"text": "x" * 2000}] * 20)) <= 6000


def test_memory_requires_consent_and_persists_only_allowed_fields(tmp_path):
    memory = LearningMemory(tmp_path / "memory.db")
    state = {
        "preference": "code",
        "mastery": {
            "n1": {
                "node_id": "n1",
                "mastery_state": "mastered",
                "confidence": 0.95,
                "last_verified": 1,
                "verification_count": 1,
                "answer": "private answer",
                "student_email": "private identity",
            }
        },
        "history": [{"answer": "never persist"}],
    }
    memory.save("a", state)
    assert memory.load("a") == {}
    memory.enable("a")
    memory.save("a", state)
    saved = memory.load("a")
    assert saved["mastery"]["n1"]["confidence"] == 0.95
    assert "private" not in json.dumps(saved) and "history" not in saved
    assert memory.load("b") == {}
    memory.delete("a")
    memory.save("a", state)
    assert memory.load("a") == {}, "stale session must not undo deletion"


def test_memory_expiry_and_minimum_aggregate_cohort(tmp_path):
    memory = LearningMemory(tmp_path / "memory.db")
    for i in range(5):
        owner = f"owner-{i}"
        memory.enable(owner)
        memory.save(
            owner,
            {
                "preference": "conceptual",
                "mastery": {"n1": {"mastery_state": "review_gap", "last_verified": 1}},
            },
        )
        if i < 4:
            assert memory.aggregate() == []
    assert memory.aggregate() == [{"concept_id": "n1", "gap_count": 5}]
    with memory.connect() as db:
        db.execute("UPDATE learning_memory SET expires=0")
    assert memory.aggregate() == [] and memory.load("owner-0") == {}


def test_remembered_fading_is_microverified_in_current_session(tmp_path):
    from engine.learning_state import update_mastery

    from tests.unit.test_learning_sessions import graph_fixture, submit

    graph = graph_fixture(tmp_path)
    state, _ = adaptive_session.start(
        graph,
        "n0",
        remembered={
            "n3": update_mastery("n3", True, "high", now=0),
            "unrelated": update_mastery("unrelated", True, "high"),
        },
    )
    assert "unrelated" not in state["mastery"]
    q = state["question"]["concept_id"]
    assert q == "n3"
    submit(graph, state)
    assert state["mastery"][q]["mastery_state"] == "mastered"


def test_http_opt_in_deletion_and_staff_boundary(tmp_path, monkeypatch):
    from tests.unit.test_learning_sessions import graph_fixture

    monkeypatch.setenv("ARCHIPELAGO_QUIZ_DB", str(tmp_path / "sessions.db"))
    graph = graph_fixture(tmp_path)
    app = Flask(__name__)
    auth = SimpleNamespace(principal=lambda: ({"role": "student"}, None))
    ctx = SimpleNamespace(engine=SimpleNamespace(graph=graph), auth=auth)
    register(app, ctx)
    register_staff(app, ctx)
    a, b = app.test_client(), app.test_client()
    data = a.get("/api/chat/diagnostic-mcqs?concept=n0&remember=1").get_json()
    assert data["memory_enabled"]
    assert a.get("/api/chat/learning-memory").get_json()["enabled"]
    assert not b.get("/api/chat/learning-memory").get_json()["enabled"]
    assert a.get("/api/staff/learning-summary?role=librarian").status_code == 403
    assert a.get("/api/staff/learning-summary", headers={"X-Role": "librarian"}).status_code == 403
    auth.principal = lambda: ({"role": "librarian"}, None)
    staff = a.get("/api/staff/learning-summary")
    assert staff.status_code == 200 and staff.get_json()["individual_records"] is False
    assert staff.headers["Cache-Control"] == "no-store, private"
    a.delete("/api/chat/learning-memory")
    assert not a.get("/api/chat/learning-memory").get_json()["enabled"]


def test_gap_resources_need_exact_nonambiguous_evidence_ids():
    graph = SimpleNamespace(nodes={"n": {"sources": [{"doc_id": "book-1"}]}})
    records = [
        {"book_id": "different", "title": "Keyword matches", "available_copies": 5},
        {
            "book_id": "book-1",
            "title": "Exact source",
            "location": "Shelf 2",
            "available_copies": 2,
        },
    ]
    out = gap_resources(graph, ["n"], records)
    assert [r["title"] for r in out] == ["Exact source"]
    assert out[0]["status"] == "imported_snapshot"
    assert gap_resources(graph, ["n"], [*records, dict(records[1])]) == []


@pytest.mark.parametrize("suffix", [".csv", ".tsv", ".xlsx", ".ods"])
def test_real_spreadsheet_formats(tmp_path, suffix):
    path = tmp_path / ("library" + suffix)
    rows = [
        ["Title", "Author", "Total Copies", "Available Copies", "Call Number"],
        ["Linear Algebra", "Author", "3", "2", "QA184"],
    ]
    if suffix in {".csv", ".tsv"}:
        import csv

        with path.open("w", newline="") as stream:
            csv.writer(stream, delimiter="\t" if suffix == ".tsv" else ",").writerows(rows)
    elif suffix == ".xlsx":
        from openpyxl import Workbook

        book = Workbook()
        for row in rows:
            book.active.append(row)
        book.save(path)
    else:
        from odf.opendocument import OpenDocumentSpreadsheet
        from odf.table import Table, TableCell, TableRow
        from odf.text import P

        doc = OpenDocumentSpreadsheet()
        table = Table(name="Sheet")
        for row in rows:
            tr = TableRow()
            for value in row:
                cell = TableCell(valuetype="string")
                cell.addElement(P(text=value))
                tr.addElement(cell)
            table.addElement(tr)
        doc.spreadsheet.addElement(table)
        doc.save(str(path))
    assert read_table(path)[1][0] == "Linear Algebra"
    records, _fields, errors = spreadsheet.load_records(path)
    assert not errors and records[0]["available_copies"] == 2
    assert records[0]["call_number"] == "QA184"


@pytest.mark.parametrize(
    "text",
    [
        "Title,Total Copies,Available Copies\nBad,-1,0\n",
        "Title,Total Copies,Available Copies\nBad,1,4\n",
        "Author\nMissing Title\n",
    ],
)
def test_invalid_spreadsheet_never_marks_applied(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text)
    result = spreadsheet.apply_merge(path, dry_run=False)
    assert result["errors"] and not result["applied"] and result["writes_performed"] == 0


def test_lfs_pointer_and_onloan_not_available(tmp_path):
    path = tmp_path / "data.ods"
    path.write_text("version https://git-lfs.github.com/spec/v1")
    with pytest.raises(ValueError, match="LFS"):
        read_table(path)
    _mapping, fields = spreadsheet.map_columns(["Title", "On Loan"])
    assert "available_copies" not in fields


def test_multi_page_chunks_never_claim_a_different_pages_offsets(tmp_path):
    import fitz

    from archipelago.ingestion.pdf_chunk import chunk_pdf

    path = tmp_path / "native.pdf"
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_textbox(
            fitz.Rect(40, 40, 540, 740), (f"Page {i + 1} evidence. " * 30), fontsize=12
        )
    doc.save(path)
    doc.close()
    chunks = chunk_pdf(str(path), page_bounded=True)
    assert chunks and {c["page_number"] for c in chunks} == {1, 2}
    assert all(c["page_start"] == c["page_end"] == c["page_number"] for c in chunks)


def test_missing_ocr_does_not_silently_succeed(monkeypatch):
    from archipelago.ingestion.ocr import page_blocks

    monkeypatch.setattr("shutil.which", lambda name: None)
    page = SimpleNamespace(get_text=lambda _: {"blocks": []}, get_images=lambda: [1])
    with pytest.raises(RuntimeError, match="Tesseract"):
        page_blocks(page)


def test_provider_does_not_switch_after_partial_output(monkeypatch):
    import archipelago.inference.llm_gateway.part04_stream as module

    monkeypatch.setattr(module.config, "configure_gateway", lambda: None)
    monkeypatch.setattr(module.config, "get_active_provider", lambda: "xkiro")
    monkeypatch.setattr(module, "_provider_order", lambda _: ["xkiro", "nvidia"])
    called = []

    def stream(provider, *args, **kwargs):
        called.append(provider)
        yield "first "
        raise RuntimeError("interrupted")

    monkeypatch.setattr(module, "_stream_by_name", stream)
    iterator = module.gateway_chat_stream([])
    assert next(iterator) == "first "
    with pytest.raises(RuntimeError, match="interrupted"):
        next(iterator)
    assert called == ["xkiro"]


def test_citation_payload_carries_private_source_and_node_flags():
    from archipelago.inference.citations import build_citation_payloads

    node = {"id": "n", "label": "Academic", "private": True}
    payloads = build_citation_payloads(
        node,
        [],
        [],
        {
            "n": [
                {
                    "doc_id": "private.pdf",
                    "page_number": 1,
                    "text": "Private text",
                    "evidence_id": "S1",
                }
            ],
        },
    )
    assert minimal_context(payloads) == ""
    node["private"] = False
    payloads = build_citation_payloads(
        node,
        [],
        [],
        {
            "n": [
                {
                    "doc_id": "private.pdf",
                    "page_number": 1,
                    "text": "Private text",
                    "visibility": "confidential",
                    "evidence_id": "S1",
                }
            ],
        },
    )
    assert minimal_context(payloads) == ""


def test_upload_inventory_cache_isolated_by_source_path(tmp_path):
    from archipelago.inference.inventory_ssot import clear_all_inventory_caches, read_inventory

    roots = [tmp_path / "a", tmp_path / "b"]
    for root, title in zip(roots, ("A", "B"), strict=True):
        (root / "pdfs").mkdir(parents=True)
        (root / "pdfs" / "upload_inventory.json").write_text(json.dumps([{"title": title}]))
    clear_all_inventory_caches()
    assert read_inventory(roots[0])[0]["title"] == "A"
    assert read_inventory(roots[1])[0]["title"] == "B"
    clear_all_inventory_caches()
