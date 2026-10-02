"""Unit tests for the cost-capped, approval-gated Apify source client."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from archipelago.ingestion import apify_source as apify

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(apify.APIFY_TOKEN_ENV, raising=False)
    monkeypatch.delenv(apify.APIFY_MAX_CHARGE_ENV, raising=False)


def _fake_store_http(payload: dict):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__ = lambda self: response
    response.__exit__ = lambda self, *a: False
    return response


def test_not_configured_without_token() -> None:
    assert apify.configured() is False
    with pytest.raises(apify.ApifyNotConfigured):
        apify.run_actor("apify/web-scraper", {}, approved=True)


def test_requires_explicit_approval(monkeypatch) -> None:
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, "apify_api_test")
    with pytest.raises(apify.ApifyApprovalRequired):
        apify.run_actor("apify/web-scraper", {}, approved=False)


def test_rejects_cap_above_ceiling(monkeypatch) -> None:
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, "apify_api_test")
    monkeypatch.setenv(apify.APIFY_MAX_CHARGE_ENV, "1.00")
    with pytest.raises(apify.ApifyBudgetError):
        apify.run_actor(
            "apify/web-scraper", {}, approved=True, max_total_charge_usd=Decimal("5.00")
        )


def test_rejects_non_positive_cap(monkeypatch) -> None:
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, "apify_api_test")
    with pytest.raises(apify.ApifyBudgetError):
        apify.resolve_charge_cap(Decimal("0"))


def test_run_actor_passes_cap_in_options_not_input(monkeypatch) -> None:
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, "apify_api_test")
    actor = MagicMock()
    actor.call.return_value = {
        "id": "run-1",
        "status": "SUCCEEDED",
        "defaultDatasetId": "ds-1",
        "item_count": 3,
    }
    client = MagicMock()
    client.actor.return_value = actor

    with patch("apify_client.ApifyClient", return_value=client):
        summary = apify.run_actor(
            "apify/web-scraper",
            {"startUrls": [{"url": "https://example.com"}]},
            approved=True,
            max_total_charge_usd=Decimal("0.50"),
            max_items=10,
        )

    assert summary == {
        "status": "SUCCEEDED",
        "run_id": "run-1",
        "dataset_id": "ds-1",
        "item_count": 3,
    }
    kwargs = actor.call.call_args.kwargs
    assert kwargs["max_total_charge_usd"] == Decimal("0.50")
    assert kwargs["max_items"] == 10
    # The cap must not be smuggled into the Actor input.
    assert "max_total_charge_usd" not in kwargs["run_input"]
    assert "maxItems" not in kwargs["run_input"]


def test_fetch_dataset_items(monkeypatch) -> None:
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, "apify_api_test")
    page = MagicMock()
    page.items = [{"url": "https://example.com", "title": "Example"}]
    dataset = MagicMock()
    dataset.list_items.return_value = page
    client = MagicMock()
    client.dataset.return_value = dataset

    with patch("apify_client.ApifyClient", return_value=client):
        items = apify.fetch_dataset_items("ds-1", limit=5)

    assert items == [{"url": "https://example.com", "title": "Example"}]
    dataset.list_items.assert_called_once_with(limit=5)


def test_search_actors_uses_public_store_api() -> None:
    payload = {"data": {"items": [{"id": "apify/web-scraper", "name": "Web Scraper"}]}}
    with patch.object(apify, "_get_json", return_value=payload) as get_json:
        actors = apify.search_actors("web scraper", limit=3)

    assert actors == [{"id": "apify/web-scraper", "name": "Web Scraper"}]
    url = get_json.call_args.args[0]
    assert url.startswith("https://api.apify.com/v2/store?")
    assert "search=web+scraper" in url
    assert "limit=3" in url


def test_token_never_appears_in_logs(monkeypatch, caplog) -> None:
    secret = "apify_api_SuperSecretValue123"
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, secret)
    actor = MagicMock()
    actor.call.return_value = {"id": "r", "status": "SUCCEEDED", "defaultDatasetId": "d"}
    client = MagicMock()
    client.actor.return_value = actor

    with patch("apify_client.ApifyClient", return_value=client), caplog.at_level("INFO"):
        apify.run_actor("apify/web-scraper", {}, approved=True)

    assert secret not in caplog.text
