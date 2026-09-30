"""Catalog bridge linking physical Resources to Document nodes in KùzuDB."""
from __future__ import annotations

import re
from typing import Any
import kuzu
from thefuzz import fuzz


def link_resource_to_document(
    db_path: str, resource_title: str, doc_id: str, pdf_url: str | None = None
) -> bool:
    """Explicitly link a Resource node to a Document node via PROVIDES_TEXT."""
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    title_esc = resource_title.replace("'", "\\'")
    doc_esc = doc_id.replace("'", "\\'")
    url_val = f"'{pdf_url}'" if pdf_url else "NULL"

    try:
        # Update Document pdf_url if provided
        if pdf_url:
            conn.execute(f"MATCH (d:Document {{id: '{doc_esc}'}}) SET d.pdf_url = {url_val}")

        # Create PROVIDES_TEXT edge
        conn.execute(f"""
            MATCH (r:Resource), (d:Document {{id: '{doc_esc}'}})
            WHERE lower(r.title) = lower('{title_esc}')
            MERGE (r)-[p:PROVIDES_TEXT]->(d)
            SET p.pdf_url = {url_val}
        """)
        del conn, db
        return True
    except Exception:
        del conn, db
        return False


def auto_link_resources(db_path: str) -> dict[str, int]:
    """Auto-link Document nodes to Resource nodes based on fuzzy title/filename similarity."""
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    res_resources = conn.execute("MATCH (r:Resource) RETURN r.id, r.title")
    resources = []
    while res_resources.has_next():
        row = res_resources.get_next()
        resources.append((str(row[0]), str(row[1])))

    res_docs = conn.execute("MATCH (d:Document) RETURN d.id, d.title")
    docs = []
    while res_docs.has_next():
        row = res_docs.get_next()
        docs.append((str(row[0]), str(row[1] or "")))

    linked = 0
    for r_id, r_title in resources:
        best_doc = None
        best_score = 0
        clean_res = re.sub(r"[^a-zA-Z0-9 ]+", " ", r_title.lower()).strip()

        for d_id, d_title in docs:
            # Check match against title or filename
            clean_fname = re.sub(r"[^a-zA-Z0-9 ]+", " ", d_id.replace(".pdf", "").lower()).strip()
            clean_dtitle = re.sub(r"[^a-zA-Z0-9 ]+", " ", d_title.lower()).strip()
            
            score1 = fuzz.token_set_ratio(clean_res, clean_fname)
            score2 = fuzz.token_set_ratio(clean_res, clean_dtitle) if clean_dtitle else 0
            score = max(score1, score2)

            if score > best_score:
                best_score = score
                best_doc = d_id

        if best_doc and best_score >= 70:
            doc_esc = best_doc.replace("'", "\\'")
            conn.execute(f"""
                MATCH (r:Resource {{id: '{r_id}'}}), (d:Document {{id: '{doc_esc}'}})
                MERGE (r)-[:PROVIDES_TEXT]->(d)
            """)
            linked += 1

    del conn, db
    return {"linked": linked}


def generate_coverage_report(db_path: str) -> str:
    """Report how many Resource nodes have linked Document text."""
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    res_total = conn.execute("MATCH (r:Resource) RETURN COUNT(r)")
    total = res_total.get_next()[0]

    res_linked = conn.execute("MATCH (r:Resource)-[:PROVIDES_TEXT]->(d:Document) RETURN COUNT(DISTINCT r)")
    linked = res_linked.get_next()[0]

    del conn, db
    return f"{linked} of {total} Resources have linked Documents"
