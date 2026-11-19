"""S5-D1 Preflight, Authorization Gate, Evaluation, and Reporting Pipeline."""

from __future__ import annotations

from d1_pipeline.auth_gate import (
    AuthorizationError,
    ExecutionMode,
    authorization_template,
    validate_investigator_authorization,
)
from d1_pipeline.figures import generate_all_figures
from d1_pipeline.metrics import compute_d1_evaluation, evaluate_query_ranking_extended
from d1_pipeline.preflight import PreflightError, validate_d1_preflight
from d1_pipeline.tables import generate_all_tables

__all__ = [
    "AuthorizationError",
    "ExecutionMode",
    "PreflightError",
    "authorization_template",
    "compute_d1_evaluation",
    "evaluate_query_ranking_extended",
    "generate_all_figures",
    "generate_all_tables",
    "validate_d1_preflight",
    "validate_investigator_authorization",
]
