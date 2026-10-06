"""A configured card total is not the live supply at the circulation desk."""

from __future__ import annotations

import pytest

from archipelago.inference.eresource_credentials import format_credential_reply
from archipelago.inference.library_credentials.part01_env import E_RESOURCE_CREDENTIALS

pytestmark = pytest.mark.unit


def test_missing_ledger_does_not_claim_zero_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIPELAGO_MEMBERSHIP_BRITISH_COUNCIL", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_MEMBERSHIP_AMERICAN_LIBRARY", raising=False)

    reply = format_credential_reply("Are British Council cards available?")
    assert reply is not None
    assert "not tracked" in reply
    assert "0 British Council" not in reply


def test_configured_totals_are_not_live_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIPELAGO_MEMBERSHIP_BRITISH_COUNCIL", "10")
    monkeypatch.setenv("ARCHIPELAGO_MEMBERSHIP_AMERICAN_LIBRARY", "5")

    reply = format_credential_reply("American Library membership cards")
    assert reply is not None
    assert "Configured card totals" in reply
    assert "Live checkout availability is not tracked" in reply
    for resource in ("british_council", "american_library"):
        assert "card_count" not in E_RESOURCE_CREDENTIALS[resource]
