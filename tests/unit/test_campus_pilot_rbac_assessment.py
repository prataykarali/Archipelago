"""Non-production UEM Kolkata campus pilot RBAC, privacy, and boundary assessment tests.

All tests execute offline against the real hosted Flask application
(``host_inference/hostapp``) wired with lightweight fake collaborators. No live
network calls, no live Koha/Supabase requests, and no repo-root file writes.
"""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any
import uuid

from flask import Flask
import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_INFERENCE = REPO_ROOT / "host_inference"
if str(HOST_INFERENCE) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE))

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_UNAVAILABLE = 503

AUTH_DENIED = frozenset({HTTP_UNAUTHORIZED, HTTP_FORBIDDEN})
TEST_RUN_ID = "11111111-2222-3333-4444-555555555555"
BEARER_HEADERS = {"Authorization": "Bearer verified-session-token"}
DEV_TOKEN_HEADERS = {"Authorization": "Bearer local-dev-token"}


class _FakeGraph:
    """Minimal in-memory graph satisfying hostapp route dependencies."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {
            "operating_systems": {"summary": "Process scheduling and virtual memory."}
        }
        self.out: dict[str, list[tuple[str, str]]] = {}
        self.inn: dict[str, list[tuple[str, str]]] = {}
        self.corpus_source = "test"
        self.graph_version = "test-v1"
        self.last_sync = None

    def rank(self, _query: str, top_k: int = 1) -> list[tuple[float, str]]:
        return [(1.0, "operating_systems")][:top_k]

    def label(self, node_id: str) -> str:
        return node_id.replace("_", " ").title()


class _FakeAuth:
    """Switchable principal stub enforcing AUTH_REQUIRED=1 semantics."""

    def __init__(self) -> None:
        self.current: dict[str, Any] | None = None

    def required(self) -> bool:
        return True

    def supabase(self) -> tuple[str, str]:
        return ("https://example.supabase.co", "pk_test_only")

    def principal(self) -> tuple[dict[str, Any] | None, str | None]:
        if self.current is None:
            return None, "A Supabase session is required."
        return dict(self.current), None

    def verify_csrf_token(self, _token: str, _candidate: str) -> bool:
        return True

    def csrf_token_for(self, _token: str) -> str:
        return "csrf-test-token"

    def issue_handoff_ticket(
        self, principal: dict[str, Any], target_origin: str, nonce: str = ""
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not target_origin:
            return None, "Target origin is required."
        return {
            "ticket": "test-ticket",
            "target_origin": target_origin,
            "expires_in": 60,
            "nonce": nonce,
            "role": principal.get("role"),
        }, None


class _FakeLimiter:
    """No-op rate limiter with deterministic quota responses."""

    def check_api(self) -> tuple[bool, int]:
        return False, 0

    def check_chat(self) -> tuple[bool, int]:
        return False, 0

    def check_auth(self) -> tuple[bool, int]:
        return False, 0

    def quota_status(self, _user_id: str) -> dict[str, Any]:
        return {"limited": False, "limit": 10, "window_seconds": 3600, "used": 1, "remaining": 9}


class _FakeCacheMetrics:
    def stats(self) -> dict[str, int]:
        return {"requests": 0, "hits": 0, "misses": 0}


@pytest.fixture
def assessment_env(monkeypatch: pytest.MonkeyPatch) -> tuple[Flask, _FakeAuth]:
    """Create an isolated hosted Flask app without disk provisioning or network calls."""
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("ARCHIPELAGO_ENV", "production")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("CRON_SECRET", "unit-test-cron-secret")
    monkeypatch.delenv("ARCHIPELAGO_INGESTION_ENABLED", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_RESEARCH_ENABLED", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    from hostapp.context import AppContext
    from hostapp.factory import create_app

    auth = _FakeAuth()
    engine = SimpleNamespace(graph=_FakeGraph(), books=[], cache_info={"source": "test"})
    ctx = AppContext(
        engine=engine,
        auth=auth,
        limiter=_FakeLimiter(),
        inventory=SimpleNamespace(),
        cache_service=SimpleNamespace(),
        cache_metrics=_FakeCacheMetrics(),
        request_dedup=SimpleNamespace(),
    )
    app = create_app(ctx=ctx)
    return app, auth


def _set_role(auth: _FakeAuth, role: str | None, user_id: str = "user-1") -> None:
    if role is None:
        auth.current = None
        return
    auth.current = {
        "id": user_id,
        "role": role,
        "username": f"{role}_tester",
        "token": "verified-session-token",
    }


@pytest.mark.parametrize(
    ("method", "path", "role", "expected_status"),
    [
        # Ingestion routes: LIBRARIAN_ROLES only
        ("POST", "/api/ingest", None, HTTP_UNAUTHORIZED),
        ("POST", "/api/ingest", "student", HTTP_FORBIDDEN),
        ("POST", "/api/ingest", "faculty", HTTP_FORBIDDEN),
        ("POST", "/api/ingest", "librarian", HTTP_UNAVAILABLE),
        ("POST", "/api/ingest", "administrator", HTTP_UNAVAILABLE),
        # Library CSV import: LIBRARIAN_ROLES only
        ("POST", "/api/library/import", None, HTTP_UNAUTHORIZED),
        ("POST", "/api/library/import", "student", HTTP_FORBIDDEN),
        ("POST", "/api/library/import", "faculty", HTTP_FORBIDDEN),
        ("POST", "/api/library/import", "librarian", HTTP_BAD_REQUEST),
        # Librarian records: GET = ELEVATED_ROLES, POST = LIBRARIAN_ROLES
        ("GET", "/api/librarian/catalog", None, HTTP_UNAUTHORIZED),
        ("GET", "/api/librarian/catalog", "student", HTTP_FORBIDDEN),
        ("GET", "/api/librarian/catalog", "faculty", HTTP_OK),
        ("POST", "/api/librarian/catalog", "faculty", HTTP_FORBIDDEN),
        ("POST", "/api/librarian/catalog", "librarian", HTTP_BAD_REQUEST),
        # Analytics & academic automation
        ("GET", "/api/analytics/sources", None, HTTP_UNAUTHORIZED),
        ("GET", "/api/analytics/sources", "student", HTTP_FORBIDDEN),
        ("GET", "/api/analytics/sources", "faculty", HTTP_OK),
        ("POST", "/api/analytics/events", "faculty", HTTP_FORBIDDEN),
        ("GET", "/api/academic-automation/status", "student", HTTP_FORBIDDEN),
        ("GET", "/api/academic-automation/status", "faculty", HTTP_OK),
        ("GET", "/api/academic-automation/review/job-1", "faculty", HTTP_FORBIDDEN),
        ("GET", "/api/academic-automation/review/job-1", "librarian", HTTP_NOT_FOUND),
        # Research intake, graph annotation, monitors, jobs, scholarly snapshot
        ("POST", "/api/research/intake/college", None, HTTP_UNAUTHORIZED),
        ("POST", "/api/research/intake/college", "student", HTTP_FORBIDDEN),
        ("POST", "/api/research/intake/college", "faculty", HTTP_FORBIDDEN),
        ("POST", "/api/research/intake/college", "librarian", HTTP_BAD_REQUEST),
        (
            "GET",
            "/api/research/graph/annotation?concept_id=operating_systems",
            "student",
            HTTP_FORBIDDEN,
        ),
        ("POST", "/api/research/graph/annotation", "faculty", HTTP_FORBIDDEN),
        ("GET", "/api/research/intelligence/monitors", "student", HTTP_FORBIDDEN),
        ("POST", "/api/research/jobs", "student", HTTP_FORBIDDEN),
        ("GET", "/api/scholarly/snapshot", "student", HTTP_FORBIDDEN),
        ("GET", "/api/scholarly/snapshot", "faculty", HTTP_UNAVAILABLE),
        # Cross-origin session handoff: ELEVATED_ROLES only
        ("POST", "/api/auth/handoff-ticket", None, HTTP_UNAUTHORIZED),
        ("POST", "/api/auth/handoff-ticket", "student", HTTP_FORBIDDEN),
        ("POST", "/api/auth/handoff-ticket", "faculty", HTTP_OK),
        # Chat quota & history deletion
        ("GET", "/api/chat/quota", None, HTTP_UNAUTHORIZED),
        ("GET", "/api/chat/quota", "student", HTTP_OK),
        ("GET", "/api/chat/quota", "faculty", HTTP_OK),
        ("DELETE", "/api/chat/history", None, HTTP_UNAUTHORIZED),
        ("DELETE", "/api/chat/history", "student", HTTP_OK),
    ],
)
def test_campus_rbac_matrix_enforcement(
    assessment_env: tuple[Flask, _FakeAuth],
    method: str,
    path: str,
    role: str | None,
    expected_status: int,
) -> None:
    """Verify actual Flask route + middleware RBAC decisions across all 5 roles."""
    app, auth = assessment_env
    _set_role(auth, role)
    client = app.test_client()

    headers = dict(BEARER_HEADERS) if role is not None else {}
    kwargs: dict[str, Any] = {"headers": headers}
    if method == "POST":
        if path == "/api/auth/handoff-ticket":
            kwargs["json"] = {"target_origin": "https://archipelago-librarian.vercel.app"}
        else:
            kwargs["json"] = {}

    response = getattr(client, method.lower())(path, **kwargs)
    assert response.status_code == expected_status, (
        f"{method} {path} as role={role!r} returned {response.status_code}, "
        f"expected {expected_status} (body={response.get_data(as_text=True)[:200]})"
    )


def test_review_route_rejects_local_dev_token(assessment_env: tuple[Flask, _FakeAuth]) -> None:
    """Academic automation review endpoints must reject local-dev-token even for librarians."""
    app, auth = assessment_env
    _set_role(auth, "librarian")
    resp = app.test_client().get("/api/academic-automation/review/job-1", headers=DEV_TOKEN_HEADERS)
    assert resp.status_code == HTTP_FORBIDDEN


def test_cron_endpoints_reject_missing_or_wrong_secret(
    assessment_env: tuple[Flask, _FakeAuth],
) -> None:
    """Scheduled cron routes must reject anonymous or mismatched Bearer secrets."""
    app, _auth = assessment_env
    client = app.test_client()
    for path in ("/api/research/intake/scheduled", "/api/internal/s5-monitor-tick"):
        assert client.get(path).status_code == HTTP_UNAUTHORIZED
        assert (
            client.get(path, headers={"Authorization": "Bearer wrong-secret"}).status_code
            == HTTP_UNAUTHORIZED
        )


def test_authenticated_api_responses_carry_private_no_store_headers(
    assessment_env: tuple[Flask, _FakeAuth],
) -> None:
    """Authenticated API responses must never be cacheable by shared campus proxies."""
    app, auth = assessment_env
    _set_role(auth, "student")
    resp = app.test_client().get("/api/chat/quota", headers=BEARER_HEADERS)
    assert resp.status_code == HTTP_OK
    cache_control = resp.headers.get("Cache-Control", "").lower()
    assert "private" in cache_control and "no-store" in cache_control


def test_user_traffic_scrubs_emails_and_bearer_tokens() -> None:
    """Telemetry detail scrubber must redact emails and credential tokens."""
    from hostapp.user_traffic import _scrub_detail

    raw = "student alice@uem.edu.in sent Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig and sk-1234567890abcdef"
    scrubbed = _scrub_detail(raw)
    assert "alice@uem.edu.in" not in scrubbed
    assert "eyJhbGciOiJIUzI1NiJ9" not in scrubbed
    assert "sk-1234567890abcdef" not in scrubbed


def test_pearson_public_book_never_exposes_subscription_id() -> None:
    """Browser-facing Pearson shelf payloads must strip subscription_id and route via /open/."""
    from remote_cache import public_book

    payload = public_book(
        {
            "id": "book-42",
            "title": "Operating System Concepts",
            "subscription_id": "SECRET-SUB-999",
            "page_count": 900,
        }
    )
    assert "subscription_id" not in payload
    assert "SECRET-SUB-999" not in str(payload)
    assert payload["open_url"] == "/open/book-42?page=1"


def test_koha_opac_url_and_bib_validation_blocks_off_host_ssrf() -> None:
    """Koha OPAC bridge must restrict fetches to HTTPS uemk-opac.l2c2.co.in public paths."""
    from hostapp.koha_bridge import _opac_book_id, _valid_opac_url

    assert _valid_opac_url(
        "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=588"
    )
    assert not _valid_opac_url(
        "http://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=588"
    )
    assert not _valid_opac_url("https://evil.example/cgi-bin/koha/opac-detail.pl?biblionumber=588")
    assert not _valid_opac_url("https://uemk-opac.l2c2.co.in/cgi-bin/koha/staff-admin.pl")
    assert (
        _opac_book_id("https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=588")
        == "588"
    )
    assert (
        _opac_book_id(
            "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=588;drop"
        )
        == ""
    )


@pytest.mark.xfail(
    strict=True,
    reason="Verified P0-1 defect: middleware.py:257 guards /papers/ but omits /pdfs/ alias from reader.py:177",
)
def test_p0_1_pdfs_alias_must_require_auth(assessment_env: tuple[Flask, _FakeAuth]) -> None:
    """Anonymous requests to /pdfs/<doc_path> must return 401 when ARCHIPELAGO_AUTH_REQUIRED=1."""
    app, auth = assessment_env
    _set_role(auth, None)
    resp = app.test_client().get("/pdfs/sample_nonexistent.pdf")
    assert resp.status_code == HTTP_UNAUTHORIZED


@pytest.mark.xfail(
    strict=True,
    reason="Verified P0-1 defect: middleware.py:257 checks exact path=='/read', omitting /read/<subpath> (reader.py:117)",
)
def test_p0_1_read_subpath_must_require_auth(assessment_env: tuple[Flask, _FakeAuth]) -> None:
    """Anonymous requests to /read/<subpath> must return 401 when ARCHIPELAGO_AUTH_REQUIRED=1."""
    app, auth = assessment_env
    _set_role(auth, None)
    resp = app.test_client().get("/read/book-42")
    assert resp.status_code == HTTP_UNAUTHORIZED


@pytest.mark.xfail(
    strict=True,
    reason="Verified P0-2 IDOR defect: research_intelligence.py:345 falls back to manager=True on dossier lookup",
)
def test_p0_2_research_dossier_must_enforce_owner_scoping(
    assessment_env: tuple[Flask, _FakeAuth],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Student B must receive 404 (not 200) when requesting Student A's research run dossier."""
    from archipelago.scholarly.intelligence import storage as intel_storage

    owner_run: dict[str, Any] = {
        "run_id": TEST_RUN_ID,
        "topic": "Private Student A Thesis Topic",
        "options": {"topic": "Private Student A Thesis Topic"},
        "retrieved_at": "2026-11-23T00:00:00Z",
        "papers": [],
        "sources": [],
    }

    class _FakeStore:
        def get_run(
            self, run_id: str, owner_id: str | None = None, *, manager: bool = False
        ) -> dict[str, Any] | None:
            if run_id != str(uuid.UUID(TEST_RUN_ID)):
                return None
            if manager or owner_id == "student-a":
                return owner_run
            return None

    monkeypatch.setattr(intel_storage, "durable_storage_configured", lambda: True)
    monkeypatch.setattr(intel_storage, "hosted_store", lambda: _FakeStore())

    app, auth = assessment_env
    _set_role(auth, "student", user_id="student-b")
    resp = app.test_client().get(
        f"/api/research/intelligence/runs/{TEST_RUN_ID}/dossier",
        headers=BEARER_HEADERS,
    )
    assert resp.status_code == HTTP_NOT_FOUND
