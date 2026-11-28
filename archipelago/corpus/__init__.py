"""Archipelago D14 reproducible open-access corpus ingestion & validation package.

Provides license-gated source registration, native PDF/HTML/text extraction,
physical-to-printed page mapping, structural filtering, section-aware passage
segmentation, concept/domain enrichment, lexical indexing support, and
versioned ``corpus_v3_d14`` manifest emission.
"""

from __future__ import annotations

from archipelago.corpus.catalog import (
    CANONICAL_DOMAINS,
    CORPUS_VERSION_V3,
    LicenseStatus,
    SourceFormat,
    SourceSpec,
    build_default_source_catalog,
)
from archipelago.corpus.license_gate import (
    AuthorizationDecision,
    authorize_source,
    verify_license_register,
)

__all__ = [
    "CANONICAL_DOMAINS",
    "CORPUS_VERSION_V3",
    "AuthorizationDecision",
    "LicenseStatus",
    "SourceFormat",
    "SourceSpec",
    "authorize_source",
    "build_default_source_catalog",
    "verify_license_register",
]
