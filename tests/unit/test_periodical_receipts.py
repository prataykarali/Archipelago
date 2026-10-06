"""Serial status labels from campus spreadsheets are normalized conservatively."""

from __future__ import annotations

import pytest

from archipelago.inference.library_queries import find_journal_status
from archipelago.inference.periodical_receipts import normalize_receipt_status
from archipelago.inference.synthesis_library import render_journal_status

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Expected", "Expected"),
        ("Overdue", "Late"),
        ("Late", "Late"),
        ("Received", "Received"),
        ("Arrived", "Received"),
        ("", "Unknown"),
        ("Subscription active", "Unknown"),
    ],
)
def test_unrecognized_delivery_is_never_claimed_as_received(
    source: str,
    expected: str,
) -> None:
    assert normalize_receipt_status(source) == expected


def test_unknown_journal_does_not_acquire_fabricated_holdings() -> None:
    assert find_journal_status("Fictional Journal of Unverified Holdings") is None


def test_blank_journal_status_is_unknown() -> None:
    answer = render_journal_status("journal", [{"journal_title": "Journal A"}])
    assert "Status unknown" in answer
    assert "Up to date" not in answer
