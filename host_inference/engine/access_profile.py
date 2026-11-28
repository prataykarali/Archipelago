"""Access-profile policy and D14 OA/license registry for SIGIR open-access isolation.

One concern: read ``ARCHIPELAGO_ACCESS_PROFILE``, load ``D14_SOURCE_INVENTORY.csv``
and ``D14_SOURCE_LICENSE_REGISTER.csv``, and provide pure helpers that enforce
open-access isolation while preserving UEM institutional mode.
"""

from __future__ import annotations

import csv
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from .docmap import hf_doc_path

ACCESS_PROFILE_ENV = "ARCHIPELAGO_ACCESS_PROFILE"
ACCESS_PROFILE_INSTITUTIONAL = "institutional"
ACCESS_PROFILE_OPEN_ACCESS = "open_access"

_OPEN_ACCESS_ALIASES = frozenset({"open_access", "open-access", "sigir_open_access", "open"})
_PEARSON_URL_MARKERS = ("/open/", "elibrary.in.pearson.com", "ebooks.elibrary.in.pearson.com")
_PEARSON_PUBLISHER_MARKER = "pearson"
_INSTITUTIONAL_RESOURCE_TYPE = "institutional_e_book"
_PEARSON_SOURCE_CATEGORY = "pearson_catalogue_only"
_RESTRICTED_ARTIFACT_MARKERS = (
    "librarian_uploads/",
    "pearson",
    "/open/",
    "pilot/silberschatz_",
    "silberschatz",
    "ramakrishnan",
    "tanenbaum",
    "hopcroft",
    "forouzan",
    "stallings",
    "elmasri",
    "computer_networks_tanenbaum",
    "doc_computer_networks_",
    "doc_introduction_to_the_design_and",
    "compilers_principles_techniques_tools_aho",
    "doc_compilers_principles_",
    "doc_fundamentals_of_database_",
    "doc_cryptography_and_network_security_",
    "doc_data_and_computer_communications",
    "doc_computer_system_architecture_",
    "doc_operating_systems_internals_",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES_D14 = Path(__file__).resolve().parents[1] / "fixtures" / "d14"
_D14_INVENTORY_PATH = (
    _REPO_ROOT / "docs" / "reports" / "d14" / "D14_SOURCE_INVENTORY.csv"
    if (_REPO_ROOT / "docs" / "reports" / "d14" / "D14_SOURCE_INVENTORY.csv").is_file()
    else _FIXTURES_D14 / "D14_SOURCE_INVENTORY.csv"
)
_D14_LICENSE_PATH = (
    _REPO_ROOT / "docs" / "reports" / "d14" / "D14_SOURCE_LICENSE_REGISTER.csv"
    if (_REPO_ROOT / "docs" / "reports" / "d14" / "D14_SOURCE_LICENSE_REGISTER.csv").is_file()
    else _FIXTURES_D14 / "D14_SOURCE_LICENSE_REGISTER.csv"
)


def _parse_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else None


@lru_cache(maxsize=1)
def _load_d14_tables() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Load and index ``D14_SOURCE_INVENTORY.csv`` joined with license metadata."""
    licenses: dict[str, dict[str, str]] = {}
    if _D14_LICENSE_PATH.is_file():
        with _D14_LICENSE_PATH.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                sid = str(row.get("source_id") or "").strip().lower()
                if sid:
                    licenses[sid] = dict(row)

    by_source_id: dict[str, dict[str, Any]] = {}
    alias_to_sid: dict[str, str] = {}
    if not _D14_INVENTORY_PATH.is_file():
        return by_source_id, alias_to_sid

    with _D14_INVENTORY_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sid = str(row.get("source_id") or "").strip().lower()
            doc_id = str(row.get("doc_id") or "").strip()
            if not sid:
                continue
            lic = licenses.get(sid, {})
            gate_allowed = str(lic.get("gate_allowed") or "").strip().lower() == "true"
            availability = str(row.get("content_availability") or "").strip().upper()
            lic_status = str(lic.get("license_status") or "").strip().upper()
            source_fmt = str(row.get("source_format") or "").strip().lower()
            extracted_units = _parse_int(row.get("extracted_units")) or 0
            origin = str(row.get("origin") or "").strip().lower()
            entry: dict[str, Any] = {
                "source_id": sid,
                "doc_id": doc_id,
                "title": str(row.get("title") or "").strip(),
                "authors": str(row.get("authors") or "").strip(),
                "domain": str(row.get("domain") or "").strip(),
                "source_format": source_fmt,
                "origin": origin,
                "content_availability": availability,
                "acquisition_status": str(row.get("acquisition_status") or "").strip().lower(),
                "extracted_units": extracted_units,
                "page_count": extracted_units if source_fmt == "pdf" and extracted_units > 0 else None,
                "canonical_url": str(row.get("canonical_url") or "").strip(),
                "license_name": str(lic.get("license_name") or "").strip(),
                "license_status": lic_status,
                "license_url": str(lic.get("license_url") or "").strip(),
                "gate_allowed": gate_allowed,
                "is_approved_oa": (
                    gate_allowed
                    and lic_status == "APPROVED_OA"
                    and availability == "FULL_TEXT_RETRIEVABLE"
                ),
                "is_excluded_commercial": (
                    (not gate_allowed)
                    or lic_status == "METADATA_ONLY"
                    or availability == "METADATA_ONLY_CATALOG_CARD"
                    or origin == "excluded_commercial"
                ),
            }
            by_source_id[sid] = entry
            alias_to_sid[sid] = sid
            if doc_id:
                low_doc = doc_id.lower().lstrip("/")
                alias_to_sid[low_doc] = sid
                alias_to_sid[low_doc.rsplit("/", 1)[-1]] = sid
                if low_doc.startswith("books/"):
                    alias_to_sid[low_doc.removeprefix("books/")] = sid
    return by_source_id, alias_to_sid


def load_d14_source_registry() -> dict[str, dict[str, Any]]:
    """Return all ``corpus_v3_d14`` inventory entries keyed by ``source_id``."""
    by_sid, _aliases = _load_d14_tables()
    return {sid: dict(entry) for sid, entry in by_sid.items()}


def lookup_d14_source(identifier: object) -> dict[str, Any] | None:
    """Resolve a ``source_id``, ``doc_id``, or filename against the D14 source registry."""
    raw = str(identifier or "").strip().lower().lstrip("/")
    if not raw:
        return None
    by_sid, aliases = _load_d14_tables()
    candidates = [raw, raw.rsplit("/", 1)[-1]]
    if raw.startswith("books/"):
        candidates.append(raw.removeprefix("books/"))
    mapped = hf_doc_path(raw).lower().lstrip("/")
    if mapped and mapped != raw:
        candidates.extend([mapped, mapped.rsplit("/", 1)[-1]])
    for key in candidates:
        sid = aliases.get(key)
        if sid and sid in by_sid:
            return dict(by_sid[sid])
    return None


def _extract_identifiers(record_or_id: object) -> list[str]:
    if isinstance(record_or_id, dict):
        vals = (record_or_id.get("source_id"), record_or_id.get("doc_id"), record_or_id.get("id"))
        return [str(v).strip() for v in vals if v]
    raw = str(record_or_id or "").strip()
    return [raw] if raw else []


def is_d14_excluded_commercial(record_or_id: object) -> bool:
    """True when ``record_or_id`` is one of the 12 D14 excluded commercial holdings."""
    for ident in _extract_identifiers(record_or_id):
        low = ident.lower().lstrip("/")
        if low.startswith(("metadata_only/", "excluded_")):
            return True
        entry = lookup_d14_source(ident)
        if entry is not None and entry["is_excluded_commercial"]:
            return True
    return False


def is_d14_approved_oa(record_or_id: object) -> bool:
    """True when ``record_or_id`` is one of the 68 approved full-text D14 OA sources."""
    for ident in _extract_identifiers(record_or_id):
        entry = lookup_d14_source(ident)
        if entry is not None:
            return bool(entry["is_approved_oa"])
    return False


def d14_canonical_oa_url(record_or_id: object) -> str:
    """Return the verified HTTPS canonical OA URL for an approved D14 source, else empty."""
    for ident in _extract_identifiers(record_or_id):
        entry = lookup_d14_source(ident)
        if entry is not None and entry["is_approved_oa"]:
            url = str(entry.get("canonical_url") or "").strip()
            if url.startswith("https://") and not is_pearson_url(url):
                return url
    return ""


def is_restricted_artifact_path(path: object) -> bool:
    """True when ``path`` references a restricted/institutional or private upload artifact."""
    low = str(path or "").strip().lower()
    if not low:
        return False
    return any(marker in low for marker in _RESTRICTED_ARTIFACT_MARKERS)


def is_unauthorized_stub(record_or_id: object) -> bool:
    """True when ``record_or_id`` is an excluded commercial, legacy ``doc_*``, or pilot stub."""
    for ident in _extract_identifiers(record_or_id):
        if is_d14_approved_oa(ident):
            return False
        low = ident.strip().lower().lstrip("/")
        if not low:
            continue
        if is_d14_excluded_commercial(low) or is_restricted_artifact_path(low):
            return True
        if low.startswith(("pilot/", "metadata_only/", "excluded_")):
            return True
        if low.startswith("doc_") and not low.endswith(".pdf"):
            return True
    return False


def active_access_profile() -> str:
    """Return ``open_access`` or ``institutional`` (default) from the environment."""
    raw = os.getenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_INSTITUTIONAL).strip().lower()
    if raw in _OPEN_ACCESS_ALIASES:
        return ACCESS_PROFILE_OPEN_ACCESS
    return ACCESS_PROFILE_INSTITUTIONAL


def is_open_access_profile() -> bool:
    """True when the deployment is restricted to open-access corpus sources only."""
    return active_access_profile() == ACCESS_PROFILE_OPEN_ACCESS


def is_pearson_url(url: object) -> bool:
    """True when ``url`` points to an institutional ``/open/`` or Pearson reader route."""
    text = str(url or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in _PEARSON_URL_MARKERS)


def is_institutional_card(card: object) -> bool:
    """True when ``card`` represents a Pearson or closed-source institutional e-book."""
    if not isinstance(card, dict):
        return False
    if card.get("is_pearson") or card.get("isPearson"):
        return True
    if str(card.get("source_category") or "").strip().lower() == _PEARSON_SOURCE_CATEGORY:
        return True
    if str(card.get("resource_type") or "").strip().lower() == _INSTITUTIONAL_RESOURCE_TYPE:
        return True
    if _PEARSON_PUBLISHER_MARKER in str(card.get("publisher") or "").strip().lower():
        return True
    for field in ("url", "pdf_url", "open_url", "reader_url", "reader_base_url"):
        if is_pearson_url(card.get(field)):
            return True
    return False


def filter_open_access_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop live Pearson ``/open/`` citations in ``open_access`` mode (retain metadata-only)."""
    if not is_open_access_profile():
        return list(citations)
    return [
        c
        for c in citations
        if isinstance(c, dict)
        and (is_d14_excluded_commercial(c) or not is_institutional_card(c))
    ]


def strip_institutional_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach access-profile flags and strip closed-source cards in ``open_access`` mode."""
    profile = active_access_profile()
    open_only = profile == ACCESS_PROFILE_OPEN_ACCESS
    payload["access_profile"] = profile
    payload["open_access_only"] = open_only
    if not open_only:
        return payload
    if isinstance(payload.get("citations"), list):
        payload["citations"] = filter_open_access_citations(payload["citations"])
    for key in ("inventory", "digital_resources", "inventory_cards"):
        if isinstance(payload.get(key), list):
            payload[key] = [item for item in payload[key] if not is_institutional_card(item)]
    return payload


__all__ = [
    "ACCESS_PROFILE_ENV",
    "ACCESS_PROFILE_INSTITUTIONAL",
    "ACCESS_PROFILE_OPEN_ACCESS",
    "active_access_profile",
    "d14_canonical_oa_url",
    "filter_open_access_citations",
    "is_d14_approved_oa",
    "is_d14_excluded_commercial",
    "is_institutional_card",
    "is_open_access_profile",
    "is_pearson_url",
    "is_restricted_artifact_path",
    "is_unauthorized_stub",
    "load_d14_source_registry",
    "lookup_d14_source",
    "strip_institutional_payload",
]
