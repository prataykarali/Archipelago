"""S5-C3 local-only human annotation workbench package."""

from __future__ import annotations

from .loader import PoolIntegrityError, assert_blinding_clean, load_blinded_pool
from .models import (
    AnnotationSession,
    CandidatePair,
    JudgmentRecord,
    LoadedPool,
    ProvenanceDeclaration,
    content_hash,
    sha256_file,
)
from .storage import (
    ExportArtifactResult,
    ExportValidationError,
    PrivatePathViolationError,
    SaveArtifactResult,
    create_timestamped_backup,
    ensure_private_path,
    export_submission,
    load_or_create_session,
    save_session,
)
from .validation import (
    PairValidationResult,
    SessionValidationReport,
    is_exact_verbatim_quote,
    validate_pair_judgment,
    validate_provenance,
    validate_session,
)
from .web_app import assert_loopback_host, create_app

__all__ = [
    "AnnotationSession",
    "CandidatePair",
    "ExportArtifactResult",
    "ExportValidationError",
    "JudgmentRecord",
    "LoadedPool",
    "PairValidationResult",
    "PoolIntegrityError",
    "PrivatePathViolationError",
    "ProvenanceDeclaration",
    "SaveArtifactResult",
    "SessionValidationReport",
    "assert_blinding_clean",
    "assert_loopback_host",
    "content_hash",
    "create_app",
    "create_timestamped_backup",
    "ensure_private_path",
    "export_submission",
    "is_exact_verbatim_quote",
    "load_blinded_pool",
    "load_or_create_session",
    "save_session",
    "sha256_file",
    "validate_pair_judgment",
    "validate_provenance",
    "validate_session",
]
