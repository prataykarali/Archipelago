"""S5-C3 Independent A/C Comparison and Human Adjudication package."""

from __future__ import annotations

from .comparison import (
    assemble_gold_v2,
    build_blank_adjudication_worksheet,
    compute_inter_annotator_agreement,
    extract_ac_disagreements,
    render_adjudication_worksheet_markdown,
)
from .pool_index import FrozenPool, PoolEntry, load_frozen_pool, sha256_file, sha256_text
from .server import create_adjudication_app, run_local_adjudication_server
from .validation import (
    ACValidationError,
    validate_adjudication_worksheet,
    validate_gold_v2_payload,
    validate_reviewer_submission,
)

__all__ = [
    "ACValidationError",
    "FrozenPool",
    "PoolEntry",
    "assemble_gold_v2",
    "build_blank_adjudication_worksheet",
    "compute_inter_annotator_agreement",
    "create_adjudication_app",
    "extract_ac_disagreements",
    "load_frozen_pool",
    "render_adjudication_worksheet_markdown",
    "run_local_adjudication_server",
    "sha256_file",
    "sha256_text",
    "validate_adjudication_worksheet",
    "validate_gold_v2_payload",
    "validate_reviewer_submission",
]
