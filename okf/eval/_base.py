"""Proxy accuracy metrics for the extraction pipeline."""

from collections import Counter
from importlib import import_module
from types import ModuleType

from okf.canonicalize import _concept_key, canonicalize_name

# Fuzzy fallback for gold comparison (P1.8). rapidfuzz backs thefuzz (see
# requirements.txt); import it directly for token_set_ratio scoring.
try:
    _rf_fuzz: ModuleType | None = import_module("rapidfuzz.fuzz")
except Exception:  # pragma: no cover - optional dependency
    _rf_fuzz = None

# Minimum token_set_ratio for two canonically-unmatched names to count as TP.
FUZZY_MATCH_THRESHOLD = 90

__all__ = [
    "FUZZY_MATCH_THRESHOLD",
    "Counter",
    "_concept_key",
    "_rf_fuzz",
    "canonicalize_name",
]
