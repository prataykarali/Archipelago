"""GET /api/page-view — passage + PDF resolve for citation deep-links."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from flask import jsonify, redirect, request

from archipelago.inference.state import app


def get_db_connection():
    """Return a Kuzu connection, or None if the DB is unavailable."""
    try:
        import kuzu
        from archipelago.inference import state as st

        return kuzu.Connection(st.db)
    except Exception:
        return None


_KNOWN_PREFIXES = (
    "papers/",
    "textbooks/",
    "textbook/",
    "ostep",
    "books/",
    "chapters/",
    "notes/",
    "pdfs/",
)


@app.route("/api/page-view", methods=["GET", "POST"])
def page_view():  # type: ignore[return]
    """Return page-view contract JSON (doc_id, passage, spans, pdf_url)."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        doc_id_raw = (data.get("doc_id") or data.get("doc") or data.get("id") or "").strip()
        page_raw = str(data.get("page", "1"))
        highlight = (data.get("highlight") or "").strip()
    else:
        doc_id_raw = (request.args.get("doc_id") or request.args.get("doc") or request.args.get("id") or "").strip()
        page_raw = request.args.get("page", "1")
        highlight = request.args.get("highlight", "").strip()

    if not doc_id_raw:
        return jsonify({"error": "doc_id is required"}), 400

    try:
        page = int(page_raw)
    except ValueError:
        page = 1
    if page < 1:
        page = 1

    try:
        from archipelago.inference.demo_query_books import (
            demo_passage_for_doc,
            resolve_doc_id,
        )

        doc_id = resolve_doc_id(doc_id_raw) or doc_id_raw
        demo = demo_passage_for_doc(doc_id_raw, page=page, highlight=highlight)
        if demo and demo.get("doc_id"):
            doc_id = str(demo.get("doc_id") or doc_id)
    except Exception:
        doc_id = doc_id_raw
        demo = None

    passage = ""
    title = ""
    authors = ""
    section_title = ""
    found_chunk = False
    conn = get_db_connection()
    if conn is not None:
        for candidate in {doc_id, doc_id_raw}:
            if not candidate:
                continue
            try:
                res = conn.execute(
                    "MATCH (c:Chunk) WHERE c.doc_id = $doc_id AND c.page_number = $page "
                    "RETURN c.text LIMIT 1",
                    {"doc_id": candidate, "page": page},
                )
                if res.has_next():
                    passage = res.get_next()[0] or ""
                    doc_id = candidate
                    found_chunk = bool(passage)
                    break
            except Exception:
                try:
                    res = conn.execute(
                        "MATCH (c:Chunk) WHERE c.doc_id = $doc_id AND c.page_number = $page "
                        "RETURN c.text_passage LIMIT 1",
                        {"doc_id": candidate, "page": page},
                    )
                    if res.has_next():
                        passage = res.get_next()[0] or ""
                        doc_id = candidate
                        found_chunk = bool(passage)
                        break
                except Exception:
                    pass

    # Booth demo summaries when graph has no chunk text
    if demo and (not found_chunk):
        passage = str(demo.get("passage") or demo.get("text") or "")
        title = str(demo.get("title") or "")
        authors = str(demo.get("authors") or "")
        section_title = str(demo.get("section_title") or "")
        if demo.get("page"):
            try:
                page = int(demo["page"]) or page
            except (TypeError, ValueError):
                pass
        if demo.get("doc_id"):
            doc_id = str(demo["doc_id"])
        if passage:
            found_chunk = True  # treat demo summary as a valid hit

    pdf_url, avail = _resolve_pdf_url(doc_id)

    pearson_url = None
    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve
        pearson_url = pearson_resolve(doc_id, page=page)
        if not pearson_url and doc_id_raw:
            pearson_url = pearson_resolve(doc_id_raw, page=page)
        if pearson_url:
            pdf_url = pearson_url
            avail = True
    except Exception:
        pass

    wants_json = (
        bool(highlight)
        or request.is_json
        or request.args.get("format") == "json"
        or (
            "application/json" in request.headers.get("Accept", "")
            and "text/html" not in request.headers.get("Accept", "")
        )
    )

    if pearson_url:
        if request.method == "GET" and not wants_json:
            return redirect(pearson_url, code=302)
        return jsonify({
            "doc_id": doc_id,
            "page": page,
            "start_page": page,
            "end_page": page,
            "highlight": highlight,
            "passage": passage or f"Pearson eLibrary digital textbook: {title or doc_id} (Page {page}). Institutional access via Pearson reader.",
            "text": passage or f"Pearson eLibrary digital textbook: {title or doc_id} (Page {page}).",
            "title": title or doc_id,
            "authors": authors,
            "section_title": section_title,
            "cited_spans": [],
            "pdf_url": pearson_url,
            "pdf_available": True,
            "url": pearson_url,
            "reader_url": pearson_url,
            "is_pearson": True,
        }), 200

    if not found_chunk and not passage:
        # Explicit miss — never invent a first-chunk fallback for random docs.
        # Checked *before* the browser redirect above so a bogus doc_id returns a
        # 404 to API callers instead of a 302 into a reader that will also fail;
        # the redirect is a nicety for humans following a citation link.
        return jsonify({
            "error": f"Cited page {page} not found for document '{doc_id_raw}'.",
            "doc_id": doc_id,
            "page": page,
            "highlight": highlight,
            "passage": "",
            "text": "",
            "pdf_url": pdf_url,
            "pdf_available": bool(avail),
            "url": f"/pdfs/{quote(doc_id, safe='/')}#page={page}" if doc_id else "",
        }), 404

    if request.method == "GET" and not wants_json:
        target = f"/read/{quote(doc_id, safe='')}?page={page}#page={page}"
        return redirect(target, code=302)


    if not passage:
        passage = (
            f"Cited page {page} from {doc_id}."
            + (f" Highlight: {highlight}." if highlight else "")
        )

    cited_spans: list[dict] = []
    if highlight:
        low = passage.lower()
        hl = highlight.lower()
        start = low.find(hl)
        if start >= 0:
            cited_spans.append({
                "start": start,
                "end": start + len(highlight),
                "text": passage[start : start + len(highlight)],
            })
        else:
            cited_spans.append({"start": 0, "end": 0, "text": highlight})

    return jsonify({
        "doc_id": doc_id,
        "page": page,
        "start_page": page,
        "end_page": page,
        "highlight": highlight,
        "passage": passage,
        "text": passage,
        "title": title,
        "authors": authors,
        "section_title": section_title,
        "cited_spans": cited_spans,
        "pdf_url": pdf_url,
        "pdf_available": bool(avail),
        "url": f"/pdfs/{quote(doc_id, safe='/')}#page={page}",
    })


def _is_known_catalog_path(path: str) -> bool:
    """True for known corpus paths (papers/, ostep, textbooks/, etc.)."""
    p = (path or "").strip().lower().replace("\\", "/")
    if not p:
        return False
    try:
        from archipelago.inference.demo_query_books import resolve_doc_id

        resolved = resolve_doc_id(p)
        if resolved:
            p = resolved.lower()
    except Exception:
        pass
    if any(p.startswith(pref) or pref.rstrip("/") in p.split("/")[0] for pref in _KNOWN_PREFIXES):
        return True
    if "ostep" in p or p.startswith("papers/") or "textbook" in p:
        return True
    if "/" not in p and not p.endswith(".pdf"):
        return False
    if p.count("/") == 0 and p.endswith(".pdf"):
        known_stems = (
            "lora", "bert", "attention", "rag", "vaswani", "devlin", "hu2021", "lewis", "edge",
        )
        return any(k in p for k in known_stems)
    return False


def _resolve_pdf_url(doc_id: str) -> tuple[str, bool]:
    """Resolve doc_id to PDF URL and availability flag."""
    from archipelago.inference import state as st

    try:
        from archipelago.inference.demo_query_books import resolve_doc_id

        doc_id = resolve_doc_id(doc_id) or doc_id
    except Exception:
        pass

    if not doc_id:
        return "", False

    pdf_base = getattr(st, "PDF_BASE_URL", "") or ""
    encoded = "/".join(quote(seg, safe="") for seg in doc_id.split("/"))
    if pdf_base:
        url = f"{pdf_base.rstrip('/')}/pdfs/{encoded}"
    else:
        url = f"/pdfs/{encoded}"
    try:
        pdf_dir = Path(getattr(st, "PDF_DIR", Path("pdfs")))
        local = pdf_dir / doc_id
        avail = local.is_file()
    except Exception:
        avail = False
    return url, avail
