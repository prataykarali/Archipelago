"""Catalog ingestion module for Subject and Resource nodes."""
from __future__ import annotations

import math
import os
import re
from typing import Any
import kuzu
import pandas as pd


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    return s if s else None


def _resource_id_from_title(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_")
    return f"res_{slug}" if slug else "res_unknown"


def _subject_id_from_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return f"subj_{slug}" if slug else "subj_unknown"


def ingest_subjects(db_path: str, filepath: str) -> dict[str, int]:
    """Ingest subjects from an ODS/Excel file into KùzuDB Subject table."""
    try:
        df = pd.read_excel(filepath, engine="odf")
    except Exception:
        df = pd.read_excel(filepath)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    merged = 0
    errors = 0
    skipped = 0

    # Ensure header column identification
    subj_col = df.columns[0]
    titles_col = df.columns[1] if len(df.columns) > 1 else None

    for _, row in df.iterrows():
        raw_name = row[subj_col]
        clean_name = _clean_str(raw_name)
        if not clean_name:
            skipped += 1
            continue

        raw_count = row[titles_col] if titles_col is not None else 0
        try:
            total_titles = int(raw_count) if (raw_count is not None and not (isinstance(raw_count, float) and math.isnan(raw_count))) else 0
        except Exception:
            total_titles = 0

        subj_id = _subject_id_from_name(clean_name)
        clean_name_esc = clean_name.replace("'", "\\'")

        query = f"""
        MERGE (s:Subject {{id: '{subj_id}'}})
        ON CREATE SET s.subject_name = '{clean_name_esc}', s.total_titles = {total_titles}
        ON MATCH SET s.subject_name = '{clean_name_esc}', s.total_titles = {total_titles}
        """
        try:
            conn.execute(query)
            merged += 1
        except Exception:
            errors += 1

    del conn, db
    return {"merged": merged, "errors": errors, "skipped": skipped}


def ingest_titles(db_path: str, filepath: str, subject_ods: str | None = None) -> dict[str, int]:
    """Ingest titles from an ODS/Excel file into KùzuDB Resource table and CATEGORIZES edges."""
    try:
        df = pd.read_excel(filepath, engine="odf")
    except Exception:
        df = pd.read_excel(filepath)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    resources_count = 0
    errors = 0

    # Determine columns
    # Expected: Subject, Title, Author, Copyright Year
    subj_col = df.columns[0]
    title_col = df.columns[1]
    author_col = df.columns[2] if len(df.columns) > 2 else None
    year_col = df.columns[3] if len(df.columns) > 3 else None

    for _, row in df.iterrows():
        title = _clean_str(row[title_col])
        if not title:
            continue

        subj_name = _clean_str(row[subj_col]) or "General"
        subj_id = _subject_id_from_name(subj_name)
        subj_esc = subj_name.replace("'", "\\'")

        author = _clean_str(row[author_col]) if author_col else "Unknown"
        author_esc = (author or "Unknown").replace("'", "\\'")

        raw_year = row[year_col] if year_col else None
        try:
            year = int(raw_year) if (raw_year is not None and not (isinstance(raw_year, float) and math.isnan(raw_year))) else 0
        except Exception:
            year = 0

        res_id = _resource_id_from_title(title)
        title_esc = title.replace("'", "\\'")

        # Ensure Subject exists
        conn.execute(f"MERGE (s:Subject {{id: '{subj_id}'}}) ON CREATE SET s.subject_name = '{subj_esc}', s.total_titles = 0")

        # Merge Resource
        res_query = f"""
        MERGE (r:Resource {{id: '{res_id}'}})
        ON CREATE SET r.title = '{title_esc}', r.author = '{author_esc}', r.copyright_year = {year},
                      r.publisher = 'Unknown', r.biblionumber = '0', r.total_copies = 1,
                      r.available_copies = 1, r.barcodes = '[]', r.overdue_items = 0, r.is_periodical = false
        ON MATCH SET r.title = '{title_esc}', r.author = '{author_esc}', r.copyright_year = {year}
        """
        conn.execute(res_query)

        # Merge CATEGORIZES edge
        cat_query = f"""
        MATCH (s:Subject {{id: '{subj_id}'}}), (r:Resource {{id: '{res_id}'}})
        MERGE (s)-[:CATEGORIZES]->(r)
        """
        conn.execute(cat_query)
        resources_count += 1

    del conn, db
    return {"resources": resources_count, "errors": errors}
