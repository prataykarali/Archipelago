"""Apify-backed source discovery for ingestion (server-side only).

Follows ``https://apify.com/agents.md``:

* the token comes from ``APIFY_TOKEN`` only — never from source, logs, or URLs;
* a **paid** Actor run requires an explicit human go-ahead (``approved=True``)
  and a per-run USD ceiling, which is passed as the *call option*
  ``max_total_charge_usd`` (bill caps belong in options, never in the input);
* results are read from the run's dataset, never from the run metadata.

Nothing here scrapes a site by itself: it is the transport an operator or the
ingestion worker calls after a source has been approved.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger("archipelago.ingestion.apify")

APIFY_TOKEN_ENV = "APIFY_TOKEN"
APIFY_MAX_CHARGE_ENV = "APIFY_MAX_TOTAL_CHARGE_USD"

DEFAULT_MAX_TOTAL_CHARGE_USD = Decimal("1.00")
MIN_MAX_TOTAL_CHARGE_USD = Decimal("0.01")

STORE_SEARCH_URL = "https://api.apify.com/v2/store"
STORE_SEARCH_DEFAULT_LIMIT = 10
STORE_SEARCH_MAX_LIMIT = 50
HTTP_TIMEOUT_SEC = 30

DEFAULT_WAIT_DURATION_SEC = 45
DEFAULT_DATASET_LIMIT = 100


class ApifyNotConfigured(RuntimeError):
    """No ``APIFY_TOKEN`` is configured."""


class ApifyApprovalRequired(RuntimeError):
    """A metered Actor run was requested without an explicit go-ahead."""


class ApifyBudgetError(ValueError):
    """The requested charge ceiling is missing, non-positive, or too large."""


def configured() -> bool:
    """True when an Apify token is present in the environment."""
    return bool(os.environ.get(APIFY_TOKEN_ENV, "").strip())


def _max_allowed_charge() -> Decimal:
    """Operator ceiling for a single run, from env (default $1.00)."""
    raw = os.environ.get(APIFY_MAX_CHARGE_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_TOTAL_CHARGE_USD
    try:
        value = Decimal(raw)
    except InvalidOperation:
        logger.warning("Invalid %s=%r; using default", APIFY_MAX_CHARGE_ENV, raw)
        return DEFAULT_MAX_TOTAL_CHARGE_USD
    return value if value > 0 else DEFAULT_MAX_TOTAL_CHARGE_USD


def resolve_charge_cap(requested: Decimal | None) -> Decimal:
    """Validate ``requested`` against the configured ceiling and return it."""
    cap = requested if requested is not None else _max_allowed_charge()
    ceiling = _max_allowed_charge()
    if cap < MIN_MAX_TOTAL_CHARGE_USD:
        raise ApifyBudgetError(f"charge cap must be at least {MIN_MAX_TOTAL_CHARGE_USD} USD")
    if cap > ceiling:
        raise ApifyBudgetError(
            f"charge cap {cap} USD exceeds the configured ceiling {ceiling} USD "
            f"({APIFY_MAX_CHARGE_ENV})"
        )
    return cap


def _client() -> Any:
    """Return an ``ApifyClient`` bound to the env token (never logged)."""
    token = os.environ.get(APIFY_TOKEN_ENV, "").strip()
    if not token:
        raise ApifyNotConfigured(f"{APIFY_TOKEN_ENV} is not set")
    from apify_client import ApifyClient

    return ApifyClient(token)


def _get_json(url: str) -> Any:
    """GET a JSON document over https only (never ``file:``/custom schemes)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"refusing non-https URL: {url!r}")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SEC) as response:  # nosec B310 — https validated
        return json.loads(response.read().decode("utf-8"))


def search_actors(keywords: str, limit: int = STORE_SEARCH_DEFAULT_LIMIT) -> list[dict]:
    """Search the public Apify Store — works without an account or Actor run.

    Search by platform/product name (e.g. ``"openlibrary"``) rather than an end
    goal, per the Apify agent guide.
    """
    query = (keywords or "").strip()
    if not query:
        return []
    bounded = max(1, min(int(limit), STORE_SEARCH_MAX_LIMIT))
    params = urllib.parse.urlencode({"search": query, "limit": bounded})
    payload = _get_json(f"{STORE_SEARCH_URL}?{params}")
    items = payload.get("data", {}).get("items", [])
    return items if isinstance(items, list) else []


def _as_mapping(run: Any) -> dict:
    """Normalise an apify-client Run object (or dict) to a plain mapping."""
    for attr in ("model_dump", "dict"):
        method = getattr(run, attr, None)
        if callable(method):
            data = method()
            if isinstance(data, dict):
                return data
    if isinstance(run, dict):
        return run
    return {k: getattr(run, k) for k in dir(run) if not k.startswith("_")}


def run_actor(
    actor_id: str,
    run_input: dict | None = None,
    *,
    approved: bool,
    max_total_charge_usd: Decimal | None = None,
    max_items: int | None = None,
) -> dict:
    """Start an Actor run with a hard bill cap; requires explicit approval.

    Args:
        actor_id: e.g. ``"apify/web-scraper"``.
        run_input: the Actor's JSON input (never a place for bill caps).
        approved: the caller has told the user the pricing model and obtained a
            go-ahead for the first paid run of the session.
        max_total_charge_usd: per-run ceiling; defaults to the configured one.
        max_items: caps billed items for pay-per-result Actors.

    Returns a summary mapping: ``status``, ``run_id``, ``dataset_id``, and
    ``item_count``. Call :func:`fetch_dataset_items` to read the data.
    """
    if not approved:
        raise ApifyApprovalRequired(
            "Actor runs are metered; state the pricing model and get an explicit "
            "go-ahead, then pass approved=True"
        )
    cap = resolve_charge_cap(max_total_charge_usd)
    client = _client()

    logger.info(
        "Apify Actor run %s (cap %s USD, max_items=%s)", actor_id, cap, max_items
    )
    run = client.actor(actor_id).call(
        run_input=run_input or {},
        max_total_charge_usd=cap,
        max_items=max_items,
        wait_duration=_wait_duration(),
    )
    if run is None:
        return {"status": "FAILED", "run_id": None, "dataset_id": None, "item_count": 0}

    data = _as_mapping(run)
    return {
        "status": data.get("status"),
        "run_id": data.get("id"),
        "dataset_id": data.get("defaultDatasetId") or data.get("default_dataset_id"),
        "item_count": data.get("item_count") or data.get("itemCount") or 0,
    }


def fetch_dataset_items(dataset_id: str, limit: int = DEFAULT_DATASET_LIMIT) -> list[dict]:
    """Read the items an Actor run produced (the only place the data lives)."""
    if not dataset_id:
        return []
    client = _client()
    page = client.dataset(dataset_id).list_items(limit=max(1, int(limit)))
    items = getattr(page, "items", None)
    if items is None and isinstance(page, dict):
        items = page.get("items")
    return list(items or [])


def _wait_duration() -> timedelta:
    """How long to wait in-line before returning a run id to poll."""
    return timedelta(seconds=DEFAULT_WAIT_DURATION_SEC)
