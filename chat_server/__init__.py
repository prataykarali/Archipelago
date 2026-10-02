"""Archipelago Chat UI Server
Serves the premium, standalone chat workspace UI on port 5052."""
from __future__ import annotations

from collections.abc import Iterator  # noqa: F401
from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory  # noqa: F401
from flask.typing import ResponseReturnValue  # noqa: F401
import json  # noqa: F401
import mimetypes  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
from pathlib import Path  # noqa: F401
import sys  # noqa: F401
import requests as _requests  # noqa: F401
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode  # noqa: F401

from .merged01_repo_root import (  # noqa: F401
    REPO_ROOT,
    _STREAM_CHUNK_BYTES,
    _DEFAULT_INFERENCE_CHAT_URL,
    _raw_inf_url,
    INFERENCE_CHAT_URL,
    BASE_DIR,
    STATIC_DIR,
    _ASSET_ROOTS,
    _VIDEO_ASSET_NAMES,
    ASSETS_DIR,
    app,
    serve_catalogs,
    add_cors_headers,
    _AUTH_PUBLIC_PATHS,
    _AUTH_SESSION_PATHS,
    _STAFF_API_PREFIXES,
    _cookie_options,
    require_verified_api_session,
    _inference_auth_headers,
    _is_auth_enforced,
    _has_valid_auth_session,
    _session_cookie_response,
    auth_session_cookie,
)
from .merged02_index import (  # noqa: F401
    index,
    landing,
    chat_ui,
    library_showcase_3d,
    library_details,
    reader_static_page,
    _requested_page,
    _with_page_fragment,
    reader_view,
    performance_dashboard,
    safety_dashboard,
    login_page,
    media_assets,
    static_files,
)
from .merged03_reader_gateway_open import (  # noqa: F401
    reader_gateway_open,
    reader_info_api,
)
from .merged04_hf_token import (  # noqa: F401
    HF_TOKEN,
    HF_REPO,
    HF_DOC_MAP,
    proxy_pdf,
    _build_redirect_shell,
)
from .merged05_resolve_link_route import (  # noqa: F401
    resolve_link_route,
    library_data,
    catalog_all,
    page_view_proxy,
)
from .merged06_chat_proxy import (  # noqa: F401
    chat_proxy,
    chat_diagnostic_mcqs_proxy,
    chat_telemetry_proxy,
    chat_verify_mcq_proxy,
    chat_adaptive_step_proxy,
    _inference_base,
    dashboards_proxy,
    readiness_proxy,
)
from .merged07_roadmap_proxy import (  # noqa: F401
    roadmap_proxy,
    auth_proxy_or_local,
    manage_users_api,
)
from .merged08_librarian_upload import (  # noqa: F401
    librarian_upload,
    librarian_job_status,
    librarian_staging_review,
    librarian_staging_publish,
    graph_subgraph,
    proxy_ingest_upload,
    proxy_ingest_status,
    proxy_ingest_cancel,
    proxy_documents_list,
    proxy_document_delete,
)

__all__ = ["REPO_ROOT", "_STREAM_CHUNK_BYTES", "_DEFAULT_INFERENCE_CHAT_URL", "_raw_inf_url", "INFERENCE_CHAT_URL", "BASE_DIR", "STATIC_DIR", "_ASSET_ROOTS", "_VIDEO_ASSET_NAMES", "ASSETS_DIR", "app", "add_cors_headers", "serve_catalogs", "_AUTH_PUBLIC_PATHS", "_AUTH_SESSION_PATHS", "_STAFF_API_PREFIXES", "_cookie_options", "require_verified_api_session", "_inference_auth_headers", "_is_auth_enforced", "_has_valid_auth_session", "_session_cookie_response", "auth_session_cookie", "index", "landing", "chat_ui", "library_showcase_3d", "library_details", "reader_static_page", "_requested_page", "_with_page_fragment", "reader_view", "reader_gateway_open", "reader_info_api", "performance_dashboard", "safety_dashboard", "login_page", "media_assets", "HF_TOKEN", "HF_REPO", "HF_DOC_MAP", "proxy_pdf", "_build_redirect_shell", "resolve_link_route", "library_data", "catalog_all", "page_view_proxy", "chat_proxy", "chat_diagnostic_mcqs_proxy", "chat_telemetry_proxy", "chat_verify_mcq_proxy", "chat_adaptive_step_proxy", "_inference_base", "dashboards_proxy", "readiness_proxy", "roadmap_proxy", "auth_proxy_or_local", "manage_users_api", "librarian_upload", "librarian_job_status", "librarian_staging_review", "librarian_staging_publish", "graph_subgraph", "proxy_ingest_upload", "proxy_ingest_status", "proxy_ingest_cancel", "proxy_documents_list", "proxy_document_delete", "static_files"]
