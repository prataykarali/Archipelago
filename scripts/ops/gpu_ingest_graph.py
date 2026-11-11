"""Graph node helpers for the local PDF pilot ingest."""

from __future__ import annotations

from gpu_ingest_model import _esc


def _ensure_doc(conn, doc_id: str, title: str) -> None:
    safe = _esc(doc_id)
    r = conn.execute(f"MATCH (d:Document {{id: '{safe}'}}) RETURN d.id")
    if r.has_next():
        return
    conn.execute(
        "CREATE (d:Document {"
        f"id: '{safe}', doc_hash: '', page_count: 0, title: '{_esc(title)}', "
        "edition: '', page_label_map: ''"
        "})"
    )
