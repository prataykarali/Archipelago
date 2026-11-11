"""SLM extraction: local-model state, generation, and OKF v1.5 parsing.

This module OWNS the local PyTorch model state (LOCAL_MODEL / LOCAL_TOKENIZER
/ LOCAL_MODE). load_local_model mutates these module globals; other modules
must query the state through is_local_mode()/is_model_loaded() instead of
importing the raw globals (a `from ... import LOCAL_MODEL` would snapshot the
pre-load None forever)."""

from __future__ import annotations

import json  # noqa: F401
import sys  # noqa: F401
import time  # noqa: F401
from typing import Any

import ollama  # noqa: F401

from okf.cleanup import is_valid_concept_name  # noqa: F401
from okf.config import (
    BASE_DIR,  # noqa: F401
    EXTRACTION_PROMPT_V15,  # noqa: F401
    MAX_CHARS_TO_SLM,  # noqa: F401
    MAX_RETRIES,  # noqa: F401
    MODEL_NAME,  # noqa: F401
    VALID_DIFFICULTIES,  # noqa: F401
    VALID_RELATIONS,  # noqa: F401
    VALID_TYPES,  # noqa: F401
    _local_path,  # noqa: F401
    infer_source_category,  # noqa: F401
)

from . import part01_local_model as _state
from .part01_local_model import (
    load_local_model,
)
from .part02_is_local_mode import (
    _extract_json_payload,
    _generate_local,
    _normalize_related,
    _string_list,
    _strip_json_fences,
    extract_okf_v15,
    is_local_mode,
    is_model_loaded,
    normalize_okf_item,
)
from .part03_extract_chunks_with_model import (
    extract_chunks_with_model,
)


def __getattr__(name: str) -> Any:
    """Late-bind ``global``-rebound state (PEP 562)."""
    return getattr(_state, name)


__all__ = [
    "LOCAL_MODE",
    "LOCAL_MODEL",
    "LOCAL_TOKENIZER",
    "_extract_json_payload",
    "_generate_local",
    "_normalize_related",
    "_string_list",
    "_strip_json_fences",
    "extract_chunks_with_model",
    "extract_okf_v15",
    "is_local_mode",
    "is_model_loaded",
    "load_local_model",
    "normalize_okf_item",
]
