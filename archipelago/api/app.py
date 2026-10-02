"""
Production REST & SSE Streaming API Server for Archipelago.

Flask + Gunicorn production backend. Importing this module builds the app and
registers every route; the implementation lives in sibling modules:

- ``engine_state``     — paths, Flask app, and runtime component state
- ``middleware``       — CORS plus Supabase session enforcement
- ``routes_auth``      — /api/auth/*, /api/users
- ``routes_chat``      — /api/chat (3-tier guardrailed graph synthesis)
- ``routes_discovery`` — topic suggestions, roadmap, diagnostic MCQs
- ``routes_library``   — catalog search, e-resources, document inventory
- ``routes_docs``      — /api/readiness, /api/upload
"""

from __future__ import annotations

import logging
import os

from archipelago.api.engine_state import (
    BASE_DIR,
    DATA_FILE,
    DB_PATH,
    PDF_DIR,
    app,
    concept_name,
    concept_node,
    ensure_engine,
    get_kuzu_connection,
    init_engine,
    load_concepts_data,
)

logger = logging.getLogger("archipelago.api")
logging.basicConfig(level=logging.INFO)

# Build runtime components before any route can serve a request.
init_engine()

# Importing these modules registers their routes and request hooks on ``app``.
from archipelago.api import (
    middleware,
    routes_auth,
    routes_chat,
    routes_discovery,
    routes_docs,
    routes_library,
)

add_cors = middleware.add_cors
require_supabase_session = middleware.require_supabase_session

api_auth_config = routes_auth.api_auth_config
api_auth_me = routes_auth.api_auth_me
api_manage_users = routes_auth.api_manage_users

api_chat = routes_chat.api_chat

api_topic_suggest = routes_discovery.api_topic_suggest
api_roadmap_quiz = routes_discovery.api_roadmap_quiz
api_chat_diagnostic_mcqs = routes_discovery.api_chat_diagnostic_mcqs
api_chat_verify_mcq = routes_discovery.api_chat_verify_mcq
api_chat_adaptive_step = routes_discovery.api_chat_adaptive_step
api_chat_telemetry = routes_discovery.api_chat_telemetry

api_catalog_search = routes_library.api_catalog_search
api_eresources = routes_library.api_eresources
api_documents = routes_library.api_documents

api_readiness = routes_docs.api_readiness
api_upload = routes_docs.api_upload

DEFAULT_PORT = 5051
BIND_HOST = "0.0.0.0"

__all__ = [
    "BASE_DIR",
    "DATA_FILE",
    "DB_PATH",
    "PDF_DIR",
    "add_cors",
    "api_auth_config",
    "api_auth_me",
    "api_catalog_search",
    "api_chat",
    "api_chat_adaptive_step",
    "api_chat_diagnostic_mcqs",
    "api_chat_telemetry",
    "api_chat_verify_mcq",
    "api_documents",
    "api_eresources",
    "api_manage_users",
    "api_readiness",
    "api_roadmap_quiz",
    "api_topic_suggest",
    "api_upload",
    "app",
    "concept_name",
    "concept_node",
    "ensure_engine",
    "get_kuzu_connection",
    "init_engine",
    "load_concepts_data",
    "require_supabase_session",
]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    app.run(host=BIND_HOST, port=port, debug=False)
