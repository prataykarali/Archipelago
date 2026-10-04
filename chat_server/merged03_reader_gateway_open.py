"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode
from .merged01_repo_root import _has_valid_auth_session, _is_auth_enforced, app  # noqa: F401
from .merged02_index import _requested_page  # noqa: F401
from host_inference.pearson_handoff import handoff
from .merged04_hf_token import HF_DOC_MAP, _build_redirect_shell  # noqa: F401


@app.route("/open")
@app.route("/open/<path:resource_id>")
@app.route("/open/book/<path:resource_id>")
def reader_gateway_open(resource_id: str = ""):
    """Universal Reader Gateway Route:
    - Provider == huggingface or local -> redirects to /read/<id>?page=N (internal PDF.js reader)
    - Provider == pearson -> launches authenticated reader flow in a new browser tab
    - External URLs -> opens external destination in new tab
    """
    if _is_auth_enforced() and not _has_valid_auth_session():
        return redirect(f"/login?next={quote(request.full_path.rstrip('?'), safe='')}")
    doc_arg = request.args.get("doc") or request.args.get("id") or request.args.get("book") or ""
    clean_id = (resource_id or doc_arg).removeprefix("book/").strip()
    page_int = _requested_page(request.args.get("page"))

    # 1. Check Pearson catalog matching
    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve, _load_pearson_catalog, _fuzzy_match_book
        cat = _load_pearson_catalog()
        matched = _fuzzy_match_book(cat, clean_id, clean_id, clean_id)
        if matched or "pearson" in clean_id.lower() or "0fcd531f" in clean_id:
            pearson_url = pearson_resolve(clean_id, page=page_int)
            if not pearson_url and matched:
                b_id = matched.get("id")
                sub_id = matched.get("subscription_id") or "debf3e10-c27c-469a-a2aa-8a30c919db91"
                v = "index.html" if matched.get("book_type") == "reflowable" else "pdfviewer.html"
                page_part = f"/page/{page_int or 1}"
                pearson_url = f"https://ebooks.elibrary.in.pearson.com/wr/{v}?version=1.0.317.1&subscriptionId={sub_id}#book/{b_id}{page_part}"
            title = (matched.get("title") if matched else clean_id) or "Pearson eLibrary Textbook"
            return handoff(title, pearson_url or "https://elibrary.in.pearson.com/", page_int)
    except Exception as exc:
        app.logger.warning("Pearson check error in gateway: %s", exc)

    # 2. Check ResourceRegistry
    try:
        from archipelago.resolver.resource_registry import get_registry
        rec = get_registry().get_by_id(clean_id)
        if rec:
            if rec.source == "pearson":
                from archipelago.resolver.pearson import resolve as pearson_resolve
                p_url = pearson_resolve(rec.resource_id, page=page_int) or rec.reader_url
                return handoff(rec.title, p_url, page_int)
            elif rec.source in ("huggingface", "local"):
                read_url = f"/read/{quote(clean_id, safe='/')}?page={page_int}"
                return redirect(read_url, code=302)
            elif rec.reader_url and (rec.reader_url.startswith("http://") or rec.reader_url.startswith("https://")):
                return _build_redirect_shell(rec.reader_url, title=rec.title)
    except Exception as exc:
        app.logger.warning("Registry check error in gateway: %s", exc)

    # 3. Default: for PDF files or HF documents, route to internal PDF.js reader
    read_url = f"/read/{quote(clean_id, safe='/')}?page={page_int}"
    return redirect(read_url, code=302)


@app.route("/api/reader/info/<path:resource_id>")
def reader_info_api(resource_id):
    """Metadata inspection for the PDF.js reader."""
    clean_id = resource_id.removeprefix("book/").strip()
    page = request.args.get("page", "1")

    # 1. Pearson check
    try:
        from archipelago.resolver.pearson import _load_pearson_catalog, _fuzzy_match_book, resolve as pearson_resolve
        cat = _load_pearson_catalog()
        matched = _fuzzy_match_book(cat, clean_id, clean_id, clean_id)
        if matched:
            p_url = pearson_resolve(clean_id, page=int(page) if page.isdigit() else 1)
            return jsonify({
                "id": clean_id,
                "title": matched.get("title", ""),
                "author": matched.get("author", ""),
                "provider": "pearson",
                "reader_url": f"/open/{quote(clean_id, safe='')}?page={page}",
                "navigation": "manual_page",
                "page_verified": False,
                "page_count": matched.get("page_count", 0),
            })
    except Exception:
        pass

    # 2. Resource Registry
    try:
        from archipelago.resolver.resource_registry import get_registry
        rec = get_registry().get_by_id(clean_id)
        if rec:
            if rec.source == "pearson":
                from archipelago.resolver.pearson import resolve as pearson_resolve
                p_url = pearson_resolve(rec.resource_id, page=int(page) if page.isdigit() else 1) or rec.reader_url
                return jsonify({
                    "id": clean_id,
                    "title": rec.title,
                    "author": rec.author,
                    "provider": "pearson",
                    "reader_url": f"/open/{quote(clean_id, safe='')}?page={page}",
                "navigation": "manual_page",
                "page_verified": False,
                    "page_count": rec.page_count,
                })
            elif rec.source == "huggingface":
                pdf_path = rec.hf_file_path or clean_id
                return jsonify({
                    "id": clean_id,
                    "title": rec.title,
                    "author": rec.author,
                    "provider": "huggingface",
                    "pdf_url": f"/pdfs/{pdf_path}",
                    "page": int(page) if page.isdigit() else 1,
                    "blob_url": rec.blob_url,
                })
            elif rec.source == "local":
                return jsonify({
                    "id": clean_id,
                    "title": rec.title,
                    "author": rec.author,
                    "provider": "local",
                    "pdf_url": rec.reader_url if rec.reader_url.startswith("/pdfs/") else f"/pdfs/{clean_id}",
                    "page": int(page) if page.isdigit() else 1,
                })
    except Exception:
        pass

    # 3. Known HF doc map or generic filename
    mapped_hf = HF_DOC_MAP.get(clean_id.lower())
    target_pdf = mapped_hf or clean_id
    title_guess = clean_id.split("/")[-1].replace(".pdf", "").replace("_", " ").title()

    return jsonify({
        "id": clean_id,
        "title": title_guess,
        "author": "Archipelago Holding",
        "provider": "huggingface" if mapped_hf else "local",
        "pdf_url": f"/pdfs/{target_pdf}",
        "page": int(page) if page.isdigit() else 1,
    })
