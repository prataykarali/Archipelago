"""Lib-Qwen Ingestion & Pedagogical Concept Extraction Engine.

Extracts canonical concepts, mathematical definitions, and directional REQUIRES/UNLOCKS
relationships from textbook chapters using lib-qwen:latest with guided JSON decoding,
negative sampling, canonical resolution, and Kahn DAG verification."""
from __future__ import annotations

import json  # noqa: F401
import logging  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
from typing import Any, Optional  # noqa: F401

from .part01_toplevel_17 import (  # noqa: F401
    logger,
    DEFAULT_MODEL,
    MAX_NEW_CONCEPTS_PER_BATCH,
    NEGATIVE_SAMPLE_PATTERNS,
    CANONICAL_ALIAS_MAP,
    is_negative_sample,
    canonicalize_concept_name,
    canonical_concept_id,
    clean_json_payload,
    OLLAMA_AVAILABLE,
    ollama,
)
from .part02_libqwenconceptextractor import (  # noqa: F401
    LibQwenConceptExtractor,
)

__all__ = ["logger", "DEFAULT_MODEL", "MAX_NEW_CONCEPTS_PER_BATCH", "NEGATIVE_SAMPLE_PATTERNS", "CANONICAL_ALIAS_MAP", "is_negative_sample", "canonicalize_concept_name", "canonical_concept_id", "clean_json_payload", "LibQwenConceptExtractor"]
