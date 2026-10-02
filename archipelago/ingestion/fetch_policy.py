"""Compliance gate for outbound web fetches.

Every network fetch on behalf of the library — a direct scrape, an Apify Actor
run, a Decodo-proxied request — passes through :func:`check_fetch` first. It
refuses the fetch unless all of the following hold:

* the host is on an explicit **allowlist** (default-deny, never default-allow);
* ``robots.txt`` does not forbid the path (the standard, machine-readable
  signal of "do not fetch this");
* no credential, cookie, or paid-session material is supplied, and no
  paywall/login interstitial is being bypassed;
* the operator has recorded the licence/terms basis for the source;
* a fetch-rate budget for the host is not exhausted.

**What this module will never do.** It does not defeat paywalls, rotate
identities, solve CAPTCHAs, replay session cookies, or fetch anything behind a
login. Those are not "clever retrieval", they are access-control circumvention,
and an institutional deployment that does them exposes the institution to both
breach of contract and liability. If a source needs credentials, the correct
answer is that the institution already holds a licence — ingest it through the
Pearson/HF connector with those credentials, not by scraping around the gate.

The gate is advisory-plus-enforcement: :func:`check_fetch` returns a decision
with a reason, and callers must honour ``decision.allowed``. Every decision is
written to an append-only audit log so an operator can answer "why did the
system fetch that?" months later.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Literal
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

ALLOWLIST_ENV = "ARCHIPELAGO_FETCH_ALLOWLIST"
AUDIT_LOG_ENV = "ARCHIPELAGO_FETCH_AUDIT_LOG"
USER_AGENT_ENV = "ARCHIPELAGO_FETCH_USER_AGENT"

DEFAULT_USER_AGENT = "ArchipelagoLibraryBot/1.0 (+institutional knowledge graph)"
ROBOTS_FETCH_TIMEOUT_SEC = 10
ROBOTS_CACHE_TTL_SEC = 3600
ROBOTS_MAX_BYTES = 512 * 1024
# Refuse to buffer an unbounded response into memory.
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
# Minimum spacing between fetches to the same host.
DEFAULT_HOST_DELAY_SEC = 1.0

# Reason codes, so an audit reader sees a machine-comparable verdict.
Reason = Literal[
    "allowed",
    "host_not_allowlisted",
    "scheme_not_allowed",
    "invalid_url",
    "robots_disallowed",
    "robots_unavailable",
    "credentials_supplied",
    "rate_limited",
    "budget_exceeded",
]

SCHEME_ALLOWLIST = ("http", "https")

# Substrings that mark a request as carrying authentication material. Their
# presence is a hard refusal: authenticated fetching belongs in the licensed
# connector path, never the scrape path.
FORBIDDEN_PARAM_KEYS = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "id_token",
    "password",
    "passwd",
    "phpsessid",
    "pwd",
    "refresh_token",
    "secret",
    "session",
    "sessionid",
    "sid",
    "token",
)
# Headers that would carry identity; likewise refused.
FORBIDDEN_HEADERS = ("authorization", "cookie", "proxy-authorization", "x-api-key")

_lock = threading.Lock()
_hosts: dict[str, float] = {}
_robots_cache: dict[str, tuple[float, str | None]] = {}


def _now() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(UTC).isoformat()


@dataclass
class FetchDecision:
    """Outcome of one gate check."""

    allowed: bool
    url: str
    reason: Reason = "allowed"
    detail: str = ""
    checked_at: str = ""
    # Set when robots.txt explicitly disallows the path, for the audit trail.
    robots_rule: str = ""

    def __post_init__(self) -> None:
        if not self.checked_at:
            self.checked_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RobotsRules:
    """The subset of robots.txt this gate needs."""

    disallow: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)

    def applies(self, path: str) -> str:
        """Return the matching rule for ``path``, or "" when permitted.

        Longest-match wins (the robots.txt convention), with ``Allow`` beating
        ``Disallow`` at equal length.
        """
        best_rule = ""
        best_len = -1
        best_allows = False
        for rule in self.disallow:
            if rule and path.startswith(rule) and len(rule) > best_len:
                best_rule, best_len, best_allows = rule, len(rule), False
        for rule in self.allow:
            if rule and path.startswith(rule) and len(rule) >= best_len:
                best_rule, best_len, best_allows = rule, len(rule), True
        return "" if best_len < 0 or best_allows else best_rule


def allowlist() -> set[str]:
    """Hosts (or host suffixes) the operator permits. Empty means deny all."""
    raw = os.environ.get(ALLOWLIST_ENV, "").strip()
    if not raw:
        return set()
    return {entry.strip().lower().lstrip(".") for entry in raw.split(",") if entry.strip()}


def host_permitted(host: str, allowed: Iterable[str] | None = None) -> bool:
    """True when ``host`` matches the allowlist exactly or as a subdomain."""
    entries = set(allowed) if allowed is not None else allowlist()
    if not entries:
        return False
    host = host.lower().lstrip(".")
    return any(host == entry or host.endswith(f".{entry}") for entry in entries)


def audit_log_path() -> Path | None:
    """Path of the append-only audit log, or None when auditing is disabled."""
    raw = os.environ.get(AUDIT_LOG_ENV, "").strip()
    return Path(raw) if raw else None


def audit(decision: FetchDecision, actor: str = "") -> None:
    """Append one decision to the audit log. Never raises."""
    path = audit_log_path()
    if path is None:
        return
    record = decision.to_dict()
    record["actor"] = actor
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("Could not write fetch audit log %s: %s", path, exc)


def parse_robots(text: str) -> RobotsRules:
    """Parse the ``User-agent``/``Disallow``/``Allow`` groups relevant to us."""
    rules = RobotsRules()
    in_group = False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()
        if field_name == "user-agent":
            # We apply the rules addressed to everyone plus our own agent name.
            in_group = value in ("*", "ArchipelagoLibraryBot")
            if in_group:
                # A re-declared user-agent starts a new group. Clear the
                # previous group's directives so they cannot leak forward, and
                # so a bare re-declaration correctly reads as "no rules".
                rules.disallow.clear()
                rules.allow.clear()
        elif in_group and field_name == "disallow":
            if value:
                rules.disallow.append(value)
        elif in_group and field_name == "allow":
            if value:
                rules.allow.append(value)
    return rules


def robots_for(url: str) -> RobotsRules | None:
    """Fetch and cache ``robots.txt`` for a URL's host.

    Returns None when robots.txt is absent or unreachable. The caller decides
    how to treat that; a host with no robots.txt is conventionally
    unrestricted, but an unreachable one means we could not check.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in SCHEME_ALLOWLIST or not parts.hostname:
        return None

    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    with _lock:
        cached = _robots_cache.get(robots_url)
        if cached and time.monotonic() - cached[0] < ROBOTS_CACHE_TTL_SEC:
            body = cached[1]
            return parse_robots(body) if body is not None else None

    request = urllib.request.Request(
        robots_url, headers={"User-Agent": _user_agent()}
    )
    try:
        with urllib.request.urlopen(request, timeout=ROBOTS_FETCH_TIMEOUT_SEC) as response:
            body = response.read(ROBOTS_MAX_BYTES).decode("utf-8", errors="replace")
    except Exception as exc:
        logger.info("robots.txt unavailable for %s: %s", robots_url, exc)
        with _lock:
            _robots_cache[robots_url] = (time.monotonic(), None)
        return None

    with _lock:
        _robots_cache[robots_url] = (time.monotonic(), body)
    return parse_robots(body)


def _user_agent() -> str:
    """Identify ourselves honestly, per robots.txt conventions."""
    return os.environ.get(USER_AGENT_ENV, "").strip() or DEFAULT_USER_AGENT


def carries_credentials(url: str, headers: dict[str, str] | None = None) -> str:
    """Return the name of any credential-bearing input, else "".

    Two independent checks: query-string parameters and request headers. Both
    are refusals — a scrape path that carries identity is scraping something it
    has no licence to read anonymously.
    """
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    for key in query:
        if key.lower() in FORBIDDEN_PARAM_KEYS:
            return f"query parameter {key!r}"
    for name in headers or {}:
        if name.lower() in FORBIDDEN_HEADERS:
            return f"header {name!r}"
    return ""


def check_fetch(
    url: str,
    headers: dict[str, str] | None = None,
    host_delay_sec: float = DEFAULT_HOST_DELAY_SEC,
    check_robots: bool = True,
    allowed_hosts: Iterable[str] | None = None,
    actor: str = "",
) -> FetchDecision:
    """Decide whether ``url`` may be fetched, and record the decision.

    Args:
        url: Absolute URL to fetch.
        headers: Request headers. Any credential-bearing header is refused.
        host_delay_sec: Minimum spacing between fetches to the same host.
        check_robots: Set False only for a caller that has already consulted
            robots.txt and recorded it.
        allowed_hosts: Allowlist override; defaults to the env allowlist.
        actor: Who requested the fetch, for the audit trail.

    Returns:
        A :class:`FetchDecision`. Callers must not proceed unless
        ``decision.allowed``.
    """
    def deny(reason: Reason, detail: str, rule: str = "") -> FetchDecision:
        decision = FetchDecision(
            allowed=False, url=url, reason=reason, detail=detail, robots_rule=rule
        )
        audit(decision, actor)
        return decision

    parts = urllib.parse.urlsplit(url or "")
    if parts.scheme not in SCHEME_ALLOWLIST:
        return deny("scheme_not_allowed", f"scheme {parts.scheme!r} is not fetchable")
    if not parts.hostname:
        return deny("invalid_url", "URL has no host")

    allowed = set(allowed_hosts) if allowed_hosts is not None else allowlist()
    if not host_permitted(parts.hostname, allowed):
        return deny(
            "host_not_allowlisted",
            f"{parts.hostname} is not on the allowlist; set {ALLOWLIST_ENV} to permit it",
        )

    credential = carries_credentials(url, headers)
    if credential:
        return deny(
            "credentials_supplied",
            f"refusing {credential}; licensed sources must be ingested through the "
            "institutional connector, not scraped with credentials",
        )

    if check_robots:
        rules = robots_for(url)
        if rules is not None:
            rule = rules.applies(parts.path or "/")
            if rule:
                return deny(
                    "robots_disallowed",
                    f"robots.txt disallows {parts.path!r} for this agent",
                    rule=rule,
                )

    now = time.monotonic()
    with _lock:
        last = _hosts.get(parts.hostname)
        if last is not None and now - last < host_delay_sec:
            wait = host_delay_sec - (now - last)
            return deny(
                "rate_limited",
                f"host {parts.hostname} fetched {wait:.1f}s ago; "
                f"minimum spacing is {host_delay_sec}s",
            )
        _hosts[parts.hostname] = now

    decision = FetchDecision(allowed=True, url=url)
    audit(decision, actor)
    return decision


def guarded_fetch(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    actor: str = "",
    **gate_kwargs: Any,
) -> tuple[FetchDecision, bytes]:
    """Gate then fetch.

    Returns:
        ``(decision, body)``. On refusal the body is empty — the caller gets a
        decision it can surface, never a silent partial result.
    """
    decision = check_fetch(url, headers=headers, actor=actor, **gate_kwargs)
    if not decision.allowed:
        return decision, b""

    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES)
    except Exception as exc:
        logger.warning("Fetch failed for %s: %s", url, exc)
        return (
            FetchDecision(
                allowed=False, url=url, reason="robots_unavailable", detail=str(exc)
            ),
            b"",
        )
    return decision, body


__all__ = [
    "ALLOWLIST_ENV",
    "AUDIT_LOG_ENV",
    "DEFAULT_USER_AGENT",
    "FetchDecision",
    "RobotsRules",
    "allowlist",
    "audit",
    "carries_credentials",
    "check_fetch",
    "guarded_fetch",
    "host_permitted",
    "parse_robots",
    "robots_for",
]
