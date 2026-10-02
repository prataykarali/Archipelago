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

from .part01_logger import (  # noqa: F401
    logger,
    DiagnosticMCQ,
    _VERIFIED_QUESTION_BANK,
    _generate_slm_mcq,
)
from .part02_generate_dynamic_mcq import (  # noqa: F401
    _generate_dynamic_mcq,
    generate_diagnostic_mcqs,
    get_prerequisite_chain,
    generate_single_mcq_on_the_spot,
)
from .part03_execute_adaptive_step import (  # noqa: F401
    execute_adaptive_step,
    validate_mcq_submission,
)
from .part04_build_personalized_graph_dag import (  # noqa: F401
    build_personalized_graph_dag,
)
from .part05_evaluate_diagnostic_mcqs import (  # noqa: F401
    evaluate_diagnostic_mcqs,
)

__all__ = ["logger", "DiagnosticMCQ", "_VERIFIED_QUESTION_BANK", "_generate_slm_mcq", "_generate_dynamic_mcq", "generate_diagnostic_mcqs", "get_prerequisite_chain", "generate_single_mcq_on_the_spot", "execute_adaptive_step", "validate_mcq_submission", "build_personalized_graph_dag", "evaluate_diagnostic_mcqs"]
