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

from collections.abc import Mapping, Sequence
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json
import logging
import os
from typing import Any
import urllib.parse
import urllib.request

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


class FetchRefused(PermissionError):
    """The compliance gate blocked a URL the caller asked an Actor to visit."""


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


def search_actors(keywords: str, limit: int = STORE_SEARCH_DEFAULT_LIMIT) -> list[dict[str, Any]]:
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
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _as_mapping(run: Any) -> dict[str, Any]:
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


def gate_start_urls(
    start_urls: Sequence[str | Mapping[str, object]] | None,
    *,
    allowed_hosts: set[str] | None = None,
    actor: str = "",
    host_delay_sec: float = 0.0,
) -> list[dict[str, str]]:
    """Run every ``startUrls`` entry through the compliance gate.

    An Actor run is still a fetch of those pages, so the same robots/ToS and
    no-credentials rules apply. Callers may pass only what survived here.

    Raises:
        FetchRefused: at least one URL was disallowed. The message names it, so
            the operator fixes the allowlist or the input rather than the run
            silently visiting a disallowed page.
    """
    from archipelago.ingestion.fetch_policy import check_fetch

    allowed: list[dict[str, str]] = []
    refused: list[str] = []
    for entry in start_urls or []:
        url = entry.get("url") if isinstance(entry, Mapping) else entry
        if not isinstance(url, str) or not url:
            continue
        decision = check_fetch(
            url,
            allowed_hosts=allowed_hosts,
            actor=actor,
            # One batch is one logical fetch of one Actor run, so the per-host
            # spacing must not reject the second URL of the same batch. Spacing
            # still applies between separate runs.
            host_delay_sec=host_delay_sec,
        )
        if decision.allowed:
            allowed.append({"url": url})
        else:
            refused.append(f"{url} ({decision.reason})")

    if refused:
        raise FetchRefused("Apify startUrls blocked by the fetch policy: " + "; ".join(refused))
    return allowed


def run_actor(
    actor_id: str,
    run_input: dict[str, Any] | None = None,
    *,
    approved: bool,
    max_total_charge_usd: Decimal | None = None,
    max_items: int | None = None,
    allowed_hosts: set[str] | None = None,
) -> dict[str, Any]:
    """Start an Actor run with a hard bill cap; requires explicit approval.

    Args:
        actor_id: e.g. ``"apify/web-scraper"``.
        run_input: the Actor's JSON input (never a place for bill caps).
        approved: the caller has told the user the pricing model and obtained a
            go-ahead for the first paid run of the session.
        max_total_charge_usd: per-run ceiling; defaults to the configured one.
        max_items: caps billed items for pay-per-result Actors.
        allowed_hosts: Host allowlist for any ``startUrls`` in ``run_input``;
            defaults to the compliance gate's configured allowlist.

    Returns a summary mapping: ``status``, ``run_id``, ``dataset_id``, and
    ``item_count``. Call :func:`fetch_dataset_items` to read the data.

    Raises:
        ApifyApprovalRequired: no explicit go-ahead was given.
        FetchRefused: a requested URL is not permitted by the fetch policy.
    """
    if not approved:
        raise ApifyApprovalRequired(
            "Actor runs are metered; state the pricing model and get an explicit "
            "go-ahead, then pass approved=True"
        )
    cap = resolve_charge_cap(max_total_charge_usd)
    input_payload = dict(run_input or {})
    start_urls = input_payload.get("startUrls")
    if start_urls:
        # Replace rather than append: only gated URLs may reach the Actor.
        input_payload["startUrls"] = gate_start_urls(
            start_urls, allowed_hosts=allowed_hosts, actor=actor_id
        )
    client = _client()

    logger.info("Apify Actor run %s (cap %s USD, max_items=%s)", actor_id, cap, max_items)
    run = client.actor(actor_id).call(
        run_input=input_payload,
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


def fetch_dataset_items(
    dataset_id: str, limit: int = DEFAULT_DATASET_LIMIT
) -> list[dict[str, Any]]:
    """Read the items an Actor run produced (the only place the data lives)."""
    if not dataset_id:
        return []
    client = _client()
    page = client.dataset(dataset_id).list_items(limit=max(1, int(limit)))
    items = getattr(page, "items", None)
    if items is None and isinstance(page, dict):
        items = page.get("items")
    return [item for item in (items or []) if isinstance(item, dict)]


def actor_run_status(run_id: str) -> dict[str, Any]:
    """Read a run and its actual dataset count after a bounded Actor call."""
    if not run_id:
        raise ValueError("run_id is required")
    run = _client().run(run_id).get()
    if run is None:
        return {"status": "NOT_FOUND", "run_id": run_id, "dataset_id": None}
    data = _as_mapping(run)
    stats = data.get("stats") or {}
    return {
        "status": data.get("status"),
        "run_id": run_id,
        "dataset_id": data.get("default_dataset_id") or data.get("defaultDatasetId"),
        "status_message": data.get("status_message") or data.get("statusMessage"),
        "usage_total_usd": data.get("usage_total_usd"),
        "started_at": str(data.get("started_at")) if data.get("started_at") else None,
        "finished_at": str(data.get("finished_at")) if data.get("finished_at") else None,
        "requests_finished": stats.get("requests_finished") or stats.get("requestsFinished") or 0,
        "requests_failed": stats.get("requests_failed") or stats.get("requestsFailed") or 0,
    }


def actor_failure_state(run_id: str) -> str | None:
    """Classify a failed source request from Actor logs without exposing log text."""
    if not run_id:
        return None
    try:
        message = _client().log(run_id).get() or ""
    except Exception as exc:
        logger.warning("Could not inspect Apify Actor log: %s", type(exc).__name__)
        return "log_unavailable"
    if "Received blocked status code: 403" in message:
        return "http_403"
    if "Received blocked status code: 429" in message:
        return "http_429"
    if "Timeout" in message or "timeout" in message or "ETIMEDOUT" in message:
        return "timeout"
    if "0 succeeded, 1 failed" in message:
        return "source_request_failed"
    return None


def _wait_duration() -> timedelta:
    """How long to wait in-line before returning a run id to poll."""
    return timedelta(seconds=DEFAULT_WAIT_DURATION_SEC)
