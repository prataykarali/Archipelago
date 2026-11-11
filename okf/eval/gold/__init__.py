"""Facade for the split of gold.py."""

from __future__ import annotations

import re  # noqa: F401

from okf.eval._base import *  # noqa: F403
from okf.eval.structural import structural_audit  # noqa: F401

from .part01_load_gold_graph import (
    _canonical_key,
    _extract_edges,
    _extract_name_docs,
    _extract_names,
    compare_concepts,
    compare_edges,
    evaluate_pipeline,
    load_gold_graph,
)
from .part02_print_report import (
    print_report,
)

__all__ = [
    "_canonical_key",
    "_extract_edges",
    "_extract_name_docs",
    "_extract_names",
    "compare_concepts",
    "compare_edges",
    "evaluate_pipeline",
    "load_gold_graph",
    "print_report",
]
