"""Hosted Archipelago inference: landing, chat, and library details.

Ingestion, uploads, and librarian job controls are not served here.
"""
from __future__ import annotations

import html
import json
import os
import time
import re
from collections import defaultdict, deque
from pathlib import Path

import requests
from flask import Flask, jsonify, redirect, request, send_from_directory
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent

def _load_env():
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v

_load_env()

from engine import Engine, maybe_polish, _hf_doc_path
from library_index import hf_title, load_hf_paths, paper_url, resolve_hf_path
from remote_cache import load_books, load_library_manifest, pearson_page_url, public_book

UI = ROOT / "ui"
ASSET = ROOT / "ui_assets"
engine = Engine()
app = Flask(__name__)

_HITS: dict[str, deque] = defaultdict(deque)
_PUBLIC_API = {
    "/api/auth/config",
    "/api/auth/session",
    "/api/health",
    "/api/readiness",
    "/api/library/data",
    "/api/chat",
    "/api/chat/diagnostic-mcqs",
    "/api/chat/adaptive-step",
    "/api/chat/telemetry",
    "/api/catalog/all",
    "/api/page-view",
}
_PUBLIC_API_PREFIXES = ("/api/reader/info/",)


def _auth_required() -> bool:
    raw = os.getenv("ARCHIPELAGO_AUTH_REQUIRED", "").strip().lower()
    if raw in {"0", "false", "no"}:
        return False
    if raw in {"1", "true", "yes"}:
        return True
    return os.getenv("ARCHIPELAGO_ENV", "development").lower() in {"production", "prod"}


def _supabase() -> tuple[str, str]:
    return os.getenv("SUPABASE_URL", "").strip().rstrip("/"), os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()


def _principal():
    if not _auth_required():
        return {"role": "student", "username": "guest", "token": ""}, None
    url, key = _supabase()
    if not url or not key:
        return None, "Supabase Auth is not configured."
    header = request.headers.get("Authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not token:
        token = request.cookies.get("archipelago_token", "").strip()
    if not token:
        return None, "A Supabase session is required."
    headers = {"apikey": key, "Authorization": f"Bearer {token}"}
    try:
        user_response = requests.get(f"{url}/auth/v1/user", headers=headers, timeout=10)
        profile_response = requests.get(
            f"{url}/rest/v1/profiles",
            params={"select": "username,role", "id": f"eq.{user_response.json().get('id', '')}"},
            headers=headers,
            timeout=8,
        ) if user_response.status_code == 200 else None
    except requests.RequestException:
        return None, "Supabase identity verification is unavailable."
    if user_response.status_code != 200 or profile_response is None or profile_response.status_code != 200:
        return None, "Your Supabase session could not be verified."
    profiles = profile_response.json()
    if not isinstance(profiles, list) or len(profiles) != 1:
        return None, "Your account does not have an assigned Archipelago role."
    role = str(profiles[0].get("role") or "")
    if role not in {"student", "faculty", "librarian", "administrator"}:
        return None, "Your account role is not permitted in Archipelago."
    return {"role": role, "username": profiles[0].get("username") or "", "token": token}, None



_API_HITS: dict[str, deque] = defaultdict(deque)


def _client_ip() -> str:
    """Extract client IP securely behind reverse proxies and CDNs."""
    for header in ("CF-Connecting-IP", "Fly-Client-IP", "X-Real-IP"):
        val = request.headers.get(header)
        if val and val.strip():
            return val.strip().split(",")[0].strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded and forwarded.strip():
        return forwarded.strip().split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def _rate_limited(bucket_dict: dict[str, deque], max_per_min: int = 20, min_gap_sec: float = 1.0) -> tuple[bool, int]:
    """Sliding-window rate limiter per client IP."""
    ip = _client_ip()
    now = time.time()
    bucket = bucket_dict[ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if bucket and now - bucket[-1] < min_gap_sec:
        return True, 1
    if len(bucket) >= max_per_min:
        return True, max(1, int(60 - (now - bucket[0])))
    bucket.append(now)
    return False, 0


@app.before_request
def _guard():
    if request.method == "OPTIONS":
        return ("", 204)
    path = request.path
    if path.startswith("/api/ingest") or path.startswith("/api/documents") or path.startswith("/api/manual"):
        return jsonify({"error": "forbidden", "detail": "Ingestion stays on the local library workstation."}), 403
    # Library browsing, reader routes, and chat are public. Supabase accounts remain
    # available for identity-aware features, but must not block an exact book/page link.
    protected_reader_path = False
    if protected_reader_path and _auth_required():
        principal, error = _principal()
        if principal is None:
            next_url = request.full_path.rstrip("?")
            return redirect(f"/login?next={quote(next_url, safe='/?=&')}")
        request.archipelago_principal = principal  # type: ignore[attr-defined]
    if path.startswith("/api/") and path not in _PUBLIC_API and not path.startswith(_PUBLIC_API_PREFIXES) and _auth_required():
        principal, error = _principal()
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        request.archipelago_principal = principal  # type: ignore[attr-defined]
    if path.startswith("/api/chat"):
        limited, retry_after = _rate_limited(_HITS, max_per_min=20, min_gap_sec=1.0)
        if limited:
            response = jsonify({"error": "rate_limited", "retry_after": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
    elif path.startswith("/api/") or path.startswith("/open/") or path.startswith("/papers/"):
        limited, retry_after = _rate_limited(_API_HITS, max_per_min=120, min_gap_sec=0.05)
        if limited:
            response = jsonify({"error": "rate_limited", "retry_after": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
    return None


@app.after_request
def _security_and_cors(response):
    origin = request.headers.get("Origin", "")
    allowed_origins = {
        "https://archipelago.antideploy.com",
        "https://archipelago-2.antideploy.com",
        "http://localhost:5152",
        "http://127.0.0.1:5152",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    }
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Requested-With"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"

    # OWASP Core Security Headers (without blocking Tailwind Play CDN or runtime asset builders)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
        "form-action 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; "
        "connect-src 'self' https://spllaastejfwclllfndp.supabase.co; "
        "frame-src 'self' https://ebooks.elibrary.in.pearson.com https://elibrary.in.pearson.com https://huggingface.co; "
        "worker-src 'self' blob: https://cdnjs.cloudflare.com"
    )
    response.headers["X-Archipelago-Mode"] = "inference-only"
    return response


def _page(name: str):
    if name in {"chat", "library"} and _auth_required():
        principal, _error = _principal()
        if principal is None:
            return redirect(f"/login?next=/{name}")
    folder = UI
    filename = {"landing": "landing.html", "chat": "index.html", "library": "library.html", "login": "login.html"}[name]
    return send_from_directory(folder, filename)


@app.get("/")
@app.get("/landing")
def landing():
    return _page("landing")


@app.get("/chat")
@app.get("/chat/")
def chat_page():
    return _page("chat")


@app.get("/library")
@app.get("/library/")
def library_page():
    return _page("library")


@app.get("/login")
def login_page():
    return _page("login")


@app.get("/api/health")
@app.get("/api/readiness")
def health():
    return jsonify({
        "ok": True,
        "mode": "inference-only",
        "concepts": len(engine.graph.nodes),
        "pearson_books": len(engine.books),
        "cache": engine.cache_info.get("source"),
        "ingestion": False,
    })


@app.get("/api/auth/config")
def auth_config():
    url, key = _supabase()
    configured = bool(url and key)
    return jsonify({
        "configured": configured,
        "required": _auth_required(),
        "url": url if configured else None,
        "publishableKey": key if configured else None,
        "chatUrl": None,
        "graphUrl": None,
    })


@app.route("/api/auth/session", methods=["POST", "DELETE", "OPTIONS"])
def auth_session():
    if request.method == "DELETE":
        response = jsonify({"authenticated": False})
        response.delete_cookie("archipelago_token", path="/")
        return response
    principal, error = _principal()
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    response = jsonify({"authenticated": True, "role": principal["role"]})
    response.set_cookie(
        "archipelago_token",
        principal["token"],
        max_age=3600,
        httponly=True,
        secure=os.getenv("ARCHIPELAGO_ENV", "production").lower() in {"production", "prod"},
        samesite="Lax",
        path="/",
    )
    return response


@app.get("/api/auth/me")
def auth_me():
    if not _auth_required():
        return jsonify({"authenticated": False, "role": "student", "open": True})
    principal, error = _principal()
    if principal is None:
        return jsonify({"authenticated": False, "detail": error}), 401
    return jsonify({"authenticated": True, "role": principal["role"], "username": principal["username"]})


@app.get("/api/library/data")
def library_data():
    manifest = load_library_manifest()
    if manifest.get("ebook_shelf"):
        return jsonify(manifest)

    ebooks = [public_book(book) for book in load_books()]
    for path in load_hf_paths():
        ebooks.append({
            "id": path,
            "title": hf_title(path),
            "author": "Library books dataset",
            "year": "",
            "domain": "Paper" if "/papers/" in f"/{path}" or path.lower().endswith(".pdf") and "/" not in path else "Textbook",
            "desc": "Opens the dataset file at the indexed page.",
            "isbn": "",
            "isPearson": False,
            "page_count": 1,
            "primaryColor": "#7c3aed",
            "accentColor": "#ddd6fe",
            "pdfUrl": "",
            "open_url": paper_url(path, 1),
            "reader_base_url": paper_url(path, 1),
        })
    holdings = [
        {"title": "Database System Concepts", "author": "Abraham Silberschatz", "publisher": "McGraw-Hill", "accession": "IEM-LIB-DB-0429", "available_ratio": "3 / 5", "no_of_copies": 5, "available_copies": 3},
        {"title": "Mathematics for Machine Learning", "author": "Deisenroth, Faisal, Ong", "publisher": "Cambridge", "accession": "IEM-LIB-ML-0018", "available_ratio": "2 / 2", "no_of_copies": 2, "available_copies": 2},
        {"title": "Attention Is All You Need", "author": "Vaswani et al.", "publisher": "NeurIPS", "accession": "IEM-LIB-AI-0007", "available_ratio": "1 / 1", "no_of_copies": 1, "available_copies": 1},
    ]
    copies = sum(row["no_of_copies"] for row in holdings)
    available = sum(row["available_copies"] for row in holdings)
    return jsonify({
        "ebook_shelf": ebooks,
        "ebook_stats": f"{len(ebooks)} institutional e-books · passwords are not shown",
        "holdings": holdings,
        "holdings_stats": {"total_records": len(holdings), "total_copies": copies, "available_copies": available},
    })


@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "invalid_payload", "detail": "Request body must be a JSON object"}), 400
    raw_query = str(body.get("query") or "")
    # Sanitize query: strip null bytes and ASCII control characters (preserving spaces, tabs, newlines)
    query = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw_query).strip()
    if len(query) > 500:
        return jsonify({"error": "Query exceeds maximum limit of 500 characters"}), 400
    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400

    def generate():
        try:
            for chunk in engine.stream_chat(query):
                yield chunk
        except Exception as e:
            app.logger.error("Chat stream error: %s", e)
            yield "\n\nAn unexpected error occurred during synthesis. Please retry your question."

    return app.response_class(generate(), mimetype="text/plain; charset=utf-8")


@app.get("/api/chat/diagnostic-mcqs")
def diagnostic_mcqs():
    concept = request.args.get("concept") or ""
    return jsonify(engine.diagnostic_payload(concept))


@app.post("/api/chat/adaptive-step")
def adaptive_step():
    body = request.get_json(silent=True) or {}
    return jsonify(engine.adaptive_step(body))


@app.post("/api/chat/telemetry")
def telemetry():
    return ("", 204)


@app.get("/api/catalog/all")
def catalog_all():
    docs = []
    existing = set()
    for book in load_books():
        b_id = book.get("id")
        if not b_id or b_id in existing:
            continue
        existing.add(b_id)
        title = book.get("title") or ""
        lower = title.lower()
        dom = "dbms" if "database" in lower else "os" if "operating" in lower else "math" if "math" in lower else "dl"
        docs.append({
            "id": b_id,
            "title": title,
            "authors": book.get("author") or "Pearson Education",
            "year": book.get("year", 2024),
            "cat": "textbook",
            "dom": dom,
            "pdf": b_id,
            "topics": [book.get("domain")] if book.get("domain") else ["Pearson eLibrary"],
        })
    for path in load_hf_paths():
        if path in existing:
            continue
        existing.add(path)
        is_paper = "/papers/" in f"/{path}" or path.lower().endswith(".pdf")
        lower = path.lower()
        dom = "peft" if "lora" in lower or "rag" in lower else "os" if "ostep" in lower else "dl"
        docs.append({
            "id": path,
            "title": hf_title(path),
            "authors": "Research Dataset",
            "year": 2024,
            "cat": "paper" if is_paper else "textbook",
            "dom": dom,
            "pdf": path,
            "topics": ["Research Paper"],
        })
    return jsonify({"documents": docs, "total": len(docs)})


@app.route("/api/page-view", methods=["GET", "POST"])
def page_view():
    data = request.get_json(silent=True) or {}
    doc_id = (request.args.get("doc_id") or request.args.get("doc") or request.args.get("id") or data.get("doc_id") or data.get("doc") or data.get("id") or "").strip()
    try:
        page = max(1, int(request.args.get("page") or data.get("page") or 1))
    except (ValueError, TypeError):
        page = 1

    # Check Pearson
    for book in load_books():
        b_id = book.get("id") or ""
        b_slug = book.get("slug") or ""
        b_isbn = book.get("isbn") or ""
        b_title = (book.get("title") or "").lower()
        if doc_id in (b_id, b_slug, b_isbn) or (doc_id and doc_id.lower() in b_title):
            pearson_url = pearson_page_url(book, page)
            wants_json = request.is_json or request.args.get("format") == "json" or "application/json" in request.headers.get("Accept", "")
            if not wants_json:
                return redirect(f"/open/{book.get('id')}?page={page}")
            return jsonify({
                "doc_id": book.get("id"),
                "page": page,
                "title": book.get("title"),
                "pdf_url": pearson_url,
                "url": pearson_url,
                "is_pearson": True,
            })

    # Default PDF / HF
    mapped = _hf_doc_path(doc_id) or doc_id
    clean_doc = mapped.lstrip("/").replace("papers/", "")
    target = f"/read?doc={quote(doc_id, safe='')}&page={page}#page={page}"
    wants_json = request.is_json or request.args.get("format") == "json" or "application/json" in request.headers.get("Accept", "")
    if not wants_json:
        return redirect(target)
    return jsonify({
        "doc_id": doc_id,
        "page": page,
        "title": hf_title(mapped) if mapped else "Document",
        "pdf_url": f"/papers/{clean_doc}",
        "url": target,
        "is_pearson": False,
    })


@app.get("/read")
@app.get("/read/<path:subpath>")
def read_page(subpath: str = ""):
    """Serve full PDF reader interface."""
    return send_from_directory(UI, "reader.html")


@app.get("/api/reader/info/<path:resource_id>")
def reader_info_api(resource_id: str):
    """Metadata inspection endpoint for reader.html."""
    clean_id = resource_id.removeprefix("book/").strip()
    try:
        page = max(1, int(request.args.get("page") or 1))
    except (ValueError, TypeError):
        page = 1

    # 1. Pearson check
    for book in load_books():
        b_id = book.get("id") or ""
        b_slug = book.get("slug") or ""
        b_isbn = book.get("isbn") or ""
        b_title = (book.get("title") or "").lower()
        if clean_id in (b_id, b_slug, b_isbn) or (clean_id and clean_id.lower() in b_title):
            p_url = pearson_page_url(book, page)
            return jsonify({
                "id": book.get("id"),
                "title": book.get("title", ""),
                "author": book.get("author", "Pearson Education"),
                "provider": "pearson",
                "reader_url": p_url,
                "page_count": book.get("page_count", 0),
            })

    # 2. Dataset / Papers check
    target_path = resolve_hf_path(_hf_doc_path(clean_id)) or resolve_hf_path(clean_id)
    if not target_path:
        return jsonify({"error": "not_found", "detail": "This document is not a reader-backed dataset file."}), 404
    clean_target = target_path.lstrip("/")
    pdf_route = f"/papers/{clean_target.removeprefix('papers/').lstrip('/')}"
    title_guess = hf_title(clean_target) if clean_target else clean_id.split("/")[-1].replace(".pdf", "").replace("_", " ").title()

    return jsonify({
        "id": clean_id,
        "title": title_guess,
        "author": "Archipelago Research Holding (HF Dataset)",
        "provider": "huggingface",
        "pdf_url": pdf_route,
        "page": page,
    })


@app.get("/papers/<path:doc_path>")
@app.get("/pdfs/<path:doc_path>")
def hosted_paper(doc_path: str):
    """Stream one dataset PDF. The browser opens #page=N on this response."""
    if not doc_path or ".." in doc_path or "\\" in doc_path or "\x00" in doc_path:
        return jsonify({"error": "bad_path", "detail": "Invalid document path."}), 400
    if not re.match(r"^[a-zA-Z0-9_\-\./]+$", doc_path):
        return jsonify({"error": "bad_path", "detail": "Disallowed characters in document path."}), 400
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        return jsonify({"error": "unavailable", "detail": "The paper dataset token is not configured."}), 503

    clean_path = doc_path.lstrip("/")
    clean_path = re.sub(r"^(papers/)+", "papers/", clean_path)
    clean_path = re.sub(r"^(textbooks/)+", "textbooks/", clean_path)

    # Check if Pearson book
    for book in load_books():
        b_id = book.get("id") or ""
        b_slug = book.get("slug") or ""
        b_isbn = book.get("isbn") or ""
        if clean_path in (b_id, b_slug, b_isbn):
            return redirect(pearson_page_url(book, 1))

    mapped = _hf_doc_path(clean_path)
    candidates = []
    if mapped:
        candidates.append(mapped)
    candidates.append(clean_path)
    if not clean_path.startswith("papers/"):
        candidates.append(f"papers/{clean_path}")
    if not clean_path.startswith("textbooks/"):
        candidates.append(f"textbooks/{clean_path}")
    if not clean_path.startswith("archipelago-books-cs/"):
        candidates.append(f"archipelago-books-cs/{clean_path}")
    base_name = clean_path.split("/")[-1]
    if base_name != clean_path:
        candidates.append(f"papers/{base_name}")
        candidates.append(f"textbooks/{base_name}")

    upstream = None
    for cand in candidates:
        verified = resolve_hf_path(cand)
        if not verified:
            continue
        try:
            resp = requests.get(
                f"https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/{verified}",
                headers={"Authorization": f"Bearer {token}"},
                stream=True,
                timeout=30,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                upstream = resp
                break
            resp.close()
        except requests.RequestException:
            pass

    if upstream is None or upstream.status_code != 200:
        return jsonify({"error": "not_found", "detail": "That page is not in the dataset."}), 404

    def generate():
        try:
            for chunk in upstream.iter_content(65536):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    response = app.response_class(generate(), mimetype="application/pdf")
    filename = doc_path.split("/")[-1] or "paper.pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@app.get("/open/<book_id>")
def open_pearson(book_id: str):
    """Redirect an indexed Pearson title to its exact reader page."""
    clean_id = (book_id or "").strip()
    if not clean_id or len(clean_id) > 128 or not re.match(r"^[a-zA-Z0-9_\-\. ]+$", clean_id):
        return jsonify({"error": "bad_request", "detail": "Invalid book ID format."}), 400

    book = next((item for item in load_books() if item.get("id") == clean_id or item.get("slug") == clean_id or item.get("isbn") == clean_id or (clean_id and clean_id.lower() in (item.get("title") or "").lower())), None)
    if book is None:
        return jsonify({"error": "not_found", "detail": "That title is not in the Pearson catalog."}), 404
    try:
        page = max(1, int(request.args.get("page") or 1))
    except (ValueError, TypeError):
        page = 1
    target = pearson_page_url(book, page)
    # Pearson owns authentication. Keeping the complete deep link intact lets its
    # own login flow return to the requested title and page without exposing secrets.
    return redirect(target, code=302)

    # Legacy handoff markup retained below only for source-history compatibility.
    # It is unreachable and never rendered.
    title = book.get("title") or "Pearson Textbook"
    safe_title = html.escape(str(title))
    safe_url = html.escape(target)
    script_url = json.dumps(target).replace("<", "\\u003c").replace(">", "\\u003e")

    username = os.environ.get("PEARSON_USERNAME", "library.uemk@uem.edu.in")
    password = os.environ.get("PEARSON_PASSWORD", "Central-Library@#1")
    json_user = json.dumps(username)
    json_pass = json.dumps(password)

    if request.args.get("direct") == "1":
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Opening {safe_title}</title></head>
<body style="margin:0;background:#0f172a;color:#e2e8f0;font-family:sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center">
<p>Opening page {page} of {safe_title} in the Pearson reader.</p>
<script>location.replace({script_url});</script>
</body></html>"""

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Opening {safe_title} — Pearson eLibrary</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: radial-gradient(circle at 50% 20%, #1e1b4b 0%, #0f172a 60%, #020617 100%);
      color: #f8fafc;
      padding: 1.5rem;
    }}
    .card {{
      width: 100%; max-width: 520px;
      background: rgba(30, 41, 59, 0.9);
      border: 1px solid rgba(245, 158, 11, 0.4);
      border-radius: 1.25rem;
      padding: 2rem;
      box-shadow: 0 20px 50px rgba(0,0,0,0.6), 0 0 40px rgba(245,158,11,0.1);
      backdrop-filter: blur(16px);
      text-align: center;
    }}
    .badge {{
      display: inline-flex; align-items: center; gap: 6px;
      background: rgba(245, 158, 11, 0.2);
      border: 1px solid rgba(245, 158, 11, 0.5);
      color: #fbbf24;
      padding: 4px 12px; border-radius: 999px;
      font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
      margin-bottom: 1rem;
    }}
    h1 {{
      font-size: 1.35rem; font-weight: 800; line-height: 1.3;
      color: #ffffff; margin-bottom: 0.5rem;
    }}
    .dest-pill {{
      display: inline-block;
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: #38bdf8;
      font-weight: 600; font-size: 0.85rem;
      padding: 4px 14px; border-radius: 8px;
      margin-bottom: 1.5rem;
    }}
    .creds-box {{
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 0.875rem;
      padding: 1.25rem;
      margin-bottom: 1.5rem;
      text-align: left;
    }}
    .creds-title {{
      font-size: 0.75rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;
      margin-bottom: 0.75rem; display: flex; align-items: center; justify-content: space-between;
    }}
    .cred-row {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.5rem 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }}
    .cred-row:last-child {{ border-bottom: none; }}
    .cred-label {{ font-size: 0.8rem; color: #cbd5e1; }}
    .cred-val-wrap {{ display: flex; align-items: center; gap: 8px; }}
    .cred-val {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem; font-weight: 600; color: #fef08a;
      background: rgba(0,0,0,0.4); padding: 3px 8px; border-radius: 6px;
      user-select: all;
    }}
    .btn-copy {{
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #f8fafc; font-size: 0.75rem; font-weight: 600;
      padding: 4px 10px; border-radius: 6px; cursor: pointer;
      transition: all 0.2s;
    }}
    .btn-copy:hover {{ background: rgba(255, 255, 255, 0.2); }}
    .btn-copy.copied {{ background: #16a34a; border-color: #22c55e; color: #fff; }}
    .launch-btn {{
      display: flex; align-items: center; justify-content: center; gap: 8px;
      width: 100%; padding: 0.875rem;
      background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
      color: #000; font-weight: 800; font-size: 0.95rem;
      border: none; border-radius: 0.75rem;
      cursor: pointer; text-decoration: none;
      box-shadow: 0 4px 20px rgba(245, 158, 11, 0.35);
      transition: all 0.2s;
    }}
    .launch-btn:hover {{
      background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
      transform: translateY(-1px); box-shadow: 0 6px 24px rgba(245, 158, 11, 0.5);
    }}
    .auto-notice {{
      margin-top: 1rem; font-size: 0.8rem; color: #94a3b8; line-height: 1.4;
    }}
    .portal-link {{
      display: inline-block; margin-top: 0.75rem; font-size: 0.75rem; color: #38bdf8; text-decoration: none;
    }}
    .portal-link:hover {{ text-decoration: underline; }}
    .toast {{
      position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
      background: #16a34a; color: white; padding: 8px 18px; border-radius: 20px;
      font-size: 0.85rem; font-weight: 600; box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      display: none; z-index: 100;
    }}
  </style>
</head>
<body>
  <div id="toast" class="toast">Credentials copied to clipboard!</div>
  <div class="card">
    <div class="badge">📖 Pearson eLibrary Digital Textbook</div>
    <h1>{safe_title}</h1>
    <div class="dest-pill">📍 Target Destination: Page {page}</div>

    <div class="creds-box">
      <div class="creds-title">
        <span>Institutional Access Credentials</span>
        <button class="btn-copy" id="copy-both-btn" onclick="copyBoth()">Copy Both</button>
      </div>
      <div class="cred-row">
        <span class="cred-label">Username</span>
        <div class="cred-val-wrap">
          <span class="cred-val" id="val-user">{username}</span>
          <button class="btn-copy" onclick="copyVal('val-user', this)">Copy</button>
        </div>
      </div>
      <div class="cred-row">
        <span class="cred-label">Password</span>
        <div class="cred-val-wrap">
          <span class="cred-val" id="val-pass">{password}</span>
          <button class="btn-copy" onclick="copyVal('val-pass', this)">Copy</button>
        </div>
      </div>
    </div>

    <a id="launch-link" class="launch-btn" href="{safe_url}" target="_blank" rel="noopener noreferrer" onclick="onLaunchClick(event)">
      Launch Pearson Reader (Page {page}) ↗
    </a>

    <p class="auto-notice">
      If Pearson displays a login prompt, paste the credentials above.<br>
      Pearson will immediately redirect to <strong>Page {page}</strong> upon signing in.
    </p>

    <a href="https://elibrary.in.pearson.com/" target="_blank" rel="noopener noreferrer" class="portal-link">
      Need to sign into Pearson portal first? Click here ↗
    </a>
  </div>

  <script>
    const user = {json_user};
    const pass = {json_pass};
    const targetUrl = {script_url};

    function showToast(msg) {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.style.display = 'block';
      setTimeout(() => {{ t.style.display = 'none'; }}, 3000);
    }}

    function copyVal(id, btn) {{
      const text = document.getElementById(id).textContent.trim();
      navigator.clipboard.writeText(text).then(() => {{
        showToast('Copied to clipboard!');
        if (btn) {{
          const old = btn.textContent;
          btn.textContent = '✓ Copied';
          btn.classList.add('copied');
          setTimeout(() => {{ btn.textContent = old; btn.classList.remove('copied'); }}, 2000);
        }}
      }});
    }}

    function copyBoth() {{
      navigator.clipboard.writeText(user + '\\t' + pass).then(() => {{
        showToast('Copied username & password!');
        const btn = document.getElementById('copy-both-btn');
        if (btn) {{
          btn.textContent = '✓ Copied Both';
          btn.classList.add('copied');
          setTimeout(() => {{ btn.textContent = 'Copy Both'; btn.classList.remove('copied'); }}, 2000);
        }}
      }});
    }}

    function onLaunchClick(e) {{
      try {{
        navigator.clipboard.writeText(user + '\\t' + pass);
      }} catch (_) {{}}
    }}

    // Attempt automatic clipboard copy of credentials on load
    try {{
      navigator.clipboard.writeText(user + '\\t' + pass).then(() => {{
        showToast('Institutional credentials copied to clipboard!');
      }}).catch(() => {{}});
    }} catch (_) {{}}
  </script>
</body>
</html>"""
    return page_html


@app.get("/ui/assets/<path:filename>")
def ui_assets(filename):
    return send_from_directory(ASSET, filename)


@app.get("/<path:filename>")
def static_files(filename):
    if filename.startswith(".") or filename.startswith("api/") or ".." in filename:
        return jsonify({"error": "not_found"}), 404
    candidate = UI / filename
    if candidate.is_file():
        return send_from_directory(UI, filename)
    return jsonify({"error": "not_found"}), 404


@app.errorhandler(400)
def handle_bad_request(e):
    return jsonify({"error": "bad_request", "detail": "The request was invalid or malformed."}), 400


@app.errorhandler(403)
def handle_forbidden(e):
    return jsonify({"error": "forbidden", "detail": "Access to this resource is prohibited."}), 403


@app.errorhandler(404)
def handle_not_found(e):
    return jsonify({"error": "not_found", "detail": "The requested resource could not be found."}), 404


@app.errorhandler(429)
def handle_rate_limit(e):
    return jsonify({"error": "rate_limited", "detail": "Too many requests. Please slow down."}), 429


@app.errorhandler(500)
def handle_internal_error(e):
    app.logger.error("Internal Server Error: %s", e)
    return jsonify({"error": "internal_error", "detail": "An internal server error occurred."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
