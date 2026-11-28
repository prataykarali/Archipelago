"""Core domain constants and SourceSpec schema for Archipelago D14 corpus_v3_d14."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

CORPUS_VERSION_V3 = "corpus_v3_d14"
PARENT_CORPUS_VERSION = "corpus_v2_d10_3025"
PARENT_MANIFEST_REL_PATH = "docs/reports/D10_S4_CANDIDATE_PASSAGE_MANIFEST.json"
PARENT_HF_REPO_ID = "Prataykarali/Library_books"
PARENT_HF_REVISION = "b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd"

CANONICAL_DOMAINS: tuple[str, ...] = (
    "Operating Systems",
    "Database Systems",
    "Data Structures & Algorithms",
    "Computer Networks",
    "Compiler Design",
    "Automata Theory",
    "Mathematics for ML",
    "Probability & Statistics",
    "Information Security",
    "AI & Machine Learning",
    "Software Engineering",
    "Computer Architecture",
)


class LicenseStatus(StrEnum):
    """Legal reuse status for a candidate corpus source."""

    APPROVED_OA = "APPROVED_OA"
    PROHIBITED_COMMERCIAL = "PROHIBITED_COMMERCIAL"
    METADATA_ONLY = "METADATA_ONLY"


class SourceFormat(StrEnum):
    """Supported native document formats for extraction."""

    PDF = "pdf"
    HTML = "html"
    TXT = "txt"
    CATALOG_CARD = "catalog_card"


@dataclass(frozen=True)
class SourceSpec:
    """Immutable specification of a candidate corpus source."""

    source_id: str
    doc_id: str
    title: str
    authors: str
    domain: str
    secondary_domains: tuple[str, ...]
    source_format: SourceFormat
    license_name: str
    license_status: LicenseStatus
    license_url: str
    canonical_url: str
    origin: str  # "baseline_v2_hf_cache" | "d14_oa_acquisition" | "excluded_commercial"
    independent_group: str
    notes: str = ""
    local_rel_path: str = ""
    extra_urls: tuple[str, ...] = field(default_factory=tuple)
