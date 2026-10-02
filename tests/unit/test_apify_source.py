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
    # The compliance gate keeps per-host rate state in module globals; reset it
    # so tests do not throttle one another on the shared example.com host.
    from archipelago.ingestion import fetch_policy

    fetch_policy._hosts.clear()
    fetch_policy._robots_cache.clear()


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
            # The compliance gate runs on every Actor URL; example.com is the
            # host this test is permitted to reach.
            allowed_hosts={"example.com"},
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


# ─── The compliance gate fronts every Actor run ─────────────────────────────


def test_run_actor_refuses_a_host_outside_the_allowlist(monkeypatch) -> None:
    """An Actor run is still a fetch: the gate applies to its startUrls."""
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, "apify_api_test")
    with patch("apify_client.ApifyClient", MagicMock()):
        with pytest.raises(apify.FetchRefused) as excinfo:
            apify.run_actor(
                "apify/web-scraper",
                {"startUrls": [{"url": "https://not-permitted.example.org/x"}]},
                approved=True,
                max_total_charge_usd=Decimal("0.50"),
                allowed_hosts={"example.com"},
            )
    assert "host_not_allowlisted" in str(excinfo.value)


def test_run_actor_refuses_a_url_carrying_credentials(monkeypatch) -> None:
    """A token in the query string is a refusal, not a convenience."""
    monkeypatch.setenv(apify.APIFY_TOKEN_ENV, "apify_api_test")
    with patch("apify_client.ApifyClient", MagicMock()):
        with pytest.raises(apify.FetchRefused) as excinfo:
            apify.run_actor(
                "apify/web-scraper",
                {"startUrls": [{"url": "https://example.com/x?access_token=secret"}]},
                approved=True,
                max_total_charge_usd=Decimal("0.50"),
                allowed_hosts={"example.com"},
            )
    assert "credentials_supplied" in str(excinfo.value)


def test_gate_start_urls_refuses_the_whole_batch_if_any_url_is_blocked(monkeypatch) -> None:
    """Fail closed: one disallowed URL aborts the run rather than filtering.

    Filtering would quietly narrow the scrape to whatever happened to pass,
    producing a partial dataset that looks complete. An operator must see the
    refusal and fix the allowlist.
    """
    with pytest.raises(apify.FetchRefused) as excinfo:
        apify.gate_start_urls(
            [
                {"url": "https://example.com/a"},
                {"url": "https://blocked.example.org/b"},
            ],
            allowed_hosts={"example.com"},
        )
    message = str(excinfo.value)
    assert "blocked.example.org" in message
    assert "host_not_allowlisted" in message


def test_gate_start_urls_passes_a_wholly_permitted_batch(monkeypatch) -> None:
    allowed = apify.gate_start_urls(
        [
            {"url": "https://example.com/a"},
            {"url": "https://example.com/b"},
        ],
        allowed_hosts={"example.com"},
        # Two URLs on one host inside a single batch must not trip the
        # inter-request spacing.
        host_delay_sec=0.0,
    )
    assert allowed == [{"url": "https://example.com/a"}, {"url": "https://example.com/b"}]


def test_gate_start_urls_accepts_plain_strings():
    assert apify.gate_start_urls(
        ["https://example.com/a"], allowed_hosts={"example.com"}
    ) == [{"url": "https://example.com/a"}]


def test_gate_start_urls_is_empty_safe():
    assert apify.gate_start_urls(None, allowed_hosts={"example.com"}) == []
    assert apify.gate_start_urls([], allowed_hosts={"example.com"}) == []


def test_gate_start_urls_drops_empty_and_malformed_entries():
    assert apify.gate_start_urls(
        [{"url": ""}, {"no_url": 1}, 42], allowed_hosts={"example.com"}
    ) == []
