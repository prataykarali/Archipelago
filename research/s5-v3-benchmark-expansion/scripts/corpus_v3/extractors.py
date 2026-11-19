"""Deterministic PDF and Markdown OA extractors with eligibility enforcement."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

import fitz

from .constants import (
    EXCLUDED_PATH_SUBSTRINGS,
    MIN_REAL_SOURCE_BYTES,
    PROVENANCE_MARKDOWN_OA_EXTRACTED,
    PROVENANCE_PDF_EXTRACTED,
    VALID_PROVENANCE_CLASSES,
)
from .models import DocumentCompleteness, PageText, SourceDocumentSpec

LIGATURE_MAP: dict[str, str] = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
    "\u00ad": "",
}
CID_ARTIFACT_RE = re.compile(r"\(cid:\d+\)")
HYPHEN_LINEBREAK_RE = re.compile(r"([A-Za-z])-\n([a-z])")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
EXCESS_NEWLINE_RE = re.compile(r"\n{3,}")
HASH_CHUNK_BYTES = 65536


class SourceEligibilityError(ValueError):
    """Raised when an ineligible, copyrighted, stub, or tampered source is passed."""


def compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 of a file in deterministic streaming chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(HASH_CHUNK_BYTES)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def resolve_source_path(spec: SourceDocumentSpec, repo_root: Path) -> Path:
    """Resolve a source path relative to repo_root when not absolute."""
    raw_path = Path(spec.path)
    return raw_path if raw_path.is_absolute() else (repo_root / raw_path)


def validate_source_eligibility(
    spec: SourceDocumentSpec,
    repo_root: Path,
    verify_sha256: bool = True,
) -> tuple[Path, str]:
    """Enforce source eligibility, exclusion guards, and optional SHA-256 match.

    Returns:
        Tuple of (resolved_path, actual_sha256).

    Raises:
        SourceEligibilityError: If source is ineligible, matches exclusion rules,
            missing, too small (synthetic stub), or fails SHA-256 verification.
    """
    if not spec.eligible:
        reason = spec.exclusion_reason or "marked eligible=False"
        raise SourceEligibilityError(f"Source {spec.doc_id} excluded: {reason}")

    if spec.provenance_class not in VALID_PROVENANCE_CLASSES:
        raise SourceEligibilityError(
            f"Source {spec.doc_id} has invalid provenance_class: {spec.provenance_class}"
        )

    normalized_path = spec.path.lower().replace("\\", "/")
    for forbidden in EXCLUDED_PATH_SUBSTRINGS:
        if forbidden in normalized_path:
            raise SourceEligibilityError(
                f"Source {spec.doc_id} matches excluded path rule '{forbidden}': {spec.path}"
            )

    resolved = resolve_source_path(spec, repo_root)
    if not resolved.is_file():
        raise SourceEligibilityError(f"Source {spec.doc_id} does not exist on disk: {resolved}")

    byte_size = resolved.stat().st_size
    if byte_size < MIN_REAL_SOURCE_BYTES:
        raise SourceEligibilityError(
            f"Source {spec.doc_id} is smaller than {MIN_REAL_SOURCE_BYTES} bytes "
            f"({byte_size} B); likely synthetic stub: {resolved}"
        )

    actual_sha256 = compute_file_sha256(resolved)
    if verify_sha256 and spec.expected_sha256 and actual_sha256 != spec.expected_sha256:
        raise SourceEligibilityError(
            f"Source {spec.doc_id} SHA-256 mismatch: expected "
            f"{spec.expected_sha256}, got {actual_sha256}"
        )

    return resolved, actual_sha256


def clean_extracted_text(raw_text: str) -> tuple[str, bool, bool]:
    """Normalize ligatures/hyphenation and detect encoding artifacts.

    Returns:
        Tuple of (cleaned_text, had_ligature_repairs, had_encoding_artifacts).
    """
    had_ligature_repairs = any(ch in raw_text for ch in LIGATURE_MAP)
    had_encoding_artifacts = ("\ufffd" in raw_text) or bool(CID_ARTIFACT_RE.search(raw_text))

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    for src, dst in LIGATURE_MAP.items():
        if src in text:
            text = text.replace(src, dst)

    text = HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    lines = [MULTI_SPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = EXCESS_NEWLINE_RE.sub("\n\n", text).strip()
    return text, had_ligature_repairs, had_encoding_artifacts


def extract_pdf_pages(path: Path) -> list[PageText]:
    """Extract deterministic 1-based per-page text from a PDF via PyMuPDF."""
    pages: list[PageText] = []
    with fitz.open(str(path)) as document:
        for idx in range(len(document)):
            raw_text = str(document[idx].get_text("text"))
            cleaned, repaired, artifacts = clean_extracted_text(raw_text)
            pages.append(
                PageText(
                    page_number=idx + 1,
                    raw_text=raw_text,
                    cleaned_text=cleaned,
                    char_count=len(cleaned),
                    had_ligature_repairs=repaired,
                    had_encoding_artifacts=artifacts,
                )
            )
    return pages


def extract_markdown_pages(path: Path) -> list[PageText]:
    """Extract deterministic text from an open-access Markdown file (page 1)."""
    raw_text = path.read_text(encoding="utf-8")
    cleaned, repaired, artifacts = clean_extracted_text(raw_text)
    return [
        PageText(
            page_number=1,
            raw_text=raw_text,
            cleaned_text=cleaned,
            char_count=len(cleaned),
            had_ligature_repairs=repaired,
            had_encoding_artifacts=artifacts,
        )
    ]


def extract_document(
    spec: SourceDocumentSpec,
    resolved_path: Path,
) -> tuple[list[PageText], DocumentCompleteness]:
    """Extract pages and compute document completeness metrics."""
    if spec.source_format == "pdf":
        if spec.provenance_class != PROVENANCE_PDF_EXTRACTED:
            raise SourceEligibilityError(
                f"PDF source {spec.doc_id} must use provenance_class '{PROVENANCE_PDF_EXTRACTED}'"
            )
        pages = extract_pdf_pages(resolved_path)
    elif spec.source_format == "markdown":
        if spec.provenance_class != PROVENANCE_MARKDOWN_OA_EXTRACTED:
            raise SourceEligibilityError(
                f"Markdown source {spec.doc_id} must use provenance_class "
                f"'{PROVENANCE_MARKDOWN_OA_EXTRACTED}'"
            )
        pages = extract_markdown_pages(resolved_path)
    else:
        raise SourceEligibilityError(
            f"Unsupported source_format '{spec.source_format}' for {spec.doc_id}"
        )

    empty_pages = tuple(p.page_number for p in pages if p.char_count == 0)
    non_empty = len(pages) - len(empty_pages)
    total_chars = sum(p.char_count for p in pages)
    mean_chars = round(total_chars / non_empty, 2) if non_empty > 0 else 0.0
    completeness = DocumentCompleteness(
        doc_id=spec.doc_id,
        source_format=spec.source_format,
        total_pages=len(pages),
        non_empty_pages=non_empty,
        empty_pages=empty_pages,
        total_chars=total_chars,
        mean_chars_per_non_empty_page=mean_chars,
        pages_with_ligature_repairs=sum(1 for p in pages if p.had_ligature_repairs),
        pages_with_encoding_artifacts=sum(1 for p in pages if p.had_encoding_artifacts),
    )
    return pages, completeness
