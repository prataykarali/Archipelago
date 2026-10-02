"""Librarian Ingestion Worker & Staging DB Management Engine.

Provides asynchronous ingestion pipeline for librarian uploads:
1. Streams document to Hugging Face Hub (Prataykarali/Library_books).
2. Structural slicing with high-yield filtering (dropping front matter, TOC, bibliographies).
3. Grammar-constrained OKF concept extraction via fine-tuned lib-qwen on GPU.
4. Entity resolution & Kahn DAG Cycle Gate verification.
5. Populates okf_graph_staging.db.
6. Vector embedding precomputation before connection-safe atomic swap to okf_graph.db."""
from __future__ import annotations

import json  # noqa: F401
import logging  # noqa: F401
import os  # noqa: F401
import queue  # noqa: F401
import re  # noqa: F401
import shutil  # noqa: F401
import threading  # noqa: F401
import time  # noqa: F401
import uuid  # noqa: F401
from dataclasses import asdict, dataclass, field  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any, Optional  # noqa: F401
import kuzu  # noqa: F401
from archipelago.graph.engine import KuzuGraphEngine  # noqa: F401
from archipelago.graph.graph_fusion import GraphFusionEngine  # noqa: F401
from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,
    canonical_concept_id,
    canonicalize_concept_name,
    is_negative_sample,
)  # noqa: F401
from archipelago.storage.hf_remote import HFStorageClient  # noqa: F401

from .part01_logger import (  # noqa: F401
    logger,
    _repo_root,
    BASE_DIR,
    STAGING_DB_PATH,
    PROD_DB_PATH,
    DATA_FILE,
    INFERENCE_RELOAD_URL,
    JOBS_DIR,
    UPLOADS_DIR,
    LibrarianJob,
)
from .part02_librarianworker import (  # noqa: F401
    LibrarianWorker,
)
from .part03_copy_db import (  # noqa: F401
    _copy_db,
    clone_production_to_staging,
    ensure_staging_db,
    count_concepts,
    export_graph_json,
    _post_inference,
    notify_inference_close,
    notify_inference_reload,
    sync_embeddings_from_db,
    _librarian_worker,
    start_upload_job,
    get_job_status,
    get_staging_review,
)
from .part04_publish_staging import (  # noqa: F401
    publish_staging,
)

__all__ = ["logger", "_repo_root", "BASE_DIR", "STAGING_DB_PATH", "PROD_DB_PATH", "DATA_FILE", "INFERENCE_RELOAD_URL", "JOBS_DIR", "UPLOADS_DIR", "LibrarianJob", "LibrarianWorker", "_copy_db", "clone_production_to_staging", "ensure_staging_db", "count_concepts", "export_graph_json", "_post_inference", "notify_inference_close", "notify_inference_reload", "sync_embeddings_from_db", "_librarian_worker", "start_upload_job", "get_job_status", "get_staging_review", "publish_staging"]
