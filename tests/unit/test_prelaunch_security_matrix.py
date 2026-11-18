"""Pre-launch security regression matrix (Phase 8/9 + graceful shutdown).

Covers, without network access:

* sessions: JWT ``alg=none`` rejection, idle timeout that background polls do
  not reset, absolute lifetime, logout revocation, cookie attributes;
* cross-origin handoff: single-use, origin-bound, staff-only, no refresh token;
* request policy: CSRF rejection, CORS allowlist, private cache headers,
  dotfile/AUDIT.md blocking, open-redirect validation;
* research isolation and Excel export: owner scoping, export headers, formula
  neutralisation while numeric metrics and sheet schema stay unchanged;
* graceful shutdown in both Vercel apps: drain, 503 + ``Retry-After``,
  callbacks run once, and SIGTERM still terminates the process.
"""

from __future__ import annotations

import base64
from io import BytesIO
import importlib
import json
from pathlib import Path
import subprocess
import sys
import textwrap
import threading
import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "host_inference"
HOST_RES = ROOT / "host_research"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

STAFF_ORIGIN = "https://archipelago-librarian.vercel.app"
EVIL_ORIGIN = "https://evil.example"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def hosted_app(monkeypatch):
    """The hosted Flask app with a tiny fake engine (same shape as other suites)."""
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    import engine as hosted_engine

    class Graph:
        nodes = {"graph_retrieval": {"summary": "Retrieval over a graph."}}  # noqa: RUF012
        out = {}  # noqa: RUF012
        inn = {}  # noqa: RUF012

        def rank(self, query, top_k=1):
            return [(0.9, "graph_retrieval")]

        def label(self, node_id):
            return node_id.replace("_", " ").title()

    fake_engine = SimpleNamespace(graph=Graph(), books=[], cache_info={"source": "test"})
    monkeypatch.setattr(hosted_engine, "Engine", lambda: fake_engine)
    import hostapp.corpus_bootstrap as corpus_bootstrap
    import hostapp.factory as host_factory

    monkeypatch.setattr(corpus_bootstrap, "provision", lambda *a, **kw: {"status": "test"})
    monkeypatch.setattr(host_factory, "provision", lambda *a, **kw: {"status": "test"})
    sys.modules.pop("server", None)
    server = importlib.import_module("server")
    ctx = server.app.extensions["archipelago"]
    monkeypatch.setattr(ctx.limiter, "check_api", lambda: (False, 0))
    monkeypatch.setattr(ctx.limiter, "check_chat", lambda: (False, 0))
    if hasattr(ctx.limiter, "check_auth"):
        monkeypatch.setattr(ctx.limiter, "check_auth", lambda: (False, 0))
    yield server
    sys.modules.pop("server", None)


@pytest.fixture
def as_user(hosted_app, monkeypatch):
    """Switch the verified server principal: ``as_user("user-a", "faculty")``."""
    ctx = hosted_app.app.extensions["archipelago"]
    current: dict = {"p": None}
    monkeypatch.setattr(ctx.auth, "principal", lambda: (current["p"], None if current["p"] else "no session"))

    def switch(user_id: str | None, role: str = "faculty", token: str = "tok-test") -> None:
        current["p"] = None if user_id is None else {"id": user_id, "role": role, "username": user_id, "token": token}

    return switch


@pytest.fixture
def guard(monkeypatch):
    """A fresh AuthGuard with Supabase 'configured' and auth required."""
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    from hostapp.security import AuthGuard

    return AuthGuard()


@pytest.fixture
def isolated_shutdown(monkeypatch):
    """Isolate the hosted shutdown registry so real module cleanups never run."""
    from hostapp import runtime_state

    monkeypatch.setattr(runtime_state, "_SHUTDOWN_CALLBACKS", [])
    runtime_state.reset_shutdown_state()
    yield runtime_state
    runtime_state.reset_shutdown_state()


@pytest.fixture
def transport(monkeypatch):
    """The host_research Vercel app loaded from its own deployment root."""
    monkeypatch.syspath_prepend(str(HOST_RES))
    for name in ("app", "discovery", "storage"):
        sys.modules.pop(name, None)
    module = importlib.import_module("app")
    module.app.config["TESTING"] = True
    monkeypatch.setattr(module, "_SHUTDOWN_CALLBACKS", [])
    module.reset_shutdown_state()
    yield module
    module.reset_shutdown_state()
    for name in ("app", "discovery", "storage"):
        sys.modules.pop(name, None)


def _jwt(alg: str, signature: str = "sig") -> str:
    enc = lambda obj: base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': alg, 'typ': 'JWT'})}.{enc({'sub': 'u1'})}.{signature}"


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #


def test_unsigned_and_malformed_tokens_are_rejected_before_network():
    from hostapp.security import _is_rejected_jwt_or_token

    assert _is_rejected_jwt_or_token(_jwt("none"))
    assert _is_rejected_jwt_or_token(_jwt("HS256", signature=""))
    assert _is_rejected_jwt_or_token("eyJfoo.bar")  # truncated JWT shape
    assert _is_rejected_jwt_or_token("a.b.c")  # invalid JWT header
    assert _is_rejected_jwt_or_token("tok with space")
    assert _is_rejected_jwt_or_token("x" * 5000)
    assert not _is_rejected_jwt_or_token(_jwt("HS256"))


def _seed_session(guard, token: str, principal: dict, at: float) -> str:
    import hashlib

    tid = hashlib.sha256(token.encode()).hexdigest()
    guard._principal_cache[tid] = (dict(principal), at)
    guard._last_activity[tid] = at
    guard._session_started[tid] = at
    return tid


def test_background_poll_does_not_reset_idle_timeout(guard, monkeypatch):
    from flask import Flask

    from hostapp import security

    clock = {"t": 1000.0}
    monkeypatch.setattr(security.time, "monotonic", lambda: clock["t"])
    monkeypatch.setenv("ARCHIPELAGO_IDLE_TIMEOUT_SECONDS", "300")
    token = "opaque-session-token"
    principal = {"id": "user-a", "role": "faculty", "username": "a", "token": token}
    tid = _seed_session(guard, token, principal, clock["t"])
    app = Flask(__name__)
    auth = {"Authorization": f"Bearer {token}"}

    clock["t"] = 1200.0
    guard._principal_cache[tid] = (principal, clock["t"])  # keep cache warm (no network)
    with app.test_request_context("/api/research/jobs/1", headers={**auth, "X-Background-Poll": "1"}):
        assert guard.principal()[0] is not None
    assert guard._last_activity[tid] == 1000.0, "background poll reset the idle timer"

    clock["t"] = 1301.0
    guard._principal_cache[tid] = (principal, clock["t"])
    with app.test_request_context("/api/research/jobs/1", headers={**auth, "X-Background-Poll": "1"}):
        result, error = guard.principal()
    assert result is None and error, "idle session survived on background polls alone"


def test_interactive_request_extends_idle_but_absolute_lifetime_wins(guard, monkeypatch):
    from flask import Flask

    from hostapp import security

    clock = {"t": 0.0}
    monkeypatch.setattr(security.time, "monotonic", lambda: clock["t"])
    monkeypatch.setenv("ARCHIPELAGO_IDLE_TIMEOUT_SECONDS", "300")
    monkeypatch.setenv("ARCHIPELAGO_SESSION_MAX_AGE_SECONDS", "900")
    token = "opaque-session-token-2"
    principal = {"id": "user-a", "role": "faculty", "username": "a", "token": token}
    tid = _seed_session(guard, token, principal, 0.0)
    app = Flask(__name__)
    for t in (250.0, 500.0, 750.0):  # interactive activity every 250s keeps it alive
        clock["t"] = t
        guard._principal_cache[tid] = (principal, t)
        with app.test_request_context("/api/x", headers={"Authorization": f"Bearer {token}"}):
            assert guard.principal()[0] is not None
    clock["t"] = 901.0
    guard._principal_cache[tid] = (principal, 901.0)
    with app.test_request_context("/api/x", headers={"Authorization": f"Bearer {token}"}):
        assert guard.principal()[0] is None, "absolute session lifetime not enforced"


def test_logout_revokes_token_for_every_guard_in_process(guard):
    from hostapp.security import AuthGuard

    other_instance = AuthGuard()
    guard.end_session("tok-logout")
    assert guard.is_revoked("tok-logout")
    assert other_instance.is_revoked("tok-logout")
    assert not other_instance.is_revoked("tok-still-valid")


def test_logout_route_clears_cookies_and_site_data(hosted_app):
    client = hosted_app.app.test_client()
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.headers.get("Clear-Site-Data") == '"cookies", "storage"'
    assert "no-store" in resp.headers.get("Cache-Control", "")
    cookies = resp.headers.getlist("Set-Cookie")
    session_cookie = next(c for c in cookies if c.startswith("archipelago_token="))
    assert "Max-Age=0" in session_cookie or "expires=Thu, 01 Jan 1970" in session_cookie
    assert "HttpOnly" in session_cookie


def test_session_cookie_is_httponly_secure_lax(hosted_app, as_user, monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_ENV", "production")
    as_user("user-a", "faculty", token="tok-cookie")
    resp = hosted_app.app.test_client().post("/api/auth/session", json={})
    assert resp.status_code == 200
    cookie = next(c for c in resp.headers.getlist("Set-Cookie") if c.startswith("archipelago_token="))
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie
    assert "no-store" in resp.headers["Cache-Control"]


def test_login_with_external_redirect_is_rejected(hosted_app, as_user):
    as_user("user-a")
    client = hosted_app.app.test_client()
    for target in ("//evil.example", "https://evil.example/x", "/\\evil.example", "javascript:alert(1)"):
        assert client.post("/api/auth/session", json={"next": target}).status_code == 400, target
    assert client.post("/api/auth/session", json={"next": "/research/papers"}).status_code == 200


@pytest.mark.parametrize(
    ("target", "safe"),
    [
        ("/chat", True),
        ("/research/papers?run=1", True),
        ("//evil.example", False),
        ("/\\evil.example", False),
        ("https://evil.example", False),
        ("javascript:alert(1)", False),
        (" /chat", False),
        ("/chat\nSet-Cookie: x", False),
        ("https://user:pw@archipelago-librarian.vercel.app/", False),
        ("https://archipelago-librarian.vercel.app/research", True),
    ],
)
def test_redirect_validation(target, safe):
    from hostapp.security import is_safe_redirect_target

    assert is_safe_redirect_target(target, (STAFF_ORIGIN,)) is safe


# --------------------------------------------------------------------------- #
# Cross-origin session handoff
# --------------------------------------------------------------------------- #

STAFF = {"id": "staff-1", "role": "faculty", "username": "f", "token": "tok-staff"}


def test_handoff_ticket_is_single_use_origin_bound_and_carries_no_refresh_token(guard):
    issued, err = guard.issue_handoff_ticket(STAFF, STAFF_ORIGIN, nonce="n" * 24)
    assert err is None and issued is not None
    assert "refresh_token" not in json.dumps(issued)
    assert issued["expires_in"] <= 60
    principal, err = guard.redeem_handoff_ticket(issued["ticket"], origin=STAFF_ORIGIN, nonce="n" * 24)
    assert err is None and principal["id"] == "staff-1"
    assert "refresh_token" not in principal
    replay, err = guard.redeem_handoff_ticket(issued["ticket"], origin=STAFF_ORIGIN, nonce="n" * 24)
    assert replay is None and err


def test_handoff_rejects_wrong_origin_nonce_role_and_revoked_session(guard):
    ticket = guard.issue_handoff_ticket(STAFF, STAFF_ORIGIN, nonce="abc")[0]["ticket"]
    assert guard.redeem_handoff_ticket(ticket, origin=EVIL_ORIGIN, nonce="abc")[0] is None
    # A failed attempt still burns the ticket (no oracle for retries).
    assert guard.redeem_handoff_ticket(ticket, origin=STAFF_ORIGIN, nonce="abc")[0] is None

    ticket = guard.issue_handoff_ticket(STAFF, STAFF_ORIGIN, nonce="abc")[0]["ticket"]
    assert guard.redeem_handoff_ticket(ticket, origin=STAFF_ORIGIN, nonce="zzz")[0] is None

    assert guard.issue_handoff_ticket(STAFF, EVIL_ORIGIN)[0] is None
    assert guard.issue_handoff_ticket({**STAFF, "role": "student"}, STAFF_ORIGIN)[0] is None

    ticket = guard.issue_handoff_ticket(STAFF, STAFF_ORIGIN)[0]["ticket"]
    guard.end_session(STAFF["token"])
    assert guard.redeem_handoff_ticket(ticket, origin=STAFF_ORIGIN)[0] is None


def test_handoff_ticket_expires(guard, monkeypatch):
    from hostapp import security

    clock = {"t": 0.0}
    monkeypatch.setattr(security.time, "monotonic", lambda: clock["t"])
    ticket = guard.issue_handoff_ticket(STAFF, STAFF_ORIGIN)[0]["ticket"]
    clock["t"] = 61.0
    assert guard.redeem_handoff_ticket(ticket, origin=STAFF_ORIGIN)[0] is None


def test_handoff_ticket_route_requires_staff_and_redeems_cookie_only(hosted_app, as_user):
    client = hosted_app.app.test_client()
    as_user(None)
    assert client.post("/api/auth/handoff-ticket", json={"target_origin": STAFF_ORIGIN}).status_code == 401
    as_user("stu-1", "student")
    assert client.post("/api/auth/handoff-ticket", json={"target_origin": STAFF_ORIGIN}).status_code == 403
    as_user("staff-1", "faculty", token="tok-route")
    resp = client.post("/api/auth/handoff-ticket", json={"target_origin": STAFF_ORIGIN, "state": "s" * 24})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "refresh_token" not in resp.get_data(as_text=True)
    assert "no-store" in resp.headers["Cache-Control"]

    # Empty Origin fails closed; matching Origin redeems into an HttpOnly cookie with no tokens in JSON.
    bad_empty = client.post("/api/auth/handoff-redeem", json={"ticket": data["ticket"], "state": "s" * 24})
    assert bad_empty.status_code == 401

    resp2 = client.post("/api/auth/handoff-ticket", json={"target_origin": STAFF_ORIGIN, "state": "s" * 24})
    ticket2 = resp2.get_json()["ticket"]
    redeem = client.post(
        "/api/auth/handoff-redeem",
        json={"ticket": ticket2, "state": "s" * 24},
        headers={"Origin": STAFF_ORIGIN},
    )
    assert redeem.status_code == 200
    redeemed_json = redeem.get_json()
    assert redeemed_json["authenticated"] is True
    assert "access_token" not in redeemed_json
    assert "refresh_token" not in redeemed_json
    cookie = next(c for c in redeem.headers.getlist("Set-Cookie") if c.startswith("archipelago_token="))
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    # Replay is rejected.
    replay = client.post(
        "/api/auth/handoff-redeem",
        json={"ticket": ticket2, "state": "s" * 24},
        headers={"Origin": STAFF_ORIGIN},
    )
    assert replay.status_code == 401


def test_bridge_pages_never_post_a_refresh_token():
    """Static guard: the raw Supabase refresh token must not cross windows."""
    for path in (HOST / "ui" / "session-bridge.html", HOST_RES / "ui" / "signin.js"):
        code_lines = [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if "refresh_token" in line and not line.strip().startswith("//")
        ]
        assert not code_lines, f"{path.name} still handles refresh_token: {code_lines}"


# --------------------------------------------------------------------------- #
# Request policy: CSRF, CORS, cache, static exposure
# --------------------------------------------------------------------------- #


def test_untrusted_origin_mutation_is_rejected(hosted_app, as_user):
    as_user("user-a")
    client = hosted_app.app.test_client()
    for method in ("post", "patch", "delete"):
        resp = getattr(client, method)(
            "/api/research/intelligence/monitors", json={}, headers={"Origin": EVIL_ORIGIN}
        )
        assert resp.status_code == 403, method
    resp = client.post("/api/chat/history", headers={"Referer": f"{EVIL_ORIGIN}/page"})
    assert resp.status_code == 403
    resp = client.post("/api/chat/history", headers={"Sec-Fetch-Site": "cross-site"})
    assert resp.status_code == 403


def test_cookie_authenticated_mutation_needs_csrf_proof(hosted_app, as_user):
    as_user("user-a", "faculty", token="tok-cookie-csrf")
    ctx = hosted_app.app.extensions["archipelago"]
    client = hosted_app.app.test_client()
    client.set_cookie("archipelago_token", "tok-cookie-csrf")
    path = "/api/research/intelligence/monitors"
    assert client.post(path, json={"topic": "graphs"}).status_code == 403
    bad = client.post(path, json={"topic": "graphs"}, headers={"X-CSRF-Token": "forged"})
    assert bad.status_code == 403
    good_token = ctx.auth.csrf_token_for("tok-cookie-csrf")
    ok = client.post(path, json={"topic": "graphs"}, headers={"X-CSRF-Token": good_token})
    assert ok.status_code != 403 or "CSRF" not in ok.get_data(as_text=True)


def test_cors_only_echoes_allowlisted_origins(hosted_app):
    client = hosted_app.app.test_client()
    evil = client.get("/api/auth/config", headers={"Origin": EVIL_ORIGIN})
    assert "Access-Control-Allow-Origin" not in evil.headers
    good = client.get("/api/auth/config", headers={"Origin": "https://archipelago.antideploy.com"})
    assert good.headers["Access-Control-Allow-Origin"] == "https://archipelago.antideploy.com"
    assert good.headers["Access-Control-Allow-Credentials"] == "true"
    assert "Origin" in good.headers.get("Vary", "")
    for resp in (evil, good):
        assert resp.headers.get("Access-Control-Allow-Origin") != "*"


def test_security_headers_and_private_cache_on_api(hosted_app, as_user):
    as_user("user-a")
    resp = hosted_app.app.test_client().get("/api/research/intelligence/runs")
    for header in (
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "Referrer-Policy",
        "Permissions-Policy",
    ):
        assert header in resp.headers
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "private" in resp.headers["Cache-Control"] and "no-store" in resp.headers["Cache-Control"]


@pytest.mark.parametrize(
    "path",
    ["/.env", "/.git/config", "/AUDIT.md", "/ui/index.html.stripped_backup_20260729", "/x/../.env", "/cache.sqlite3"],
)
def test_dotfiles_backups_and_audit_are_not_served(hosted_app, path):
    assert hosted_app.app.test_client().get(path).status_code == 404


def test_unauthenticated_research_access_is_401(hosted_app, as_user):
    as_user(None)
    client = hosted_app.app.test_client()
    for path in (
        "/api/research/intelligence/runs",
        "/api/research/intelligence/runs/00000000-0000-0000-0000-000000000001/xlsx",
        "/api/research/intelligence/monitors",
    ):
        assert client.get(path).status_code == 401, path


# --------------------------------------------------------------------------- #
# Research isolation + Excel export (Phase 4/5)
# --------------------------------------------------------------------------- #


def _saved_run(tmp_path, owner: str, title: str) -> str:
    from archipelago.scholarly.contracts.okf_models import PaperAuthor, PaperIdentifiers, PaperRecord, ProvenancePointer
    from archipelago.scholarly.intelligence.search import discover
    from archipelago.scholarly.intelligence.storage import ResearchStore

    class Fake:
        def discover_with_status(self, query, limit):
            paper = PaperRecord(
                paper_id="paper-one",
                title="Graph neural networks for molecules",
                abstract="Graph neural networks represent molecular structures.",
                identifiers=PaperIdentifiers(doi="10.1000/example", openalex_id="https://openalex.org/W1"),
                authors=[PaperAuthor(name="A Researcher")],
                venue="Journal of Graphs",
                publication_date="2025-01-01",
                is_open_access=True,
            )
            prov = ProvenancePointer(source_type="openalex", artifact_sha256="a" * 64, source_url="https://openalex.org/W1")
            return (
                [{"paper": paper, "source": "openalex", "provenance": prov, "citation_count": 7, "source_metadata": {}}],
                [{"source": "openalex", "status": "live", "record_count": 1}],
            )

    run = discover({"topic": "graph neural networks", "top_k": 1}, Fake())
    run["papers"][0]["title"] = title
    return ResearchStore(tmp_path / "research.sqlite3").save_run(owner, run)


def test_excel_export_is_owner_scoped_private_and_formula_safe(hosted_app, as_user, monkeypatch, tmp_path):
    from openpyxl import load_workbook

    from archipelago.scholarly.intelligence.workbook import HEADERS

    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_DB", str(tmp_path / "research.sqlite3"))
    malicious = '=HYPERLINK("https://evil.example","x")'
    run_id = _saved_run(tmp_path, "user-a", malicious)
    client = hosted_app.app.test_client()

    as_user("user-a")
    resp_std = client.get(f"/api/research/intelligence/runs/{run_id}/xlsx")
    assert resp_std.status_code == 200
    assert resp_std.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert resp_std.headers.get("X-Archipelago-Export-Schema") == "paper-venue-v2"
    assert "private" in resp_std.headers["Cache-Control"] and "no-store" in resp_std.headers["Cache-Control"]
    assert "Authorization" in resp_std.headers.get("Vary", "") and "Cookie" in resp_std.headers.get("Vary", "")
    assert "attachment" in resp_std.headers["Content-Disposition"]
    std_book = load_workbook(BytesIO(resp_std.data))
    assert std_book.sheetnames == ["Start Here", "Papers", "Authors", "Sources"], "standard sheet schema changed"
    std_papers = std_book["Papers"]
    std_headers = {c.value: i for i, c in enumerate(std_papers[1], 1)}
    assert std_papers.cell(2, std_headers["Paper Title"]).value == "'" + malicious

    resp = client.get(f"/api/research/intelligence/runs/{run_id}/xlsx?mode=advanced")
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "private" in resp.headers["Cache-Control"] and "no-store" in resp.headers["Cache-Control"]
    assert "Authorization" in resp.headers.get("Vary", "") and "Cookie" in resp.headers.get("Vary", "")
    assert "attachment" in resp.headers["Content-Disposition"]

    book = load_workbook(BytesIO(resp.data))
    assert book.sheetnames == list(HEADERS), "sheet schema changed"
    papers = book["Papers"]
    assert [c.value for c in papers[1]] == HEADERS["Papers"], "column schema changed"
    col = {c.value: i for i, c in enumerate(papers[1], 1)}
    title_cell = papers.cell(2, col["Title"])
    assert title_cell.data_type == "s" and title_cell.value == "'" + malicious
    assert papers.cell(2, col["Year"]).value == 2025, "numeric metric altered"
    assert papers.cell(2, col["Citations"]).value == 7, "numeric metric altered"

    as_user("user-b")
    for suffix in ("", "/graph", "/xlsx"):
        assert client.get(f"/api/research/intelligence/runs/{run_id}{suffix}").status_code == 404
    assert client.get("/api/research/intelligence/runs").get_json()["runs"] == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("+SUM(A1)", "'+SUM(A1)"),
        ("-2+3", "'-2+3"),
        ("@cmd", "'@cmd"),
        ("\t=cmd", "'\t=cmd"),
        ("\r=cmd", "'\r=cmd"),
        ("  =cmd", "'  =cmd"),
        ("Graph networks", "Graph networks"),
        (7, 7),
        (3.5, 3.5),
        (None, None),
        (True, True),
    ],
)
def test_workbook_cell_guard(raw, expected):
    from hostapp.routes.research_intelligence import _safe_workbook_cell

    assert _safe_workbook_cell(raw) == expected


# --------------------------------------------------------------------------- #
# Graceful shutdown — host_inference
# --------------------------------------------------------------------------- #


def test_shutdown_drains_in_flight_then_runs_callbacks_once(isolated_shutdown):
    rs = isolated_shutdown
    calls: list[str] = []
    rs.register_shutdown_callback(lambda: calls.append("flush"))
    rs.register_shutdown_callback(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert rs.begin_request()
    result: dict = {}
    worker = threading.Thread(target=lambda: result.update(rs.initiate_shutdown(drain_timeout=3.0)))
    worker.start()
    time.sleep(0.2)
    assert rs.is_shutting_down()
    assert worker.is_alive(), "shutdown did not wait for the in-flight request"
    assert calls == [], "callbacks ran before drain"
    assert rs.begin_request() is False, "new request admitted while draining"
    rs.end_request()
    worker.join(2.0)
    assert not worker.is_alive()
    assert result["drained"] is True and result["in_flight"] == 0
    assert calls == ["flush"] and result["callback_errors"] == 1
    rs.initiate_shutdown(drain_timeout=0)
    assert calls == ["flush"], "callbacks ran twice"


def test_shutdown_drain_times_out(isolated_shutdown):
    rs = isolated_shutdown
    assert rs.begin_request()
    start = time.monotonic()
    result = rs.initiate_shutdown(drain_timeout=0.3)
    assert time.monotonic() - start < 2.0
    assert result["drained"] is False and result["in_flight"] == 1


def test_draining_app_returns_503_with_retry_after(hosted_app, isolated_shutdown):
    client = hosted_app.app.test_client()
    assert client.get("/api/auth/config").status_code == 200
    isolated_shutdown.initiate_shutdown(drain_timeout=0)
    resp = client.get("/api/auth/config")
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "5"
    assert resp.get_json()["status"] == "shutting_down"
    health = client.get("/api/health")
    assert health.status_code == 503 and health.get_json()["status"] == "shutting_down"
    isolated_shutdown.reset_shutdown_state()
    assert client.get("/api/auth/config").status_code == 200
    assert isolated_shutdown.in_flight_requests() == 0, "in-flight counter leaked"


def _sigterm_exits(script: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_sigterm_still_terminates_host_inference_process():
    result = _sigterm_exits(
        """
        import os, signal, sys, time
        sys.path.insert(0, ".")
        from hostapp.runtime_state import install_shutdown_handlers
        install_shutdown_handlers()
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(2)
        print("STILL_ALIVE")
        """,
        HOST,
    )
    assert "STILL_ALIVE" not in result.stdout, "SIGTERM was swallowed; process would never exit"


# --------------------------------------------------------------------------- #
# Graceful shutdown + session controls — host_research
# --------------------------------------------------------------------------- #


def test_research_transport_drains_with_503(transport):
    client = transport.app.test_client()
    transport.initiate_shutdown(drain_timeout=0)
    ready = client.get("/api/readiness")
    assert ready.status_code == 503 and ready.get_json()["status"] == "shutting_down"
    other = client.get("/api/auth/config")
    assert other.status_code == 503 and other.headers["Retry-After"] == "5"
    transport.reset_shutdown_state()
    assert client.get("/api/auth/config").status_code == 200
    assert transport.in_flight_requests() == 0


def test_research_transport_logout_and_csrf(transport):
    client = transport.app.test_client()
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.headers["Clear-Site-Data"] == '"cookies", "storage"'
    assert client.post("/api/auth/logout", headers={"Origin": EVIL_ORIGIN}).status_code == 403
    assert client.get("/AUDIT.md").status_code == 404
    assert client.get("/.env").status_code == 404


def test_research_transport_revoked_token_is_refused(transport, monkeypatch):
    storage = importlib.import_module("storage")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "k")
    storage.revoke_token("tok-gone")
    assert storage.verify_user("tok-gone") is None


def test_sigterm_still_terminates_host_research_process():
    result = _sigterm_exits(
        """
        import os, signal, sys, time
        sys.path.insert(0, ".")
        import app
        app.install_signal_handlers(force=True) if hasattr(app, "install_signal_handlers") else None
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(2)
        print("STILL_ALIVE")
        """,
        HOST_RES,
    )
    assert "STILL_ALIVE" not in result.stdout, "SIGTERM was swallowed; process would never exit"


# --------------------------------------------------------------------------- #
# Client IP extraction, log redaction, chat deletion, and proxy forwarding
# --------------------------------------------------------------------------- #


def test_client_ip_prefers_vercel_header_and_rightmost_hop(monkeypatch):
    from flask import Flask

    from hostapp.security import RateLimiter

    app = Flask(__name__)
    monkeypatch.setenv("VERCEL", "1")
    with app.test_request_context(
        "/",
        headers={
            "X-Forwarded-For": "1.2.3.4, 10.0.0.1",
            "X-Vercel-Forwarded-For": "198.51.100.2, 203.0.113.9",
        },
    ):
        assert RateLimiter.client_ip() == "203.0.113.9"

    with app.test_request_context("/", headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.42"}):
        assert RateLimiter.client_ip() == "203.0.113.42"


def test_log_redaction_masks_cookie_and_secret_headers():
    from hostapp.log_redaction import redact

    scrubbed = redact("Authorization: Bearer sk-secret-123 Cookie: archipelago_token=tok_abc; Set-Cookie: session=xyz")
    assert "sk-secret-123" not in scrubbed
    assert "tok_abc" not in scrubbed
    assert "xyz" not in scrubbed


def test_chat_history_deletion_endpoint_requires_auth_and_clears(hosted_app, as_user, monkeypatch):
    from hostapp.routes import chat as chat_routes

    client = hosted_app.app.test_client()
    as_user(None)
    assert client.delete("/api/chat/history").status_code == 401
    as_user("user-del", "student")
    cleared: list[str] = []
    monkeypatch.setattr(
        chat_routes,
        "clear_user_traffic",
        lambda user_id="", session_id=None: cleared.append(user_id) or 1,
    )
    resp = client.delete("/api/chat/history")
    assert resp.status_code == 200
    assert cleared == ["user-del"]


def test_research_transport_forwards_origin_and_set_cookie(transport, monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_ORIGIN", "https://archipelago-blond.vercel.app")
    captured: dict = {}

    class FakeUpstream:
        status_code = 200
        content = b'{"authenticated": true}'
        headers = {
            "Content-Type": "application/json",
            "Set-Cookie": "archipelago_token=tok-123; HttpOnly; Secure; SameSite=Lax; Path=/",
        }

    def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        return FakeUpstream()

    monkeypatch.setattr(transport.requests, "request", fake_request)
    client = transport.app.test_client()
    resp = client.post(
        "/api/auth/handoff-redeem",
        json={"ticket": "t" * 24, "state": "s" * 24},
        headers={"Origin": STAFF_ORIGIN},
    )
    assert resp.status_code == 200
    assert captured["headers"].get("Origin") == STAFF_ORIGIN
    assert any("archipelago_token=tok-123" in c for c in resp.headers.getlist("Set-Cookie"))


# --------------------------------------------------------------------------- #
# Research Preservation Gate (Phase 9)
# --------------------------------------------------------------------------- #


def test_research_pipeline_and_methodology_files_are_unmodified():
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", "archipelago/", "host_inference/archipelago/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "", f"Research core was modified: {result.stdout}"
