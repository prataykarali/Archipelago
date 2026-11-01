"""Verified catalogue identifiers must never be guessed or silently misjoined."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_research"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from koha_snapshot import _catalog_identifiers, _valid_isbn  # noqa: E402


@pytest.mark.unit
def test_isbn_checksum_rejects_wrong_identifier() -> None:
    assert _valid_isbn("9789332543515")
    assert _valid_isbn("0-306-40615-2")
    assert not _valid_isbn("9789332543516")
    assert not _valid_isbn("unknown")


@pytest.mark.unit
def test_catalog_identifiers_require_unique_book_id(tmp_path: Path) -> None:
    path = tmp_path / "catalog_identifiers.csv"
    path.write_text(
        "biblionumber,isbn,call_number,rack_number\n1480,9789332543515,004 RUS,\n",
        encoding="utf-8",
    )
    assert _catalog_identifiers(path)["1480"] == {
        "isbn": "9789332543515",
        "call_number": "004 RUS",
        "rack_number": "",
    }
    path.write_text(
        "biblionumber,isbn,call_number,rack_number\n"
        "1480,9789332543515,004 RUS,\n"
        "1480,9789332543515,004 RUS,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate biblionumber"):
        _catalog_identifiers(path)
