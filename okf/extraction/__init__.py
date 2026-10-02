"""SLM extraction: local-model state, generation, and OKF v1.5 parsing.

This module OWNS the local PyTorch model state (LOCAL_MODEL / LOCAL_TOKENIZER
/ LOCAL_MODE). load_local_model mutates these module globals; other modules
must query the state through is_local_mode()/is_model_loaded() instead of
importing the raw globals (a `from ... import LOCAL_MODEL` would snapshot the
pre-load None forever)."""
from __future__ import annotations

from .part01_local_model import (  # noqa: F401
    load_local_model,
)
from .part02_is_local_mode import (  # noqa: F401
    is_local_mode,
    is_model_loaded,
    _strip_json_fences,
    _extract_json_payload,
    _string_list,
    _normalize_related,
    normalize_okf_item,
    _generate_local,
    extract_okf_v15,
)
from .part03_extract_chunks_with_model import (  # noqa: F401
    extract_chunks_with_model,
)

import json  # noqa: F401
import sys  # noqa: F401
import time  # noqa: F401
import ollama  # noqa: F401
from okf.cleanup import is_valid_concept_name  # noqa: F401
from okf.config import (
    BASE_DIR,
    EXTRACTION_PROMPT_V15,
    MAX_CHARS_TO_SLM,
    MAX_RETRIES,
    MODEL_NAME,
    VALID_DIFFICULTIES,
    VALID_RELATIONS,
    VALID_TYPES,
    _local_path,
    infer_source_category,
)  # noqa: F401
from . import part01_local_model as _state  # noqa: F401

def __getattr__(name: str):
    """Late-bind ``global``-rebound state (PEP 562)."""
    return getattr(_state, name)


__all__ = ["LOCAL_MODEL", "LOCAL_TOKENIZER", "LOCAL_MODE", "is_local_mode", "is_model_loaded", "_strip_json_fences", "_extract_json_payload", "_string_list", "_normalize_related", "normalize_okf_item", "load_local_model", "_generate_local", "extract_okf_v15", "extract_chunks_with_model"]
