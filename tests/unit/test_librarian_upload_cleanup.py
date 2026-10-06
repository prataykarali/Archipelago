"""Spreadsheet upload staging must be bounded and cleaned on every path."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
import pytest

from archipelago.inference.routes_misc import m09_librarian_intake as intake

pytestmark = pytest.mark.unit


def _upload(data: bytes, filename: str = "catalogue.csv") -> dict:
    return {"file": (BytesIO(data), filename)}


def test_staged_upload_is_removed_after_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(intake.tempfile, "tempdir", str(tmp_path))
    seen: list[Path] = []

    def fake_plan(path: Path, **_kwargs: object) -> SimpleNamespace:
        assert path.is_file()
        seen.append(path)
        return SimpleNamespace(summary=lambda: {"create": 1})

    monkeypatch.setattr(intake, "plan_merge", fake_plan)
    app = Flask(__name__)
    with app.test_request_context(
        "/api/ingest/spreadsheet/plan", method="POST", data=_upload(b"title\nTest book\n")
    ):
        response, status = intake.ingest_spreadsheet_plan.__wrapped__()
    assert status == 200
    assert response.json == {"create": 1, "dry_run": True}
    assert seen and not seen[0].exists()
    assert list(tmp_path.iterdir()) == []


def test_staged_upload_is_removed_when_plan_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(intake.tempfile, "tempdir", str(tmp_path))

    def fail_plan(_path: Path, **_kwargs: object) -> None:
        raise RuntimeError("parser failed")

    monkeypatch.setattr(intake, "plan_merge", fail_plan)
    app = Flask(__name__)
    with app.test_request_context(
        "/api/ingest/spreadsheet/plan", method="POST", data=_upload(b"title\nTest book\n")
    ):
        with pytest.raises(RuntimeError, match="parser failed"):
            intake.ingest_spreadsheet_plan.__wrapped__()
    assert list(tmp_path.iterdir()) == []


def test_staged_upload_is_removed_after_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(intake.tempfile, "tempdir", str(tmp_path))
    seen: list[Path] = []

    def fake_apply(path: Path, **_kwargs: object) -> dict[str, int]:
        assert path.is_file()
        seen.append(path)
        return {"created": 1}

    monkeypatch.setattr(intake, "apply_merge", fake_apply)
    app = Flask(__name__)
    with app.test_request_context(
        "/api/ingest/spreadsheet/apply", method="POST", data=_upload(b"title\nTest book\n")
    ):
        response, status = intake.ingest_spreadsheet_apply.__wrapped__()
    assert status == 200
    assert response.json == {"created": 1}
    assert seen and not seen[0].exists()
    assert list(tmp_path.iterdir()) == []


def test_oversized_upload_is_rejected_and_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(intake.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(intake, "MAX_SHEET_BYTES", 8)
    app = Flask(__name__)
    with app.test_request_context(
        "/api/ingest/spreadsheet/plan", method="POST", data=_upload(b"title\nToo big\n")
    ):
        response, status = intake.ingest_spreadsheet_plan.__wrapped__()
    assert status == 400
    assert response.json["error"] == "Spreadsheet exceeds the size limit."
    assert list(tmp_path.iterdir()) == []
