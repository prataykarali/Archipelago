"""ODS → KùzuDB Ingestion — Institutional Catalog Reports.

Implements KùzuDB node table creation and row ingestion for:
  - SubjectReport (subject-wise title counts)
  - JournalReport (journal titles / issue rows)
  - KeywordReport (titles-with-keyword lists)

ODS-1: schema validation via ods_parser (ideal + real KOHA exports).
ODS-2: empty-cell fallbacks + keyword dedup; incomplete rows are dropped + logged.
"""
from __future__ import annotations

import hashlib
from typing import Any

import kuzu

from archipelago.inference.ods_parser import (
    ODS_SCHEMA_SUBJECT,
    ODS_SCHEMA_JOURNAL,
    ODS_SCHEMA_KEYWORD,
    build_column_map,
    build_column_map_for_rows,
    clean_ods_row,
    deduplicate_keywords,
    read_ods_sheet,
    resolve_schema,
    sniff_schema,
    ODSParseError,
)


ODS_SCHEMA_DDL: dict[str, str] = {
    "SubjectReport": """
        CREATE NODE TABLE IF NOT EXISTS SubjectReport (
            id STRING PRIMARY KEY,
            department STRING,
            title_count INT64,
            volume_issue_count INT64
        )
    """,
    "JournalReport": """
        CREATE NODE TABLE IF NOT EXISTS JournalReport (
            id STRING PRIMARY KEY,
            journal_title STRING,
            issn STRING,
            issue_count INT64,
            publisher STRING
        )
    """,
    "KeywordReport": """
        CREATE NODE TABLE IF NOT EXISTS KeywordReport (
            id STRING PRIMARY KEY,
            title STRING,
            author STRING,
            subject_keyword STRING,
            call_number STRING
        )
    """,
}


def ensure_ods_schema(conn: kuzu.Connection) -> None:
    """Create ODS-related node tables if they don't exist."""
    for table_name, ddl in ODS_SCHEMA_DDL.items():
        try:
            conn.execute(ddl)
        except Exception as e:
            print(f"[ODS] Warning creating table {table_name}: {e}")


def _ods_id(prefix: str, *parts: str) -> str:
    raw = "_".join(str(p) for p in parts if p)
    hash_digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    stem = raw[:48].lower().replace(" ", "_").replace("/", "_")
    return f"ods_{prefix}_{stem}_{hash_digest}"


def _parse_int(val: Any) -> int:
    if val is None:
        return 0
    s = str(val).strip().replace(",", "")
    # Real journal exports store "Vol. 10, Issue. 4" — count as 1 issue row.
    if not s:
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        # Non-numeric issue labels still represent one observed issue.
        return 1 if s else 0


def ingest_ods_subject_report(conn: kuzu.Connection, rows: list[list[str]]) -> dict:
    """Validate schema, insert SubjectReport nodes. Drops incomplete rows."""
    ensure_ods_schema(conn)
    schema, col_map = build_column_map_for_rows(rows, preferred="subject_report")

    inserted = 0
    dropped = 0
    errors: list[str] = []

    for i, row in enumerate(rows[1:], 2):
        if not any(c.strip() for c in row):
            continue
        try:
            cleaned = clean_ods_row(row, col_map)
            dept = (
                cleaned.get("subject / department")
                or cleaned.get("subject")
                or ""
            ).strip()
            title_count = _parse_int(
                cleaned.get("title count") or cleaned.get("total titles") or "0"
            )
            vol_issue_count = _parse_int(cleaned.get("volume/issue count", "0"))

            if not dept:
                dropped += 1
                errors.append(f"Row {i}: empty department — dropped")
                continue

            record_id = _ods_id("subj", dept)
            conn.execute(
                """
                MERGE (s:SubjectReport {id: $id})
                ON CREATE SET
                    s.department = $department,
                    s.title_count = $title_count,
                    s.volume_issue_count = $volume_issue_count
                ON MATCH SET
                    s.department = $department,
                    s.title_count = $title_count,
                    s.volume_issue_count = $volume_issue_count
                """,
                parameters={
                    "id": record_id,
                    "department": dept,
                    "title_count": title_count,
                    "volume_issue_count": vol_issue_count,
                },
            )
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
            dropped += 1

    return {
        "inserted": inserted,
        "dropped": dropped,
        "errors": errors,
        "schema": schema.get("name"),
    }


def ingest_ods_journal_report(conn: kuzu.Connection, rows: list[list[str]]) -> dict:
    """Validate schema, insert JournalReport nodes.

    ODS-1: ideal schema requires ISSN; real KOHA issue exports lack ISSN and
    use per-issue rows — we accept them with ISSN fallback and aggregate counts.
    Incomplete rows (no journal title) are dropped + logged.
    """
    ensure_ods_schema(conn)
    schema, col_map = build_column_map_for_rows(rows, preferred="journal_report")

    # Aggregate real issue-level rows by journal title.
    aggregates: dict[str, dict[str, Any]] = {}
    dropped = 0
    errors: list[str] = []

    for i, row in enumerate(rows[1:], 2):
        if not any(c.strip() for c in row):
            continue
        try:
            cleaned = clean_ods_row(row, col_map)
            journal_title = (cleaned.get("journal title") or "").strip()
            if not journal_title:
                dropped += 1
                errors.append(f"Row {i}: missing journal title — dropped")
                continue

            issn = (cleaned.get("issn") or "").strip()
            # Ideal control path: if schema required ISSN and cell empty → drop.
            # Real issue exports never have ISSN column — fallback is OK.
            if "issn" in col_map and not issn:
                dropped += 1
                errors.append(f"Row {i}: missing ISSN — dropped from concept-linking")
                continue
            if not issn:
                issn = "0000-0000"

            publisher = (cleaned.get("publisher") or "Unknown Publisher").strip()
            issue_raw = cleaned.get("issue count") or cleaned.get("issue number/volume") or "1"
            issue_count = _parse_int(issue_raw)

            key = journal_title.lower()
            if key not in aggregates:
                aggregates[key] = {
                    "journal_title": journal_title,
                    "issn": issn,
                    "publisher": publisher,
                    "issue_count": 0,
                }
            aggregates[key]["issue_count"] += max(issue_count, 1)
            # Prefer a real ISSN over the placeholder if later rows provide one.
            if issn != "0000-0000":
                aggregates[key]["issn"] = issn
            if publisher and publisher != "Unknown Publisher":
                aggregates[key]["publisher"] = publisher
        except Exception as e:
            errors.append(f"Row {i}: {e}")
            dropped += 1

    inserted = 0
    for agg in aggregates.values():
        try:
            record_id = _ods_id("jour", agg["issn"], agg["journal_title"][:32])
            conn.execute(
                """
                MERGE (j:JournalReport {id: $id})
                ON CREATE SET
                    j.journal_title = $journal_title,
                    j.issn = $issn,
                    j.issue_count = $issue_count,
                    j.publisher = $publisher
                ON MATCH SET
                    j.journal_title = $journal_title,
                    j.issn = $issn,
                    j.issue_count = $issue_count,
                    j.publisher = $publisher
                """,
                parameters={
                    "id": record_id,
                    "journal_title": agg["journal_title"],
                    "issn": agg["issn"],
                    "issue_count": int(agg["issue_count"]),
                    "publisher": agg["publisher"],
                },
            )
            inserted += 1
        except Exception as e:
            errors.append(f"Aggregate {agg['journal_title']}: {e}")
            dropped += 1

    return {
        "inserted": inserted,
        "dropped": dropped,
        "errors": errors,
        "schema": schema.get("name"),
    }


def ingest_ods_keyword_report(conn: kuzu.Connection, rows: list[list[str]]) -> dict:
    """Validate schema, insert KeywordReport nodes with ODS-2 keyword dedup."""
    ensure_ods_schema(conn)
    schema, col_map = build_column_map_for_rows(rows, preferred="keyword_report")

    inserted = 0
    dropped = 0
    errors: list[str] = []

    for i, row in enumerate(rows[1:], 2):
        if not any(c.strip() for c in row):
            continue
        try:
            cleaned = clean_ods_row(row, col_map)
            title = (cleaned.get("title") or "").strip()
            if not title:
                dropped += 1
                errors.append(f"Row {i}: missing title — dropped")
                continue

            author = cleaned.get("author") or "Unknown / Institutional"
            subject_keyword_raw = cleaned.get("subject keyword") or "uncategorized"
            call_number = cleaned.get("call number") or "Unassigned"

            keywords_list = [k.strip() for k in subject_keyword_raw.split(",") if k.strip()]
            deduped_keywords = deduplicate_keywords(keywords_list)
            subject_keyword = ", ".join(deduped_keywords) if deduped_keywords else "uncategorized"

            record_id = _ods_id("keyw", title[:32], author[:16])
            conn.execute(
                """
                MERGE (k:KeywordReport {id: $id})
                ON CREATE SET
                    k.title = $title,
                    k.author = $author,
                    k.subject_keyword = $subject_keyword,
                    k.call_number = $call_number
                ON MATCH SET
                    k.title = $title,
                    k.author = $author,
                    k.subject_keyword = $subject_keyword,
                    k.call_number = $call_number
                """,
                parameters={
                    "id": record_id,
                    "title": title,
                    "author": author,
                    "subject_keyword": subject_keyword,
                    "call_number": call_number,
                },
            )
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
            dropped += 1

    return {
        "inserted": inserted,
        "dropped": dropped,
        "errors": errors,
        "schema": schema.get("name"),
    }


def sync_ods_reports_to_graph(
    conn: kuzu.Connection,
    filepaths: dict[str, str],
) -> dict[str, dict]:
    """Parse, validate, and ingest multiple ODS reports.

    Args:
        conn: KùzuDB connection.
        filepaths: Dict mapping report type to file path.
            E.g. {"subject_report": "/path/to/subject.ods", ...}
    """
    ensure_ods_schema(conn)
    results: dict[str, dict] = {}

    type_to_ingestor = {
        "subject_report": ingest_ods_subject_report,
        "journal_report": ingest_ods_journal_report,
        "keyword_report": ingest_ods_keyword_report,
    }

    for report_type, filepath in filepaths.items():
        if report_type not in type_to_ingestor:
            results[report_type] = {"error": f"Unknown report type: {report_type}"}
            continue
        try:
            rows = read_ods_sheet(filepath)
            detected = sniff_schema(rows)
            use_type = detected or report_type
            if detected and detected != report_type:
                print(
                    f"[ODS] Warning: file {filepath} has schema '{detected}' "
                    f"but was mapped as '{report_type}'. Using detected type."
                )
            result = type_to_ingestor[use_type](conn, rows)
            results[use_type] = result
        except ODSParseError as e:
            results[report_type] = {"error": str(e), "dropped": 0, "inserted": 0}
        except Exception as e:
            results[report_type] = {
                "error": f"Unexpected error: {e}",
                "dropped": 0,
                "inserted": 0,
            }

    return results


def default_docs_ods_paths(docs_dir: str | None = None) -> dict[str, str]:
    """Map report types → institutional ODS files under docs/ (excl. guides/reports)."""
    from pathlib import Path
    from archipelago.inference import state as st

    root = Path(docs_dir) if docs_dir else (st.BASE_DIR / "docs")
    mapping = {
        "subject_report": root / "SUBJECT-WISE TITLE COUNT-reportresults.ods",
        "journal_report": root / "JOURNALS TITLES AND ISSUE COUNTS-reportresults.ods",
        "keyword_report": root / "Titles List with specified keyword-reportresults.ods",
    }
    return {k: str(v) for k, v in mapping.items() if v.is_file()}
