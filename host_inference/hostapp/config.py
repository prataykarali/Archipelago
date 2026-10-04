"""Configuration for the hosted Archipelago app.

One concern: every literal the app needs at wiring time — filesystem roots,
public-API policy, rate-limit policy, allowed origins and role sets — as named
constants.  No magic numbers live in the route modules.
"""
from __future__ import annotations

import os
from pathlib import Path

# ``HOST_ROOT`` is the ``host_inference`` directory (this package's parent), so
# the static UI and asset directories sit exactly where they always have.
HOST_ROOT = Path(__file__).resolve().parent.parent
ROOT = HOST_ROOT
UI = ROOT / "ui"
ASSET = ROOT / "ui_assets"

# Reading and asking stay open; staff surfaces remain role-gated.
OPEN_READING_ALLOWED = os.getenv("ARCHIPELAGO_OPEN_READING", "1").strip().lower() not in {
    "0", "false", "no",
}

MAX_CONTENT_LENGTH_BYTES = 5 * 1024 * 1024

# Endpoints reachable without a Supabase session.  Library browsing, the reader
# routes and chat are intentionally public so an exact book/page link never
# bounces a reader to the login page.
PUBLIC_API = frozenset({
    "/api/auth/config",
    "/api/auth/session",
    "/api/health",
    "/api/readiness",
    "/api/library/data",
    "/api/chat",
    "/api/chat/diagnostic-mcqs",
    "/api/chat/adaptive-step",
    "/api/chat/telemetry",
    # Cookie-owned controls contain no other browser's memory or staff data.
    "/api/chat/learning-memory",
    "/api/catalog/all",
    "/api/page-view",
    "/api/graph/subgraph",
    "/api/roadmap",
    "/api/quiz",
})
PUBLIC_API_PREFIXES = ("/api/reader/info/",)

# Ingestion only ever runs on the local library workstation.
INGESTION_PREFIXES = ("/api/ingest", "/api/documents", "/api/manual")

# Rate limiting: chat is stricter than general API traffic.
CHAT_RATE_MAX_PER_MIN = 20
CHAT_RATE_MIN_GAP_SEC = 1.0
API_RATE_MAX_PER_MIN = 120
API_RATE_MIN_GAP_SEC = 0.05
RATE_WINDOW_SEC = 60.0

ALLOWED_ORIGINS = frozenset({
    "https://archipelago.antideploy.com",
    "https://archipelago-2.antideploy.com",
    "https://archipelago3.antideploy.com",
    "http://localhost:5152",
    "http://127.0.0.1:5152",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
})

AUTH_ROLES = frozenset({"student", "faculty", "librarian", "administrator"})
# Roles permitted to open the graph page and import library holdings.
ELEVATED_ROLES = frozenset({"faculty", "librarian", "administrator"})
LIBRARIAN_ROLES = frozenset({"librarian", "administrator"})

PAGE_FILES = {
    "landing": "landing.html",
    "chat": "index.html",
    "library": "library.html",
    "login": "login.html",
}
# Pages that require a session when auth is enabled.
# Reading and asking are open to every campus user, so chat and the library are
# NOT gated — an exact book/page link must never bounce a reader to the login
# page. Elevated surfaces (the graph console, librarian import) stay gated in
# their own routes. Set ARCHIPELAGO_OPEN_READING=0 to restore mandatory
# sessions for these pages.
# Open reading: chat and library are accessible without authentication
AUTH_GATED_PAGES = frozenset()

SESSION_COOKIE_NAME = "archipelago_token"
SESSION_COOKIE_MAX_AGE = 3600

DEFAULT_PORT = "8080"


def load_env() -> None:
    """Load ``host_inference/.env`` into the process environment (best effort).

    Existing environment variables always win, so a deployment can override any
    value from its own configuration.
    """
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


# Loading the environment on import guarantees secrets are present before any
# module that reads them at import time (the cache_service singletons, provider
# configuration).  ``config`` is imported before every other app module.
load_env()
