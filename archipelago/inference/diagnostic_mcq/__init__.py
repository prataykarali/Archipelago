"""Interactive Diagnostic MCQ Layer for Archipelago.

Generates and validates targeted multiple-choice questions for upstream
prerequisites in Mode C pedagogical exploration.
Enforces strict 4-option format (A, B, C, D) with literature citations."""

from __future__ import annotations

from dataclasses import asdict, dataclass  # noqa: F401
import hashlib  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
import os  # noqa: F401
import random  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401

from .part01_logger import (
    _VERIFIED_QUESTION_BANK,
    DiagnosticMCQ,
    _generate_slm_mcq,
    logger,
)
from .part02_generate_dynamic_mcq import (
    _generate_dynamic_mcq,
    generate_diagnostic_mcqs,
    generate_single_mcq_on_the_spot,
    get_prerequisite_chain,
)
from .part03_execute_adaptive_step import (
    execute_adaptive_step,
    validate_mcq_submission,
)
from .part04_build_personalized_graph_dag import (
    build_personalized_graph_dag,
)
from .part05_evaluate_diagnostic_mcqs import (
    evaluate_diagnostic_mcqs,
)

__all__ = [
    "_VERIFIED_QUESTION_BANK",
    "DiagnosticMCQ",
    "_generate_dynamic_mcq",
    "_generate_slm_mcq",
    "build_personalized_graph_dag",
    "evaluate_diagnostic_mcqs",
    "execute_adaptive_step",
    "generate_diagnostic_mcqs",
    "generate_single_mcq_on_the_spot",
    "get_prerequisite_chain",
    "logger",
    "validate_mcq_submission",
]
