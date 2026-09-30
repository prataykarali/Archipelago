"""Catalog schema definition for KùzuDB institutional catalog tables."""
from __future__ import annotations
from typing import Any


def create_schema(conn: Any) -> None:
    """Create node and relationship tables for institutional library catalog."""
    ddl_statements = [
        """
        CREATE NODE TABLE IF NOT EXISTS Subject (
            id STRING PRIMARY KEY,
            subject_name STRING,
            total_titles INT64
        )
        """,
        """
        CREATE NODE TABLE IF NOT EXISTS Resource (
            id STRING PRIMARY KEY,
            title STRING,
            author STRING,
            copyright_year INT64,
            publisher STRING,
            biblionumber STRING,
            total_copies INT64,
            available_copies INT64,
            barcodes STRING,
            overdue_items INT64,
            is_periodical BOOLEAN
        )
        """,
        """
        CREATE NODE TABLE IF NOT EXISTS Document (
            id STRING PRIMARY KEY,
            doc_hash STRING,
            page_count INT64,
            title STRING,
            edition STRING,
            page_label_map STRING,
            pdf_url STRING
        )
        """,
        """
        CREATE REL TABLE IF NOT EXISTS CATEGORIZES (
            FROM Subject TO Resource
        )
        """,
        """
        CREATE REL TABLE IF NOT EXISTS PROVIDES_TEXT (
            FROM Resource TO Document,
            pdf_url STRING
        )
        """,
    ]
    for ddl in ddl_statements:
        try:
            conn.execute(ddl)
        except Exception:
            pass
