"""Librarian Ingestion Worker & Staging DB Management Engine.

Provides asynchronous ingestion pipeline for librarian uploads:
1. Streams document to Hugging Face Hub (Prataykarali/Library_books).
2. Structural slicing with high-yield filtering (dropping front matter, TOC, bibliographies).
3. Grammar-constrained OKF concept extraction via fine-tuned lib-qwen on GPU.
4. Entity resolution & Kahn DAG Cycle Gate verification.
5. Populates okf_graph_staging.db.
6. Vector embedding precomputation before connection-safe atomic swap to okf_graph.db."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
import os  # noqa: F401
from pathlib import Path  # noqa: F401
import queue  # noqa: F401
import re  # noqa: F401
import shutil  # noqa: F401
import threading  # noqa: F401
import time  # noqa: F401
from typing import Any, Optional  # noqa: F401
import uuid  # noqa: F401

import kuzu  # noqa: F401

from archipelago.graph.engine import KuzuGraphEngine  # noqa: F401
from archipelago.graph.graph_fusion import GraphFusionEngine  # noqa: F401
from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,  # noqa: F401
    canonical_concept_id,  # noqa: F401
    canonicalize_concept_name,  # noqa: F401
    is_negative_sample,  # noqa: F401
)
from archipelago.storage.hf_remote import HFStorageClient  # noqa: F401

from .part01_logger import (
    BASE_DIR,
    DATA_FILE,
    INFERENCE_RELOAD_URL,
    JOBS_DIR,
    PROD_DB_PATH,
    STAGING_DB_PATH,
    UPLOADS_DIR,
    LibrarianJob,
    _repo_root,
    logger,
)
from .part02_librarianworker import (
    LibrarianWorker,
)
from .part03_copy_db import (
    _copy_db,
    _librarian_worker,
    _post_inference,
    clone_production_to_staging,
    count_concepts,
    ensure_staging_db,
    export_graph_json,
    get_job_status,
    get_staging_review,
    notify_inference_close,
    notify_inference_reload,
    start_upload_job,
    sync_embeddings_from_db,
)
from .part04_publish_staging import (
    publish_staging,
)

__all__ = [
    "BASE_DIR",
    "DATA_FILE",
    "INFERENCE_RELOAD_URL",
    "JOBS_DIR",
    "PROD_DB_PATH",
    "STAGING_DB_PATH",
    "UPLOADS_DIR",
    "LibrarianJob",
    "LibrarianWorker",
    "_copy_db",
    "_librarian_worker",
    "_post_inference",
    "_repo_root",
    "clone_production_to_staging",
    "count_concepts",
    "ensure_staging_db",
    "export_graph_json",
    "get_job_status",
    "get_staging_review",
    "logger",
    "notify_inference_close",
    "notify_inference_reload",
    "publish_staging",
    "start_upload_job",
    "sync_embeddings_from_db",
]
