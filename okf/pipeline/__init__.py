"""Pipeline orchestration: full runs, incremental --add, and finalization."""

from __future__ import annotations

from collections import Counter  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
from pathlib import Path  # noqa: F401
import sys  # noqa: F401

from okf import config, extraction  # noqa: F401
from okf.cleanup import (
    clean_pipeline,
    cleanup_and_canonicalize,  # noqa: F401
)
from okf.config import BASE_DIR, MODEL_NAME, _local_path, infer_source_category  # noqa: F401
from okf.extraction import extract_chunks_with_model, load_local_model  # noqa: F401
from okf.graph_db import ingest_to_kuzu  # noqa: F401
from okf.pipeline_staged import PipelineAborted as PipelineAborted
from okf.pipeline_staged import run_pipeline_staged as run_pipeline_staged

from .part01_filter_extracted_relations import (
    compute_doc_id,
    filter_extracted_relations,
    finalize_and_build,
    run_pipeline,
)
from .part02_add_document import (
    add_document,
)

__all__ = [
    "PipelineAborted",
    "add_document",
    "clean_pipeline",
    "compute_doc_id",
    "filter_extracted_relations",
    "finalize_and_build",
    "run_pipeline",
    "run_pipeline_staged",
]
