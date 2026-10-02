"""Catalog search, e-resource portals, and document inventory routes.

Search never interpolates user input into Cypher, and never invents a
catalog record when nothing matches.
"""

from __future__ import annotations

import logging

from flask import Response, jsonify, request

from archipelago.api.engine_state import (
    CATALOG_SEARCH_LIMIT,
    DEFAULT_AVAILABLE_COPIES,
    DEFAULT_SHELF_LOCATION,
    DOCUMENT_LIST_LIMIT,
    PDF_DIR,
    app,
    get_kuzu_connection,
)

logger = logging.getLogger("archipelago.api")

SUCCESS_STATUS = 200
# The Resource node has no "location" column; shelf identity comes from the
# Koha biblionumber/call number. Columns must match catalog_schema.py exactly.
RESOURCE_SEARCH_CYPHER = (
    "MATCH (r:Resource) "
    "WHERE lower(r.title) CONTAINS lower($q) OR lower(r.author) CONTAINS lower($q) "
    "RETURN r.id, r.title, r.author, r.biblionumber, r.publisher, "
    "r.copyright_year, r.available_copies, r.total_copies "
    f"LIMIT {CATALOG_SEARCH_LIMIT}"
)
DOCUMENT_LIST_CYPHER = f"MATCH (d:Document) RETURN d.id, d.title LIMIT {DOCUMENT_LIST_LIMIT}"

INSTITUTIONAL_PORTALS = [
    {
        "name": "National Digital Library of India (NDLI)",
        "url": "https://ndl.iitkgp.ac.in",
        "access": "Institutional SSO",
    },
    {
        "name": "IEEE Xplore Digital Library",
        "url": "https://ieeexplore.ieee.org",
        "access": "Campus IP / VPN Proxy",
    },
    {
        "name": "Scopus & ScienceDirect (Elsevier)",
        "url": "https://www.sciencedirect.com",
        "access": "Institutional Passkey",
    },
]


def _rows_to_dicts(result) -> list[dict]:
    """Drain a Kùzu result set into a list of dicts."""
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    return rows


def _shelf_label(biblionumber) -> str:
    """Call number for a catalog record, or the default when unassigned."""
    text = str(biblionumber or "").strip()
    if not text or text == "0":
        return DEFAULT_SHELF_LOCATION
    return text


@app.route("/api/catalog/search", methods=["GET"])
def api_catalog_search() -> Response:
    """Search Koha/OPAC physical inventory by title, author, or subject."""
    q = request.args.get("q", "").strip().lower()
    results: list[dict] = []

    if q:
        conn = get_kuzu_connection()
        if conn is not None:
            try:
                # Parameterized query: user input is never spliced into Cypher.
                for row in _rows_to_dicts(conn.execute(RESOURCE_SEARCH_CYPHER, {"q": q})):
                    results.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "author": row[2],
                            "shelf_location": _shelf_label(row[3]),
                            "publisher": row[4],
                            "year": row[5],
                            "available_copies": (
                                row[6] if row[6] is not None else DEFAULT_AVAILABLE_COPIES
                            ),
                            "total_copies": row[7],
                        }
                    )
            except Exception as exc:
                logger.warning("Kuzu resource search unavailable (%s); returning no matches.", exc)

    return jsonify(
        {
            "query": q,
            "results": results,
            "count": len(results),
        }
    ), SUCCESS_STATUS


@app.route("/api/eresources", methods=["GET"])
def api_eresources() -> Response:
    """Return institutional links and access portals for IEEE, NDLI, Scopus."""
    try:
        from archipelago.inference.eresource_credentials import load_credentials

        creds = load_credentials()
    except Exception:
        creds = {}

    return jsonify(
        {
            "institutional_portals": [dict(p) for p in INSTITUTIONAL_PORTALS],
            "overlay": creds,
        }
    ), SUCCESS_STATUS


@app.route("/api/documents", methods=["GET"])
def api_documents() -> Response:
    """Return all indexed documents in the active library."""
    docs: list[dict] = []
    conn = get_kuzu_connection()
    if conn is not None:
        try:
            for row in _rows_to_dicts(conn.execute(DOCUMENT_LIST_CYPHER)):
                docs.append({"doc_id": row[0], "title": row[1] or row[0]})
        except Exception as exc:
            logger.debug("Kuzu document listing unavailable: %s", exc)

    if not docs and PDF_DIR.is_dir():
        for f in sorted(PDF_DIR.glob("*.pdf")):
            docs.append({"doc_id": f.name, "title": f.stem.replace("_", " ")})

    return jsonify({"total_documents": len(docs), "documents": docs}), SUCCESS_STATUS
