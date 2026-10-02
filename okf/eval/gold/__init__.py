"""Facade for the split of gold.py."""
from __future__ import annotations

from .part01_load_gold_graph import (  # noqa: F401
    load_gold_graph,
    _extract_names,
    _canonical_key,
    _extract_name_docs,
    compare_concepts,
    _extract_edges,
    compare_edges,
    evaluate_pipeline,
)
from .part02_print_report import (  # noqa: F401
    print_report,
)

import re  # noqa: F401
from okf.eval._base import *  # noqa: F401
from okf.eval.structural import structural_audit  # noqa: F401

__all__ = ["load_gold_graph", "_extract_names", "_canonical_key", "_extract_name_docs", "compare_concepts", "_extract_edges", "compare_edges", "evaluate_pipeline", "print_report"]
