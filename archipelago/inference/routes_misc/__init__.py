"""Flask routes: CORS, PDFs, readiness, ingestion API, diagnostics."""
from __future__ import annotations

import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import secrets  # noqa: F401
import threading  # noqa: F401
import time  # noqa: F401
from pathlib import Path  # noqa: F401
from urllib.parse import quote  # noqa: F401
from flask import jsonify, send_from_directory, request, redirect  # noqa: F401
import kuzu  # noqa: F401
from ingestion_jobs import JobStatus  # noqa: F401
from ingestion_worker import job_store, get_worker, graph_lock  # noqa: F401
from archipelago.auth import require_librarian, librarian_token_expected  # noqa: F401
from archipelago.inference import state as st  # noqa: F401
from archipelago import supabase_auth  # noqa: F401
import torch  # noqa: F401

from .m01_cors_pdf import (  # noqa: F401
    add_cors_headers,
    serve_pdf,
    REMOTE_PDF_SOURCES,
)
from .m02_shares import (  # noqa: F401
    SHARES_DIR,
    _SHARE_MAX_BYTES,
    _SHARE_ID_RE,
    create_share,
    get_share,
)
from .m03_health_internal import (  # noqa: F401
    readiness,
    close_graph_internal,
    reload_graph_internal,
)
from .m04_ingest import (  # noqa: F401
    ingestion_capabilities,
    ingest_upload,
    ingest_status,
    ingest_cancel,
    ingest_list,
    SlidingWindowLimiter,
    _ingest_limiter,
    ingest_index,
    estimate_ingestion_time,
)
from .m05_graph_admin import (  # noqa: F401
    list_graph_documents,
    delete_graph_document,
    manual_add_concept,
    manual_add_edge,
)
from .m06_roadmap_resolver import (  # noqa: F401
    api_roadmap_quiz,
    api_roadmap_plan,
    api_roadmap_between,
    resolve_pdf_file,
    pdf_available,
)
from .m07_diagnostics import (  # noqa: F401
    server_root,
)
from .m08_auth_users import (  # noqa: F401
    api_auth_config,
    api_auth_me,
    manage_users_api_backend,
)
from .m09_librarian_intake import (  # noqa: F401
    ingest_mention,
    ingest_page_image,
    ingest_page_text,
    ingest_spreadsheet_plan,
    ingest_spreadsheet_apply,
    intake_capabilities,
)
from .m10_probes import (  # noqa: F401
    health,
    ready,
    api_health,
)

__all__ = ["add_cors_headers", "serve_pdf", "REMOTE_PDF_SOURCES", "SHARES_DIR", "_SHARE_MAX_BYTES", "_SHARE_ID_RE", "create_share", "get_share", "readiness", "close_graph_internal", "reload_graph_internal", "ingestion_capabilities", "ingest_upload", "ingest_status", "ingest_cancel", "ingest_list", "SlidingWindowLimiter", "_ingest_limiter", "ingest_index", "list_graph_documents", "delete_graph_document", "manual_add_concept", "manual_add_edge", "server_root", "api_roadmap_quiz", "api_roadmap_plan", "api_roadmap_between", "resolve_pdf_file", "pdf_available", "estimate_ingestion_time", "api_auth_config", "api_auth_me", "manage_users_api_backend", "ingest_mention", "ingest_page_image", "ingest_page_text", "ingest_spreadsheet_plan", "ingest_spreadsheet_apply", "intake_capabilities", "health", "ready", "api_health"]
