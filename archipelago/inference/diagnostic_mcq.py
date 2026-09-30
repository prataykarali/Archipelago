"""Interactive Diagnostic MCQ Layer for Archipelago runtime.

Generates and validates targeted multiple-choice questions for upstream
prerequisites in Mode C pedagogical exploration.
Enforces strict 4-option format (A, B, C, D) with literature citations.
"""

from __future__ import annotations

# Re-export from src.archipelago.inference.diagnostic_mcq
from src.archipelago.inference.diagnostic_mcq import (
    DiagnosticMCQ,
    build_personalized_graph_dag,
    evaluate_diagnostic_mcqs,
    generate_diagnostic_mcqs,
    validate_mcq_submission,
    get_prerequisite_chain,
    generate_single_mcq_on_the_spot,
    execute_adaptive_step,
    _generate_slm_mcq,
    _generate_dynamic_mcq,
)

__all__ = [
    "DiagnosticMCQ",
    "build_personalized_graph_dag",
    "evaluate_diagnostic_mcqs",
    "generate_diagnostic_mcqs",
    "validate_mcq_submission",
    "get_prerequisite_chain",
    "generate_single_mcq_on_the_spot",
    "execute_adaptive_step",
    "_generate_slm_mcq",
    "_generate_dynamic_mcq",
]

