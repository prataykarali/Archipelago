"""Content, byte-level, and honesty verification helpers for hosted E2E checks.

One concern: deterministic validation of PDF bytes, XLSX workbooks, readiness
revision separation, abstention payloads, and secret redaction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import io
import json
import re
from typing import Any
import zipfile

STREAM_START_MARKER = "[STREAM_START]"

PDF_MAGIC_PREFIX = b"%PDF-"
PDF_EOF_MARKER = b"%%EOF"
PDF_MIN_VALID_BYTES = 100
PDF_EOF_TAIL_BYTES = 2048
XLSX_ZIP_MAGIC = b"PK\x03\x04"
XLSX_MIN_VALID_BYTES = 256
XLSX_REQUIRED_ENTRIES = ("xl/workbook.xml", "[Content_Types].xml")
ALLOWED_VERDICTS = frozenset({"PASS", "FAIL", "BLOCKED"})
UNVERSIONED_RELEASE_VALUES = frozenset({"", "unversioned", "unknown", "none"})

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_PUBLISHABLE_KEY_RE = re.compile(r"\bsb_(publishable|secret)_[A-Za-z0-9_-]+\b")
_COOKIE_TOKEN_RE = re.compile(r"(archipelago_session=)[^;\s]+", re.IGNORECASE)


@dataclass
class JourneyResult:
    """Structured result for one hosted E2E user journey."""

    journey_id: str
    title: str
    verdict: str
    environment: str
    requires_auth: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    blocker_detail: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in ALLOWED_VERDICTS:
            raise ValueError(f"Invalid verdict: {self.verdict!r}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a redacted plain dictionary."""
        return redact_evidence(asdict(self))


def redact_text(text: str) -> str:
    """Redact emails, bearer tokens, JWTs, session cookies, and Supabase keys."""
    cleaned = _BEARER_RE.sub(r"\1[REDACTED]", text)
    cleaned = _JWT_RE.sub("[REDACTED_JWT]", cleaned)
    cleaned = _PUBLISHABLE_KEY_RE.sub("sb_\\1_[REDACTED]", cleaned)
    cleaned = _COOKIE_TOKEN_RE.sub(r"\1[REDACTED]", cleaned)
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    return cleaned


def redact_evidence(value: Any) -> Any:
    """Recursively redact sensitive strings inside nested evidence structures."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_evidence(item) for item in value]
    if isinstance(value, tuple):
        return [redact_evidence(item) for item in value]
    if isinstance(value, dict):
        return {str(k): redact_evidence(v) for k, v in value.items()}
    return value


def verify_pdf_bytes(raw_bytes: bytes, requested_page: int = 1) -> dict[str, Any]:
    """Verify raw bytes represent a real PDF document with the requested page.

    Args:
        raw_bytes: Raw HTTP response body bytes.
        requested_page: 1-based page number expected to exist in the PDF.

    Returns:
        Dictionary with ``valid`` boolean, byte length, magic check, and page count.
    """
    size = len(raw_bytes)
    has_magic = raw_bytes.startswith(PDF_MAGIC_PREFIX)
    has_eof = (
        PDF_EOF_MARKER in raw_bytes[-PDF_EOF_TAIL_BYTES:] if size >= len(PDF_EOF_MARKER) else False
    )
    page_count: int | None = None
    parser_error: str | None = None

    if has_magic and size >= PDF_MIN_VALID_BYTES:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw_bytes))
            page_count = len(reader.pages)
        except ImportError:
            # Fallback structural check when pypdf is absent.
            page_count = raw_bytes.count(b"/Type /Page") - raw_bytes.count(b"/Type /Pages")
            if page_count <= 0:
                page_count = None
        except Exception as exc:
            parser_error = f"{type(exc).__name__}: {exc}"

    page_in_range = page_count is not None and requested_page >= 1 and requested_page <= page_count
    valid = (
        has_magic
        and size >= PDF_MIN_VALID_BYTES
        and (has_eof or page_count is not None)
        and parser_error is None
        and (page_in_range if page_count is not None else True)
    )
    return {
        "valid": valid,
        "byte_length": size,
        "has_pdf_magic": has_magic,
        "has_eof_marker": has_eof,
        "page_count": page_count,
        "requested_page": requested_page,
        "page_in_range": page_in_range,
        "parser_error": parser_error,
    }


def verify_xlsx_bytes(raw_bytes: bytes) -> dict[str, Any]:
    """Verify raw bytes represent a valid OOXML Excel (.xlsx) workbook.

    Args:
        raw_bytes: Raw HTTP response body bytes.

    Returns:
        Dictionary with ``valid`` boolean, zip entry checks, and sheet names.
    """
    size = len(raw_bytes)
    has_zip_magic = raw_bytes.startswith(XLSX_ZIP_MAGIC)
    entries: list[str] = []
    sheet_names: list[str] = []
    has_required_xml = False
    has_worksheet_xml = False
    parser_error: str | None = None

    if has_zip_magic and size >= XLSX_MIN_VALID_BYTES:
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zf:
                entries = zf.namelist()
            has_required_xml = all(req in entries for req in XLSX_REQUIRED_ENTRIES)
            has_worksheet_xml = any(
                name.startswith("xl/worksheets/") and name.endswith(".xml") for name in entries
            )
        except (zipfile.BadZipFile, OSError) as exc:
            parser_error = f"{type(exc).__name__}: {exc}"

    if has_required_xml and has_worksheet_xml and parser_error is None:
        try:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
            sheet_names = list(wb.sheetnames)
            wb.close()
        except ImportError:
            sheet_names = []
        except Exception as exc:
            parser_error = f"{type(exc).__name__}: {exc}"

    valid = (
        has_zip_magic
        and size >= XLSX_MIN_VALID_BYTES
        and has_required_xml
        and has_worksheet_xml
        and parser_error is None
    )
    return {
        "valid": valid,
        "byte_length": size,
        "has_zip_magic": has_zip_magic,
        "has_required_xml": has_required_xml,
        "has_worksheet_xml": has_worksheet_xml,
        "sheet_names": sheet_names,
        "zip_entry_count": len(entries),
        "parser_error": parser_error,
    }


def verify_readiness_separation(
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Verify deployed code revision separately from graph export fingerprint.

    Args:
        headers: HTTP response headers (case-insensitive lookup performed).
        payload: Parsed JSON body from ``/api/readiness``.

    Returns:
        Structured dictionary separating ``deployed_revision`` and
        ``graph_fingerprint`` and noting whether revision is explicitly versioned.
    """
    lower_headers = {k.lower(): v for k, v in headers.items()}
    deployed_revision = str(
        lower_headers.get("x-archipelago-release")
        or payload.get("deployed_revision")
        or payload.get("release_sha")
        or ""
    ).strip()
    graph_fingerprint = str(payload.get("graph_version") or "").strip()
    revision_is_versioned = deployed_revision.lower() not in UNVERSIONED_RELEASE_VALUES
    revision_distinct_from_graph = bool(
        deployed_revision and graph_fingerprint and deployed_revision != graph_fingerprint
    )
    return {
        "deployed_revision": deployed_revision or "missing",
        "deployed_revision_versioned": revision_is_versioned,
        "graph_fingerprint": graph_fingerprint or "missing",
        "revision_distinct_from_graph": revision_distinct_from_graph,
        "vercel_deployment_id": lower_headers.get("x-vercel-id", ""),
        "concepts": payload.get("concepts"),
        "corpus_source": (payload.get("corpus") or {}).get("source")
        if isinstance(payload.get("corpus"), dict)
        else None,
        "pearson_books": payload.get("pearson_books"),
    }


def parse_chat_response(raw_text: str) -> dict[str, Any]:
    """Parse ``/api/chat`` responses (both ``[STREAM_START]`` framed and plain JSON)."""
    text = raw_text.strip()
    if not text:
        return {}
    meta_part = (
        text.split(STREAM_START_MARKER, 1)[0].strip() if STREAM_START_MARKER in text else text
    )
    try:
        parsed = json.loads(meta_part)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def verify_abstention_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Verify an unsupported-topic (Q39) chat response abstains cleanly.

    Clean abstention requires zero citations and zero fabricated graph nodes/edges.
    """
    citations = payload.get("citations") or payload.get("sources") or []
    graph = payload.get("graph") or {}
    nodes = (graph.get("nodes") or []) if isinstance(graph, dict) else []
    edges = (graph.get("edges") or []) if isinstance(graph, dict) else []
    trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
    render_graph = payload.get("render_graph")
    zero_citations = isinstance(citations, list) and len(citations) == 0
    zero_graph_nodes = isinstance(nodes, list) and len(nodes) == 0
    zero_graph_edges = isinstance(edges, list) and len(edges) == 0
    graph_not_rendered = render_graph is not True
    return {
        "clean_abstention": (
            zero_citations and zero_graph_nodes and zero_graph_edges and graph_not_rendered
        ),
        "citation_count": len(citations) if isinstance(citations, list) else -1,
        "graph_node_count": len(nodes) if isinstance(nodes, list) else -1,
        "graph_edge_count": len(edges) if isinstance(edges, list) else -1,
        "render_graph": render_graph,
        "grounding_status": (
            trace.get("grounding_status")
            or payload.get("grounding_status")
            or payload.get("intent")
        ),
        "provenance_status": trace.get("provenance_status"),
        "claim_support_status": trace.get("claim_support_status"),
    }
