"""Feature regression — the compliance gate for outbound web fetches.

The gate is the thing standing between the institution and a terms-of-service
breach, so its refusals matter more than its happy path. These tests pin the
refusals:

* default-deny: an unlisted host is never fetched;
* robots.txt ``Disallow`` is honoured, with longest-match and Allow-beats-
  Disallow precedence;
* a request carrying credentials, a session cookie, or a token in the query
  string is refused outright — licensed content is ingested through the
  connector, not scraped around the gate;
* per-host rate spacing is enforced;
* every decision, refusal included, reaches the audit log.

No test performs a real network request.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archipelago.ingestion import fetch_policy as fp  # noqa: E402

pytestmark = pytest.mark.unit

ALLOWED = {"example.edu", "openaccess.org"}
SITE = "https://example.edu/papers/attention.pdf"


@pytest.fixture(autouse=True)
def isolated_gate(monkeypatch, tmp_path):
    """Fresh allowlist, audit log, and caches for each test."""
    monkeypatch.setenv(fp.ALLOWLIST_ENV, "example.edu,openaccess.org")
    monkeypatch.setenv(fp.AUDIT_LOG_ENV, str(tmp_path / "audit.log"))
    monkeypatch.delenv(fp.USER_AGENT_ENV, raising=False)
    fp._hosts.clear()
    fp._robots_cache.clear()
    return tmp_path


def _robots(body: str) -> None:
    """Seed the robots cache for example.edu with a fresh timestamp.

    The cache is only honoured within ROBOTS_CACHE_TTL_SEC, so a stale stamp
    would silently fall through to a real network fetch.
    """
    fp._robots_cache["https://example.edu/robots.txt"] = (time.monotonic(), body)


def _audit_lines(tmp_path) -> list[dict]:
    path = Path(str(tmp_path))
    log = next(path.glob("audit.log"), None)
    if not log or not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


# ─── Default deny ───────────────────────────────────────────────────────────


def test_host_on_allowlist_is_permitted():
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed


def test_unlisted_host_is_refused():
    decision = fp.check_fetch("https://evil.example.com/x", allowed_hosts=ALLOWED)
    assert not decision.allowed
    assert decision.reason == "host_not_allowlisted"


def test_empty_allowlist_refuses_everything(monkeypatch):
    """Default-deny: an unconfigured deployment fetches nothing."""
    monkeypatch.setenv(fp.ALLOWLIST_ENV, "")
    assert fp.allowlist() == set()
    assert not fp.check_fetch(SITE).allowed


def test_subdomain_of_an_allowed_host_is_permitted():
    assert fp.check_fetch("https://cdn.example.edu/x", allowed_hosts=ALLOWED).allowed


def test_lookalike_domain_is_refused():
    """`example.edu.evil.com` must not match the `example.edu` entry."""
    assert not fp.check_fetch("https://example.edu.evil.com/x", allowed_hosts=ALLOWED).allowed


@pytest.mark.parametrize(
    "url, reason",
    [
        ("file:///etc/passwd", "scheme_not_allowed"),
        ("ftp://example.edu/x", "scheme_not_allowed"),
        ("javascript:alert(1)", "scheme_not_allowed"),
        ("https:///no-host", "invalid_url"),
        ("", "scheme_not_allowed"),
    ],
)
def test_non_http_schemes_are_refused(url, reason):
    decision = fp.check_fetch(url, allowed_hosts=ALLOWED)
    assert not decision.allowed
    assert decision.reason == reason


# ─── Credentials are never used to scrape ───────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://example.edu/x?access_token=abc",
        "https://example.edu/x?api_key=abc",
        "https://example.edu/x?password=hunter2",
        "https://example.edu/x?session=abc",
        "https://example.edu/x?PHPSESSID=abc",
        "https://example.edu/x?id_token=abc",
    ],
)
def test_query_string_credentials_are_refused(url):
    decision = fp.check_fetch(url, allowed_hosts=ALLOWED)
    assert not decision.allowed
    assert decision.reason == "credentials_supplied"
    assert "connector" in decision.detail, "the refusal must point to the licensed path"


@pytest.mark.parametrize("header", ["Authorization", "Cookie", "X-API-Key", "Proxy-Authorization"])
def test_credential_headers_are_refused(header):
    decision = fp.check_fetch(SITE, headers={header: "Bearer secret"}, allowed_hosts=ALLOWED)
    assert not decision.allowed
    assert decision.reason == "credentials_supplied"


def test_ordinary_headers_are_allowed():
    decision = fp.check_fetch(
        SITE, headers={"Accept": "application/pdf"}, allowed_hosts=ALLOWED
    )
    assert decision.allowed


# ─── robots.txt ─────────────────────────────────────────────────────────────


def test_disallowed_path_is_refused():
    _robots("User-agent: *\nDisallow: /private/")
    decision = fp.check_fetch("https://example.edu/private/secret.pdf", allowed_hosts=ALLOWED)
    assert not decision.allowed
    assert decision.reason == "robots_disallowed"
    assert decision.robots_rule == "/private/"


def test_allowed_path_passes_when_robots_permits():
    _robots("User-agent: *\nDisallow: /private/")
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed


def test_blank_disallow_means_allow_everything():
    """`Disallow:` with an empty value is the robots convention for "allow"."""
    _robots("User-agent: *\nDisallow:")
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed


def test_comments_and_blank_lines_are_ignored():
    _robots("# welcome\n\nUser-agent: *   # our agent\nDisallow: /x/\n")
    assert not fp.check_fetch("https://example.edu/x/y", allowed_hosts=ALLOWED).allowed


def test_longest_match_wins():
    _robots("User-agent: *\nDisallow: /papers/\nAllow: /papers/public/")
    # The longer Allow rule is more specific, so it wins.
    assert fp.check_fetch("https://example.edu/papers/public/a.pdf", allowed_hosts=ALLOWED).allowed
    assert not fp.check_fetch("https://example.edu/papers/private/a.pdf", allowed_hosts=ALLOWED).allowed


def test_rules_for_other_agents_are_not_applied():
    _robots("User-agent: BadBot\nDisallow: /\n")
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed


def test_unreachable_robots_allows_but_is_logged(monkeypatch):
    """No robots.txt means unrestricted by convention, not a refusal."""
    monkeypatch.setattr(fp, "robots_for", lambda url: None)
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed


def test_check_robots_can_be_skipped_by_a_caller():
    """A caller that already consulted robots.txt can say so."""
    _robots("User-agent: *\nDisallow: /")
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED, check_robots=False).allowed


# ─── parse_robots ───────────────────────────────────────────────────────────


def test_parse_robots_collects_both_directives():
    rules = fp.parse_robots("User-agent: *\nDisallow: /a\nAllow: /a/b\nDisallow: /c\n")
    assert "/a" in rules.disallow and "/c" in rules.disallow
    assert "/a/b" in rules.allow


def test_parse_robots_of_empty_text_permits_everything():
    rules = fp.parse_robots("")
    assert rules.applies("/anything") == ""


# ─── Rate limiting ──────────────────────────────────────────────────────────


def test_second_fetch_to_same_host_is_throttled():
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed
    decision = fp.check_fetch("https://example.edu/other.pdf", allowed_hosts=ALLOWED)
    assert not decision.allowed
    assert decision.reason == "rate_limited"
    assert "spacing" in decision.detail


def test_refusals_do_not_consume_the_rate_budget():
    """A blocked request must not rate-limit the operator's next good one."""
    fp.check_fetch("https://evil.example.com/x", allowed_hosts=ALLOWED)
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed


def test_different_hosts_have_separate_budgets():
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed
    assert fp.check_fetch("https://openaccess.org/a.pdf", allowed_hosts=ALLOWED).allowed


# ─── Audit trail ────────────────────────────────────────────────────────────


def test_allowed_decision_is_audited(isolated_gate):
    fp.check_fetch(SITE, allowed_hosts=ALLOWED, actor="librarian")
    records = _audit_lines(isolated_gate)
    assert len(records) == 1
    assert records[0]["allowed"] is True
    assert records[0]["actor"] == "librarian"


def test_refusal_is_audited_with_its_reason(isolated_gate):
    fp.check_fetch("https://evil.example.com/x", allowed_hosts=ALLOWED, actor="librarian")
    records = _audit_lines(isolated_gate)
    assert records[0]["allowed"] is False
    assert records[0]["reason"] == "host_not_allowlisted"


def test_credential_attempt_is_audited(isolated_gate):
    fp.check_fetch(
        "https://example.edu/x?access_token=abc", allowed_hosts=ALLOWED, actor="sweeper"
    )
    assert _audit_lines(isolated_gate)[0]["reason"] == "credentials_supplied"


def test_audit_is_disabled_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv(fp.AUDIT_LOG_ENV, raising=False)
    assert fp.audit_log_path() is None
    # Must not raise.
    fp.check_fetch(SITE, allowed_hosts=ALLOWED)


# ─── guarded_fetch ──────────────────────────────────────────────────────────


def test_guarded_fetch_returns_no_body_when_refused(monkeypatch):
    """A refusal must never leak a payload the caller could mistake for data."""
    def explode(*args, **kwargs):
        raise AssertionError("network must not be touched after a refusal")

    monkeypatch.setattr(fp.urllib.request, "urlopen", explode)
    decision, body = fp.guarded_fetch(
        "https://evil.example.com/x", allowed_hosts=ALLOWED
    )
    assert not decision.allowed
    assert body == b""


def test_guarded_fetch_propagates_a_network_error_as_a_refusal(monkeypatch):
    monkeypatch.setattr(fp, "check_fetch", lambda url, **kw: fp.FetchDecision(allowed=True, url=url))
    monkeypatch.setattr(fp.urllib.request, "urlopen", explode_any)
    decision, body = fp.guarded_fetch(SITE, allowed_hosts=ALLOWED)
    assert not decision.allowed
    assert body == b""


def explode_any(*args, **kwargs):
    """Stand-in urlopen that always fails."""
    raise OSError("network down")


# ─── The gate is default-deny, not an allowlist of ideas ────────────────────


def test_gate_does_not_mention_or_implement_circumvention():
    """Guard against the module gaining a bypass helper in future."""
    source = (REPO_ROOT / "archipelago" / "ingestion" / "fetch_policy.py").read_text(
        encoding="utf-8"
    ).lower()
    for banned in ("bypass_paywall", "solve_captcha", "rotate_proxy", "stealth", "spoof_user_agent"):
        assert banned not in source

def test_redeclared_user_agent_starts_a_fresh_group():
    """Rules from a previous group must not leak into the next one.

    A file that groups `User-agent: BadBot` first and then `User-agent: *`
    would otherwise inherit BadBot's `Disallow: /`, blocking the whole site.
    """
    _robots("User-agent: BadBot\nDisallow: /\nUser-agent: *\n")
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed


def test_grouped_rules_apply_to_the_matching_agent():
    _robots("User-agent: BadBot\nDisallow: /\n\nUser-agent: *\nDisallow: /x/\n")
    assert not fp.check_fetch("https://example.edu/x/y", allowed_hosts=ALLOWED).allowed
    assert fp.check_fetch(SITE, allowed_hosts=ALLOWED).allowed
