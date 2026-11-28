"""License verification and source authorization gate for Archipelago D14.

Enforces strict legal compliance: commercial textbooks (CLRS, Tanenbaum,
Dragon Book, Silberschatz, Hopcroft, Pearson/UEM institutional holdings) and
unverified/metadata-only entries are deterministically rejected before any
download or full-text extraction can proceed.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from archipelago.corpus.catalog import (
    CANONICAL_DOMAINS,
    LicenseStatus,
    SourceFormat,
    SourceSpec,
)

# Explicit deny-list patterns for unauthorized commercial textbooks & holdings.
PROHIBITED_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bclrs\b", re.IGNORECASE),
    re.compile(r"introduction\s+to\s+algorithms.*cormen", re.IGNORECASE),
    re.compile(r"\btanenbaum\b", re.IGNORECASE),
    re.compile(r"\bdragon\s+book\b", re.IGNORECASE),
    re.compile(r"compilers:\s*principles,\s*techniques,\s*and\s*tools", re.IGNORECASE),
    re.compile(r"\bsilberschatz\b", re.IGNORECASE),
    re.compile(r"\bhopcroft\b", re.IGNORECASE),
    re.compile(r"\bpearson\b", re.IGNORECASE),
    re.compile(r"\bsommerville\b", re.IGNORECASE),
    re.compile(r"\bstallings\b", re.IGNORECASE),
    re.compile(r"\brussell\s*&\s*norvig\b", re.IGNORECASE),
)

APPROVED_LICENSE_TOKENS: tuple[str, ...] = (
    "cc-by",
    "cc0",
    "public domain",
    "gfdl",
    "ietf trust",
    "mit",
    "apache-2.0",
    "postgresql",
    "author free open",
    "arxiv / open-access",
)

PROHIBITED_LICENSE_TOKENS: tuple[str, ...] = (
    "all rights reserved",
    "commercial",
    "proprietary",
    "institutional only",
    "pearson",
)


@dataclass(frozen=True)
class AuthorizationDecision:
    """Result of evaluating a SourceSpec against the D14 license gate."""

    source_id: str
    allowed: bool
    reason: str
    license_status: LicenseStatus


def _matches_prohibited_work(spec: SourceSpec) -> str | None:
    """Return matching deny-list pattern if the source is a prohibited textbook."""
    haystack = f"{spec.title} {spec.authors} {spec.doc_id}"
    for pattern in PROHIBITED_TITLE_PATTERNS:
        if pattern.search(haystack):
            return pattern.pattern
    return None


def _license_is_approved(license_name: str) -> bool:
    """Return True if the license string matches an approved OA/free license."""
    lowered = license_name.strip().lower()
    if not lowered:
        return False
    if any(token in lowered for token in PROHIBITED_LICENSE_TOKENS):
        return False
    return any(token in lowered for token in APPROVED_LICENSE_TOKENS)


def authorize_source(spec: SourceSpec) -> AuthorizationDecision:
    """Evaluate whether ``spec`` is legally authorized for full-text ingestion."""
    if spec.domain not in CANONICAL_DOMAINS:
        return AuthorizationDecision(
            source_id=spec.source_id,
            allowed=False,
            reason=f"unknown_domain:{spec.domain}",
            license_status=spec.license_status,
        )

    if spec.source_format == SourceFormat.CATALOG_CARD:
        return AuthorizationDecision(
            source_id=spec.source_id,
            allowed=False,
            reason="metadata_only_catalog_card",
            license_status=LicenseStatus.METADATA_ONLY,
        )

    if spec.license_status != LicenseStatus.APPROVED_OA:
        return AuthorizationDecision(
            source_id=spec.source_id,
            allowed=False,
            reason=f"license_status_blocked:{spec.license_status.value}",
            license_status=spec.license_status,
        )

    matched_pattern = _matches_prohibited_work(spec)
    if matched_pattern is not None:
        return AuthorizationDecision(
            source_id=spec.source_id,
            allowed=False,
            reason=f"prohibited_commercial_work:{matched_pattern}",
            license_status=LicenseStatus.PROHIBITED_COMMERCIAL,
        )

    if not _license_is_approved(spec.license_name):
        return AuthorizationDecision(
            source_id=spec.source_id,
            allowed=False,
            reason=f"unverified_license:{spec.license_name}",
            license_status=LicenseStatus.PROHIBITED_COMMERCIAL,
        )

    if not spec.license_url.startswith(("http://", "https://")):
        return AuthorizationDecision(
            source_id=spec.source_id,
            allowed=False,
            reason="missing_license_url",
            license_status=LicenseStatus.METADATA_ONLY,
        )

    return AuthorizationDecision(
        source_id=spec.source_id,
        allowed=True,
        reason="verified_open_access",
        license_status=LicenseStatus.APPROVED_OA,
    )


def verify_license_register(
    specs: list[SourceSpec],
) -> tuple[list[SourceSpec], list[AuthorizationDecision]]:
    """Partition ``specs`` into authorized OA sources and full decision audit rows."""
    approved: list[SourceSpec] = []
    decisions: list[AuthorizationDecision] = []
    for spec in specs:
        decision = authorize_source(spec)
        decisions.append(decision)
        if decision.allowed:
            approved.append(spec)
    return approved, decisions
