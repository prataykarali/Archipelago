"""Versioned S5-v3.1 D1 preflight, authorization gate, evaluation engine, and table generators."""

from __future__ import annotations

from eval_v31.auth_gate import (
    V31AuthorizationError,
    build_v31_authorization_template,
    is_valid_human_id,
    validate_v31_authorization_gate,
)
from eval_v31.constants import (
    AUTH_APPROVED_STATUS_V31,
    AUTH_SCHEMA_VERSION_V31,
    BENCHMARK_VERSION_V31,
    GOLD_SCHEMA_VERSION_V31,
    GOLD_STATUS_FINAL,
    GOLD_STATUS_SYNTHETIC,
    SYNTHETIC_BANNER,
)
from eval_v31.metrics import compute_v31_d1_evaluation, evaluate_v31_query_ranking
from eval_v31.preflight import (
    V31PreflightError,
    V31PreflightFinding,
    V31PreflightResult,
    sha256_file,
    validate_v31_preflight,
)
from eval_v31.tables import (
    generate_csv_table,
    generate_latex_table,
    generate_markdown_table,
    write_results_tables,
)

__all__ = [
    "AUTH_APPROVED_STATUS_V31",
    "AUTH_SCHEMA_VERSION_V31",
    "BENCHMARK_VERSION_V31",
    "GOLD_SCHEMA_VERSION_V31",
    "GOLD_STATUS_FINAL",
    "GOLD_STATUS_SYNTHETIC",
    "SYNTHETIC_BANNER",
    "V31AuthorizationError",
    "V31PreflightError",
    "V31PreflightFinding",
    "V31PreflightResult",
    "build_v31_authorization_template",
    "compute_v31_d1_evaluation",
    "evaluate_v31_query_ranking",
    "generate_csv_table",
    "generate_latex_table",
    "generate_markdown_table",
    "is_valid_human_id",
    "sha256_file",
    "validate_v31_authorization_gate",
    "validate_v31_preflight",
    "write_results_tables",
]
