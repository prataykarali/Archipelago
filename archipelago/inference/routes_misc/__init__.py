"""Flask routes: CORS, PDFs, readiness, ingestion API, diagnostics."""

from __future__ import annotations

import json  # noqa: F401
import os  # noqa: F401
from pathlib import Path  # noqa: F401
import re  # noqa: F401
import secrets  # noqa: F401
import threading  # noqa: F401
import time  # noqa: F401
from urllib.parse import quote  # noqa: F401

from flask import jsonify, redirect, request, send_from_directory  # noqa: F401
import kuzu  # noqa: F401
import torch  # noqa: F401

from archipelago import supabase_auth  # noqa: F401
from archipelago.auth import librarian_token_expected, require_librarian  # noqa: F401
from archipelago.inference import state as st  # noqa: F401
from ingestion_jobs import JobStatus  # noqa: F401
from ingestion_worker import get_worker, graph_lock, job_store  # noqa: F401

from .m01_cors_pdf import (
    REMOTE_PDF_SOURCES,
    add_cors_headers,
    serve_pdf,
)
from .m02_shares import (
    _SHARE_ID_RE,
    _SHARE_MAX_BYTES,
    SHARES_DIR,
    create_share,
    get_share,
)
from .m03_health_internal import (
    close_graph_internal,
    readiness,
    reload_graph_internal,
)
from .m04_ingest import (
    SlidingWindowLimiter,
    _ingest_limiter,
    estimate_ingestion_time,
    ingest_cancel,
    ingest_index,
    ingest_list,
    ingest_status,
    ingest_upload,
    ingestion_capabilities,
)
from .m05_graph_admin import (
    delete_graph_document,
    list_graph_documents,
    manual_add_concept,
    manual_add_edge,
)
from .m06_roadmap_resolver import (
    api_roadmap_between,
    api_roadmap_plan,
    api_roadmap_quiz,
    pdf_available,
    resolve_pdf_file,
)
from .m07_diagnostics import (
    server_root,
)
from .m08_auth_users import (
    api_auth_config,
    api_auth_me,
    manage_users_api_backend,
)
from .m09_librarian_intake import (
    ingest_mention,
    ingest_page_image,
    ingest_page_text,
    ingest_spreadsheet_apply,
    ingest_spreadsheet_plan,
    intake_capabilities,
)
from .m10_probes import (
    api_health,
    health,
    ready,
)
from .m11_scholarly import scholarly_discover

__all__ = [
    "REMOTE_PDF_SOURCES",
    "SHARES_DIR",
    "_SHARE_ID_RE",
    "_SHARE_MAX_BYTES",
    "SlidingWindowLimiter",
    "_ingest_limiter",
    "add_cors_headers",
    "api_auth_config",
    "api_auth_me",
    "api_health",
    "api_roadmap_between",
    "api_roadmap_plan",
    "api_roadmap_quiz",
    "close_graph_internal",
    "create_share",
    "delete_graph_document",
    "estimate_ingestion_time",
    "get_share",
    "health",
    "ingest_cancel",
    "ingest_index",
    "ingest_list",
    "ingest_mention",
    "ingest_page_image",
    "ingest_page_text",
    "ingest_spreadsheet_apply",
    "ingest_spreadsheet_plan",
    "ingest_status",
    "ingest_upload",
    "ingestion_capabilities",
    "intake_capabilities",
    "list_graph_documents",
    "manage_users_api_backend",
    "manual_add_concept",
    "manual_add_edge",
    "pdf_available",
    "readiness",
    "ready",
    "reload_graph_internal",
    "resolve_pdf_file",
    "scholarly_discover",
    "serve_pdf",
    "server_root",
]
