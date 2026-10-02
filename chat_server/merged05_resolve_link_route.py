"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
from flask.typing import ResponseReturnValue
import requests as _requests
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode
from .merged01_repo_root import REPO_ROOT, _inference_auth_headers, app  # noqa: F401
from .merged02_index import _requested_page, _with_page_fragment  # noqa: F401
from .merged04_hf_token import _build_redirect_shell  # noqa: F401
from .merged06_chat_proxy import _inference_base  # noqa: F401


@app.route("/resolve", methods=["GET"])
@app.route("/resolve/<path:book_id>", methods=["GET"])
@app.route("/api/resource/<path:book_id>/link", methods=["GET"])
def resolve_link_route(book_id: str | None = None):
    """Resolve a book/paper/Pearson link using the LinkResolver engine."""
    from flask import jsonify, redirect
    from archipelago.resolver import LinkResolver

    target_id = book_id or request.args.get("id") or request.args.get("book_id") or ""
    title = request.args.get("title")
    isbn = request.args.get("isbn")
    doi = request.args.get("doi")
    source = request.args.get("source")
    wants_json = request.args.get("json") == "1" or "application/json" in request.headers.get("Accept", "")

    resolver = LinkResolver()
    client_ip = request.remote_addr or "default"
    result = resolver.resolve(
        resource_id=target_id,
        title=title,
        isbn=isbn,
        doi=doi,
        source=source,
        client_key=client_ip,
    )
    page = _requested_page(request.args.get("page"))
    if result.get("working") and result.get("url"):
        provider = str(result.get("source") or source or "").lower()
        if provider == "pearson":
            from archipelago.resolver.pearson import resolve as pearson_resolve
            result["url"] = pearson_resolve(target_id, page=page) or _with_page_fragment(result["url"], page)
            result["reader_url"] = result["url"]
        elif provider in {"huggingface", "local"} and target_id:
            result["url"] = f"/open/{quote(target_id, safe='/')}?page={page}"
            result["reader_url"] = result["url"]
        result["page"] = page

    if wants_json or request.path.startswith("/api/resource/"):
        return jsonify(result), (200 if result.get("working") else 404)

    if result.get("working") and result.get("url"):
        if result.get("source") == "pearson":
            return _build_redirect_shell(result["url"], title=result.get("title") or "Pearson eLibrary")
        return redirect(result["url"], code=302)

    # Fallback to local PDF proxy or 404
    if target_id and (target_id.endswith(".pdf") or "paper_" in target_id or "book_" in target_id):
        return redirect(f"/read/{quote(target_id, safe='/')}?page={page}", code=302)

    return jsonify(result), 404


@app.route("/api/library/data")
def library_data():
    """Returns library catalog + e-book shelf + full resource inventory (no secrets)."""
    from archipelago.inference.library_catalog_api import build_library_data_payload

    return build_library_data_payload(REPO_ROOT)


@app.route("/api/catalog/all")
def catalog_all():
    """Return all catalog documents for the Stack of Books panel."""
    from archipelago.inference.library_catalog_api import build_library_data_payload

    try:
        data = build_library_data_payload(REPO_ROOT)
    except Exception as exc:
        app.logger.warning("Failed building library data for catalog_all: %s", exc)
        data = {}

    docs = []
    existing_ids = set()

    for b in data.get("ebook_shelf", []):
        b_id = b.get("id")
        if not b_id or b_id in existing_ids:
            continue
        existing_ids.add(b_id)
        docs.append({
            "id": b_id,
            "title": b.get("title") or b_id,
            "authors": b.get("author") or "Academic Corpus",
            "year": b.get("year", 2024),
            "cat": "textbook" if not b.get("isPaper") else "paper",
            "dom": b.get("domain", "General CS"),
            "pdf": b.get("pdfUrl") or b_id,
            "topics": [b.get("domain")] if b.get("domain") else [],
        })

    for pb in data.get("pearson_books", []):
        p_id = pb.get("id")
        if not p_id or p_id in existing_ids:
            continue
        existing_ids.add(p_id)
        docs.append({
            "id": p_id,
            "title": pb.get("title") or p_id,
            "authors": pb.get("author") or "Pearson Education",
            "year": pb.get("year", 2024),
            "cat": "textbook",
            "dom": "dbms" if "database" in (pb.get("title") or "").lower() else "os" if "operating" in (pb.get("title") or "").lower() else "dl",
            "pdf": pb.get("pdf_url") or p_id,
            "topics": [pb.get("domain")] if pb.get("domain") else ["Pearson eLibrary"],
        })

    for p in data.get("research_papers", []):
        p_id = p.get("id") or p.get("filename")
        if not p_id or p_id in existing_ids:
            continue
        existing_ids.add(p_id)
        docs.append({
            "id": p_id,
            "title": p.get("title", p_id),
            "authors": p.get("source", "ArXiv / Academic Research"),
            "year": 2024,
            "cat": "paper",
            "dom": "dl",
            "pdf": f"papers/{p_id}" if not str(p_id).startswith("papers/") else p_id,
            "topics": ["Research Paper"],
        })

    return jsonify({"documents": docs, "total": len(docs)})


@app.route("/api/page-view", methods=["GET", "POST", "OPTIONS"])
def page_view_proxy() -> ResponseReturnValue:
    """Proxy page-view requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/page-view"
    try:
        if request.method == "GET":
            upstream = _requests.get(
                target,
                params=request.args,
                headers=_inference_auth_headers(),
                allow_redirects=False,
                timeout=10,
            )
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                headers=_inference_auth_headers(),
                allow_redirects=False,
                timeout=10,
            )
        if upstream.status_code in (301, 302, 303, 307, 308) and "Location" in upstream.headers:
            return redirect(upstream.headers["Location"], code=upstream.status_code)
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for page-view: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
