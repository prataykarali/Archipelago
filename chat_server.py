"""
Archipelago Chat UI Server
Serves the premium, standalone chat workspace UI on port 5052.
"""

from collections.abc import Iterator

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
from flask.typing import ResponseReturnValue
import json
import mimetypes
import os
import re
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
if REPO_ROOT.name == "frontend":
    REPO_ROOT = REPO_ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

import requests as _requests

mimetypes.add_type("video/mp4", ".mp4")

_STREAM_CHUNK_BYTES = 64 * 1024  # 64 KiB chunks for streaming proxy responses
_DEFAULT_INFERENCE_CHAT_URL = "http://127.0.0.1:5151/api/chat"
_raw_inf_url = os.environ.get("ARCHIPELAGO_INFERENCE_URL", _DEFAULT_INFERENCE_CHAT_URL).rstrip("/")
INFERENCE_CHAT_URL = _raw_inf_url if _raw_inf_url.endswith("/api/chat") else f"{_raw_inf_url}/api/chat"

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "chat_ui"
# buttons/ (icons) + ui/assets/ (videos) both map to /ui/assets/*
_ASSET_ROOTS = tuple(
    p for p in (BASE_DIR / "buttons", BASE_DIR / "ui" / "assets") if p.is_dir()
)
# Canonical librarian avatar videos — ASSETS_DIR is the asset root holding them.
_VIDEO_ASSET_NAMES = ("library_hi.mp4", "library_think.mp4", "archi_main.mp4")
ASSETS_DIR = next(
    (
        root
        for root in _ASSET_ROOTS
        if all((root / name).exists() for name in _VIDEO_ASSET_NAMES)
    ),
    _ASSET_ROOTS[-1] if _ASSET_ROOTS else (BASE_DIR / "ui" / "assets"),
)

app = Flask(__name__, static_folder=str(STATIC_DIR))

# CORS configuration
@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response

@app.route("/data/catalogs/<path:filename>")
def serve_catalogs(filename):
    """Serve catalog metadata only to a verified institutional session."""
    if not _has_valid_auth_session():
        return jsonify({"error": "unauthorized"}), 401
    catalog_dir = BASE_DIR / "data" / "catalogs"
    return send_from_directory(str(catalog_dir), filename)

from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode

_AUTH_PUBLIC_PATHS = frozenset({
    "/api/auth/config",
    "/api/readiness",
    "/api/health",
})
_AUTH_SESSION_PATHS = frozenset({"/api/auth/session"})
_STAFF_API_PREFIXES = ("/api/users", "/api/librarian", "/api/ingest", "/api/documents", "/api/manual/")


def _cookie_options() -> dict[str, object]:
    domain = os.environ.get("ARCHIPELAGO_COOKIE_DOMAIN", "").strip() or None
    production = os.environ.get("ARCHIPELAGO_ENV", "development").strip().lower() in {"production", "prod"}
    secure_setting = os.environ.get("ARCHIPELAGO_COOKIE_SECURE")
    secure = production if secure_setting is None else secure_setting.strip().lower() in {"1", "true", "yes"}
    return {"domain": domain, "secure": secure, "httponly": True, "samesite": "Lax", "path": "/"}


@app.before_request
def require_verified_api_session():
    """Apply one verified-session policy to every private API endpoint."""
    if not request.path.startswith("/api/") or request.method == "OPTIONS":
        return None
    if (
        request.path in _AUTH_PUBLIC_PATHS
        or request.path in _AUTH_SESSION_PATHS
    ):
        return None
    from archipelago import supabase_auth
    if not supabase_auth.is_auth_required():
        return None
    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    g.archipelago_principal = principal
    if request.path.startswith(_STAFF_API_PREFIXES) and principal.role not in {"librarian", "administrator"}:
        return jsonify({"error": "forbidden", "detail": "Librarian or administrator role required"}), 403
    return None


def _inference_auth_headers() -> dict[str, str]:
    principal = getattr(g, "archipelago_principal", None)
    if principal is None:
        return {}
    return {"Authorization": f"Bearer {principal.access_token}"}

def _is_auth_enforced() -> bool:
    from archipelago import supabase_auth
    return supabase_auth.is_auth_required()

def _has_valid_auth_session() -> bool:
    """Verify the Supabase identity before serving protected browser pages."""
    if not _is_auth_enforced():
        return True
    from archipelago import supabase_auth

    principal, _error = supabase_auth.authenticate_request(request)
    return principal is not None


def _session_cookie_response(payload: dict | None = None, status: int = 200):
    response = jsonify(payload or {"authenticated": True})
    response.status_code = status
    return response


@app.route("/api/auth/session", methods=["POST", "DELETE", "OPTIONS"])
def auth_session_cookie():
    """Exchange a verified Supabase bearer token for a secure HttpOnly cookie."""
    if request.method == "OPTIONS":
        return ("", 204)
    response = _session_cookie_response({"authenticated": False})
    cookie_args = _cookie_options()
    if request.method == "DELETE":
        response.delete_cookie("archipelago_token", **cookie_args)
        return response

    from archipelago import supabase_auth
    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    response = _session_cookie_response({"authenticated": True, "role": principal.role})
    response.set_cookie(
        "archipelago_token",
        principal.access_token,
        max_age=3600,
        **cookie_args,
    )
    return response

@app.route("/")
def index():
    """Serves the landing page (Built for the curious) — publicly accessible."""
    return send_from_directory(str(STATIC_DIR), "landing.html")


@app.route("/landing")
def landing():
    """Serves the cinematic landing page — publicly accessible."""
    return send_from_directory(str(STATIC_DIR), "landing.html")


@app.route("/chat")
@app.route("/chat/")
def chat_ui():
    """Serves the main Chat interface index.html on the same port."""
    if not _has_valid_auth_session():
        return redirect("/login?next=/chat")
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/library_showcase_3d.js")
def library_showcase_3d():
    """Serve 3D showcase engine."""
    return send_from_directory(str(STATIC_DIR), "library_showcase_3d.js")


@app.route("/library")
@app.route("/library/")
def library_details():
    """Serves library details (current institutional data snapshot)."""
    if not _has_valid_auth_session():
        return redirect("/login?next=/library")
    return send_from_directory(str(STATIC_DIR), "library.html")


@app.route("/reader.html")
def reader_static_page():
    """Serves the dedicated PDF.js reader page."""
    if _is_auth_enforced() and not _has_valid_auth_session():
        return redirect(f"/login?next={quote(request.full_path.rstrip('?'), safe='')}")
    return send_from_directory(str(STATIC_DIR), "reader.html")


def _requested_page(value: str | None) -> int:
    try:
        return max(1, min(int(value or 1), 100000))
    except (TypeError, ValueError):
        return 1


def _with_page_fragment(target_url: str, page: int) -> str:
    """Preserve a requested page in provider-specific reader URLs."""
    parsed = urlsplit(target_url)
    if "pearson" in parsed.netloc.lower():
        fragment = re.sub(r"/page/\d+", "", parsed.fragment)
        fragment = f"{fragment}/page/{page}" if fragment else f"page/{page}"
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, fragment))
    if parsed.path.startswith(("/read/", "/open/")):
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    return target_url


@app.route("/read")
@app.route("/read/<path:resource_id>")
@app.route("/read/book/<path:resource_id>")
def reader_view(resource_id: str = ""):
    """Dedicated internal PDF reader view (PDF.js).
    Supports ?doc=PATH&page=N for direct page jumping.
    If resource is Pearson, redirects to /open/<id>?page=N to launch external flow.
    """
    if _is_auth_enforced() and not _has_valid_auth_session():
        return redirect(f"/login?next={quote(request.full_path.rstrip('?'), safe='')}")
    doc_arg = request.args.get("doc") or request.args.get("id") or request.args.get("src") or request.args.get("book") or ""
    clean_id = (resource_id or doc_arg).removeprefix("book/").strip()
    page = _requested_page(request.args.get("page"))

    # Check if Pearson book
    if clean_id:
        try:
            from archipelago.resolver.pearson import _load_pearson_catalog, _fuzzy_match_book
            cat = _load_pearson_catalog()
            if _fuzzy_match_book(cat, clean_id, clean_id, clean_id) or "pearson" in clean_id.lower() or "0fcd531f" in clean_id:
                return redirect(f"/open/{quote(clean_id, safe='/')}?page={page}", code=302)
        except Exception:
            pass

    return send_from_directory(str(STATIC_DIR), "reader.html")


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
            return _build_redirect_shell(pearson_url or "https://elibrary.in.pearson.com/", title=f"{title} (Pearson eLibrary)")
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
                return _build_redirect_shell(p_url, title=f"{rec.title} (Pearson eLibrary)")
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
                "reader_url": p_url,
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
                    "reader_url": p_url,
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


@app.route("/performance")
@app.route("/performance/")
def performance_dashboard():
    """Serves the Performance Metrics ops dashboard."""
    return send_from_directory(str(STATIC_DIR), "performance.html")


@app.route("/safety")
@app.route("/safety/")
def safety_dashboard():
    """Serves the Safety Layer / Routing Gate dashboard."""
    return send_from_directory(str(STATIC_DIR), "safety.html")

@app.route("/login")
@app.route("/login/")
def login_page():
    """Serves the authentication login page."""
    return send_from_directory(str(STATIC_DIR), "login.html")


@app.route("/ui/assets/<path:filename>")
def media_assets(filename):
    """Serve button icons (buttons/) and videos (ui/assets/) under /ui/assets/."""
    safe = Path(filename)
    if ".." in safe.parts:
        return ("Not found", 404)
    for root in _ASSET_ROOTS:
        candidate = root / filename
        if candidate.is_file() or candidate.is_symlink():
            return send_from_directory(str(root), filename, conditional=True)
    fallback = _ASSET_ROOTS[0] if _ASSET_ROOTS else ASSETS_DIR
    return send_from_directory(str(fallback), filename, conditional=True)


HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_REPO = "Prataykarali/Library_books"

HF_DOC_MAP = {
    "book_deep_learning_goodfellow_2016.pdf": "papers/Goodfellow2014_GAN.pdf",
    "book_deep_learning_goodfellow_2016": "papers/Goodfellow2014_GAN.pdf",
    "deep_learning_goodfellow": "papers/Goodfellow2014_GAN.pdf",
    "goodfellow2014_gan.pdf": "papers/Goodfellow2014_GAN.pdf",
    "vaswani2017_attention_is_all_you_need.pdf": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "paper_attention_is_all_you_need_2017": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "paper_attention_is_all_you_need_2017.pdf": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "book_math_for_machine_learning_2020": "textbooks/Deisenroth_Math_For_ML.pdf",
    "book_math_for_machine_learning_2020.pdf": "textbooks/Deisenroth_Math_For_ML.pdf",
    "deisenroth_math_for_ml.pdf": "textbooks/Deisenroth_Math_For_ML.pdf",
    "08_paging.pdf": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
    "ostep_three_easy_pieces": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
    "corpus_book_artificial_intelligence_a_new_synthesis_1998": "https://archive.org/details/artificialintell0000nils",
    "book_speech_and_language_processing_jurafsky": "https://web.stanford.edu/~jurafsky/slp3/",
    "hu2021_lora.pdf": "papers/Hu2021_LoRA.pdf",
    "dettmers2023_qlora.pdf": "papers/Dettmers2023_QLoRA.pdf",
    "lewis2020_rag.pdf": "papers/Lewis2020_RAG.pdf",
    "devlin2018_bert.pdf": "papers/Devlin2018_BERT.pdf",
    "edge2024_graphrag.pdf": "papers/Edge2024_GraphRAG.pdf",
    "bahdanau2014_attention.pdf": "papers/Bahdanau2014_Attention.pdf",
    "kwon2023_vllm.pdf": "papers/Kwon2023_vLLM.pdf",
    "brown2020_gpt3.pdf": "papers/Brown2020_GPT3.pdf",
}

@app.route("/pdfs/<path:filename>")
@app.route("/papers/<path:filename>")
def proxy_pdf(filename):
    """Stream corpus PDFs directly from disk, HuggingFace private dataset, or external fallback."""
    import re
    from flask import redirect

    pdf_dir = BASE_DIR / "pdfs"
    target_name = Path(filename).name
    lower_target = target_name.lower()
    lower_filename = filename.lower()

    for cand in [
        pdf_dir / filename,
        pdf_dir / f"{filename}.pdf",
        BASE_DIR / filename,
        BASE_DIR / "papers" / target_name,
        BASE_DIR / "textbooks" / target_name,
    ]:
        if cand.is_file():
            return send_from_directory(str(cand.parent), cand.name, conditional=True, mimetype="application/pdf")

    for match in pdf_dir.glob(f"**/{target_name}"):
        if match.is_file():
            return send_from_directory(str(match.parent), match.name, conditional=True, mimetype="application/pdf")
    for match in pdf_dir.glob(f"**/{target_name}.pdf"):
        if match.is_file():
            return send_from_directory(str(match.parent), match.name, conditional=True, mimetype="application/pdf")

    hf_rel_path = HF_DOC_MAP.get(lower_filename) or HF_DOC_MAP.get(lower_target)
    if hf_rel_path:
        if hf_rel_path.startswith("http://") or hf_rel_path.startswith("https://"):
            return redirect(hf_rel_path, code=302)
        local_rel = pdf_dir / hf_rel_path
        if local_rel.is_file():
            return send_from_directory(str(local_rel.parent), local_rel.name, conditional=True, mimetype="application/pdf")

    # Check Pearson eLibrary Catalog resolution
    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve
        pearson_url = pearson_resolve(filename)
        if not pearson_url and target_name != filename:
            pearson_url = pearson_resolve(target_name)
        if pearson_url:
            return redirect(pearson_url, code=302)
    except Exception:
        pass

    hf_candidates = []
    if hf_rel_path:
        hf_candidates.append(hf_rel_path)
    if "/" in filename:
        hf_candidates.append(filename)
    hf_candidates.extend([
        f"papers/{target_name}",
        f"textbooks/{target_name}",
        f"books/papers/{target_name}",
        f"books/textbooks/{target_name}",
        target_name,
    ])

    # Try huggingface_hub local caching first for range requests & instant page rendering
    hf_token_val = HF_TOKEN or os.environ.get("HF_TOKEN", "").strip()
    hf_headers = {"Authorization": f"Bearer {hf_token_val}"} if hf_token_val else {}
    for rel_path in hf_candidates:
        if rel_path.startswith("http://") or rel_path.startswith("https://"):
            continue
        try:
            from huggingface_hub import hf_hub_download
            cached_path = hf_hub_download(
                repo_id=HF_REPO,
                filename=rel_path,
                repo_type="dataset",
                token=hf_token_val,
            )
            if cached_path and os.path.isfile(cached_path):
                cp = Path(cached_path)
                return send_from_directory(str(cp.parent), cp.name, conditional=True, mimetype="application/pdf")
        except Exception:
            pass

    for rel_path in hf_candidates:
        hf_url = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{rel_path}"
        try:
            resp = _requests.get(hf_url, headers=hf_headers, stream=True, timeout=12)
            if resp.status_code == 200:
                def generate_hf():
                    try:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                yield chunk
                    except Exception:
                        pass
                    finally:
                        resp.close()
                return Response(
                    generate_hf(),
                    status=200,
                    content_type="application/pdf",
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Content-Disposition": f'inline; filename="{target_name}"',
                    },
                )
        except Exception:
            pass

    arxiv_match = re.search(r"(\d{4}\.\d{4,5})", target_name)
    if arxiv_match:
        return redirect(f"https://arxiv.org/pdf/{arxiv_match.group(1)}", code=302)

    return Response('{"error":"PDF not found"}', status=404, mimetype="application/json")


def _build_redirect_shell(target_url: str, title: str = "Resource") -> str:
    """Build an HTML redirect page that escapes HF Space iframe nesting.

    When the app is embedded inside a Hugging Face Space iframe, a bare HTTP
    302 redirect navigates the *inner* frame — the user never leaves the Space.
    This causes Pearson viewer pages and HF blob pages to either get blocked by
    X-Frame-Options or render as a black screen.

    The HTML shell detects iframe nesting via ``window.top !== window.self`` and
    uses ``window.open(..., '_blank')`` to pop open a real browser tab. When
    running natively (not in an iframe), it falls back to standard navigation.
    """
    import html as _html
    safe_url = _html.escape(target_url, quote=True)
    safe_title = _html.escape(title, quote=True)
    script_url = json.dumps(target_url).replace("</", "<\\/")
    # Shared institutional credentials are NEVER rendered into gateway HTML by
    # default: any unauthenticated fetch of this page would read them. Ops can
    # opt in explicitly for a kiosk/lecture demo via this flag.
    pearson_hint = ""
    if "pearson" in target_url.lower() and os.environ.get("ARCHIPELAGO_EXPOSE_READER_CREDENTIALS", "0").strip().lower() in {"1", "true", "yes"}:
        p_user = os.environ.get("PEARSON_USERNAME", "library.uemk@uem.edu.in")
        p_pass = os.environ.get("PEARSON_PASSWORD", "Central-Library@#1")
        pearson_hint = f"""
    <div style="margin-top: 1.25rem; padding: 1rem; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 0.75rem; font-size: 0.85rem; color: #fde68a; line-height: 1.5; text-align: left;">
      <div style="font-weight: 700; margin-bottom: 0.5rem; color: #fbbf24;">🔑 Institutional Access Credentials:</div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
        <span>User: <strong id="cas-user">{p_user}</strong></span>
        <button type="button" onclick="navigator.clipboard.writeText('{p_user}');this.textContent='Copied!'" style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; cursor: pointer;">Copy</button>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>Pass: <strong id="cas-pass">{p_pass}</strong></span>
        <button type="button" onclick="navigator.clipboard.writeText('{p_pass}');this.textContent='Copied!'" style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; cursor: pointer;">Copy</button>
      </div>
      <div style="margin-top: 0.5rem; font-size: 0.75rem; opacity: 0.8;">If Pearson prompts for login, paste these credentials to immediately jump to your requested page.</div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Opening {safe_title} — Archipelago</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; margin: 0;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      color: #e2e8f0;
    }}
    .card {{
      text-align: center; padding: 2rem 3rem;
      background: rgba(30, 41, 59, 0.9); border-radius: 1rem;
      box-shadow: 0 4px 24px rgba(0,0,0,0.3);
      max-width: 480px;
    }}
    .card h2 {{ margin: 0 0 0.5rem; font-size: 1.25rem; color: #93c5fd; }}
    .card p {{ margin: 0 0 1.5rem; font-size: 0.9rem; opacity: 0.8; }}
    .card a.open-btn {{
      display: inline-block; padding: 0.75rem 2rem;
      background: #2563eb; color: #fff; text-decoration: none;
      border-radius: 0.5rem; font-weight: 600; transition: background 0.2s;
    }}
    .card a.open-btn:hover {{ background: #1d4ed8; }}
    .spinner {{
      width: 24px; height: 24px; border: 3px solid rgba(147,197,253,0.3);
      border-top-color: #93c5fd; border-radius: 50%;
      animation: spin 0.8s linear infinite; margin: 0 auto 1rem;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>
  <div class="card">
    <div class="spinner"></div>
    <h2>Opening: {safe_title}</h2>
    <p>Redirecting to resource…</p>
    <a id="fallback-link" class="open-btn" href="{safe_url}" target="_blank"
       rel="noopener noreferrer">Open Manually</a>
    {pearson_hint}
  </div>
  <script>
    (function() {{
      var url = {script_url};
      try {{
        // Detect if running inside an iframe (e.g. Hugging Face Space)
        if (window.top !== window.self) {{
          // Inside iframe — must pop open a new tab to escape
          window.open(url, "_blank", "noopener,noreferrer");
        }} else {{
          // Running natively — standard navigation
          window.location.href = url;
        }}
      }} catch (e) {{
        // Cross-origin frame access blocked — we're definitely in an iframe
        window.open(url, "_blank", "noopener,noreferrer");
      }}
    }})();
  </script>
</body>
</html>"""


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


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat_proxy() -> ResponseReturnValue:
    """Proxy chat prompts to the upstream inference server, streaming the reply."""
    if request.method == "OPTIONS":
        return ("", 204)

    payload = request.get_json(silent=True) or {}
    try:
        upstream = _requests.post(
            INFERENCE_CHAT_URL,
            json=payload,
            headers=_inference_auth_headers(),
            stream=True,
            timeout=(5, 300),
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502

    def stream_upstream() -> Iterator[bytes]:
        for chunk in upstream.iter_content(chunk_size=_STREAM_CHUNK_BYTES):
            yield chunk

    return Response(
        stream_upstream(),
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/octet-stream"),
    )


@app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST", "OPTIONS"])
def chat_diagnostic_mcqs_proxy() -> ResponseReturnValue:
    """Proxy diagnostic MCQs requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/diagnostic-mcqs"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, headers=_inference_auth_headers(), timeout=5)
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                headers=_inference_auth_headers(),
                timeout=5,
            )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for diagnostic-mcqs: %s", exc)
        return {
            "success": False,
            "available": False,
            "badge": "Personalized assessment temporarily unavailable.",
            "error": str(exc),
        }, 200
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/api/chat/telemetry", methods=["POST", "OPTIONS"])
def chat_telemetry_proxy() -> ResponseReturnValue:
    """Proxy telemetry tracking events to upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/telemetry"
    try:
        upstream = _requests.post(
            target,
            json=request.get_json(silent=True) or {},
            headers=_inference_auth_headers(),
            timeout=5,
        )
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return {"logged": False, "error": str(exc)}, 200


@app.route("/api/chat/verify-mcq", methods=["POST", "OPTIONS"])
def chat_verify_mcq_proxy() -> ResponseReturnValue:
    """Proxy diagnostic MCQ verification requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/verify-mcq"
    try:
        upstream = _requests.post(
            target,
            json=request.get_json(silent=True) or {},
            headers=_inference_auth_headers(),
            timeout=30,
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for verify-mcq: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/api/chat/adaptive-step", methods=["POST", "OPTIONS"])
def chat_adaptive_step_proxy() -> ResponseReturnValue:
    """Proxy diagnostic adaptive-step requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/adaptive-step"
    try:
        upstream = _requests.post(
            target,
                json=request.get_json(silent=True) or {},
                headers=_inference_auth_headers(),
                timeout=30,
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for adaptive-step: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )



def _inference_base() -> str:
    """Derive inference origin from ARCHIPELAGO_INFERENCE_URL (…/api/chat)."""
    url = INFERENCE_CHAT_URL.rstrip("/")
    if url.endswith("/api/chat"):
        return url[: -len("/api/chat")]
    if url.endswith("/api/chat/"):
        return url[: -len("/api/chat/")]
    return url


@app.route("/api/dashboards/<path:subpath>", methods=["GET", "POST", "OPTIONS"])
def dashboards_proxy(subpath: str) -> ResponseReturnValue:
    """Proxy performance/safety dashboard APIs to the inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/dashboards/{subpath}"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, headers=_inference_auth_headers(), timeout=15)
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                headers=_inference_auth_headers(),
                timeout=30,
            )
    except Exception as exc:
        app.logger.warning("Dashboard upstream unreachable: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/api/readiness", methods=["GET", "OPTIONS"])
@app.route("/api/health", methods=["GET", "OPTIONS"])
def readiness_proxy() -> ResponseReturnValue:
    """Proxy readiness/health check to inference engine."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/readiness"
    try:
        upstream = _requests.get(target, timeout=5)
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return jsonify({"ready": False, "error": str(exc)}), 503


@app.route("/api/roadmap", methods=["GET", "POST", "OPTIONS"])
def roadmap_proxy() -> ResponseReturnValue:
    """Proxy learning roadmap to inference engine."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/roadmap"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, headers=_inference_auth_headers(), timeout=10)
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                headers=_inference_auth_headers(),
                timeout=30,
            )
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

@app.route("/api/auth/config", methods=["GET"])
@app.route("/api/auth/me", methods=["GET"])
def auth_proxy_or_local():
    """Return browser-safe auth configuration or the verified current principal."""
    from archipelago import supabase_auth
    if request.path == "/api/auth/config":
        return jsonify(supabase_auth.public_config())

    if not supabase_auth.is_auth_required():
        return jsonify({"authenticated": False, "auth_required": False})

    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    return jsonify({
        "authenticated": True,
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role,
    })


@app.route("/api/users", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/users/<user_id>", methods=["PUT", "DELETE", "OPTIONS"])
def manage_users_api(user_id=None):
    """User management endpoints for librarian and administrator."""
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-User-Role,X-User-Name,X-User-Id"
        return resp

    from archipelago import supabase_auth
    principal, auth_err = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": auth_err or "Authentication required"}), 401

    if request.method == "GET":
        users, err = supabase_auth.list_managed_users(principal)
        if err:
            return jsonify({"error": "forbidden", "detail": err}), 403
        return jsonify({"users": users, "requester": {"role": principal.role, "user_id": principal.user_id}})

    elif request.method == "POST":
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.create_managed_user(principal, data)
        if err:
            return jsonify({"error": "bad_request", "detail": err}), 400
        return jsonify({"success": True, "user": user}), 201

    elif request.method == "PUT":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.update_managed_user(principal, user_id, data)
        if err:
            return jsonify({"error": "update_failed", "detail": err}), 400
        return jsonify({"success": True, "user": user})

    elif request.method == "DELETE":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        ok, err = supabase_auth.delete_managed_user(principal, user_id)
        if err:
            return jsonify({"error": "delete_failed", "detail": err}), 400
        return jsonify({"success": True})

    return jsonify({"error": "method_not_allowed"}), 405


# ── Librarian Ingestion & Staging Workflow Endpoints ─────────────────────────

@app.route("/api/librarian/upload", methods=["POST", "OPTIONS"])
def librarian_upload():
    """Compatibility alias for the canonical staged ingestion pipeline."""
    if request.method == "OPTIONS":
        return ("", 204)
    return proxy_ingest_upload()


@app.route("/api/librarian/jobs/<job_id>", methods=["GET", "OPTIONS"])
def librarian_job_status(job_id: str):
    """Compatibility alias for canonical ingestion status."""
    if request.method == "OPTIONS":
        return ("", 204)
    return proxy_ingest_status(job_id)


@app.route("/api/librarian/staging/review", methods=["GET", "OPTIONS"])
def librarian_staging_review():
    """Retired review endpoint; canonical jobs publish only after full success."""
    if request.method == "OPTIONS":
        return ("", 204)
    return jsonify({"error": "staging review is retired", "use": "/api/ingest/<job_id>"}), 410


@app.route("/api/librarian/staging/publish", methods=["POST", "OPTIONS"])
def librarian_staging_publish():
    """Retired staging publish endpoint; uploads use the canonical worker."""
    if request.method == "OPTIONS":
        return ("", 204)
    return jsonify({"error": "manual staging publish is retired", "use": "/api/ingest"}), 410


@app.route("/api/graph/subgraph", methods=["GET", "OPTIONS"])
def graph_subgraph():
    """Serve bounded subgraph with styling metadata for interactive visualization."""
    if request.method == "OPTIONS":
        return ("", 204)

    target_id = request.args.get("target_id") or request.args.get("concept_id") or "linear_algebra"
    secondary_target_id = request.args.get("secondary_target_id")
    mode = request.args.get("mode") or "mode_c"
    max_nodes = int(request.args.get("max_nodes", 10))
    min_nodes = int(request.args.get("min_nodes", 5))

    from archipelago.graph.subgraph import generate_bounded_subgraph
    from archipelago.graph.engine import KuzuGraphEngine

    db_path = BASE_DIR / "okf_graph.db"
    conn = None
    engine = None
    if db_path.exists():
        try:
            engine = KuzuGraphEngine(db_path=db_path, read_only=True)
            conn = engine.conn
        except Exception:
            pass

    try:
        subgraph = generate_bounded_subgraph(
            target_id=target_id,
            secondary_target_id=secondary_target_id,
            mode=mode,
            max_nodes=max_nodes,
            min_nodes=min_nodes,
            kuzu_conn=conn,
        )
        data = subgraph.to_dict()

        # Enrich nodes with difficulty color and badge
        diff_colors = {
            "foundational": "#10b981",  # emerald green
            "intermediate": "#3b82f6",  # blue
            "advanced": "#8b5cf6",      # purple
            "expert": "#ec4899",        # pink
        }
        for n in data.get("nodes", []):
            diff = (n.get("difficulty") or "intermediate").lower()
            n["color"] = diff_colors.get(diff, "#3b82f6")
            n["badge"] = f"[{diff.capitalize()}]"

        # Enrich edge semantics
        edge_styles = {
            "REQUIRES": {"style": "solid", "color": "#f59e0b", "label": "REQUIRES (Prerequisite)"},
            "UNLOCKS": {"style": "dashed", "color": "#10b981", "label": "UNLOCKS (Progression)"},
            "RELATED": {"style": "dotted", "color": "#9ca3af", "label": "RELATED (Association)"},
            "PROVIDES_TEXT": {"style": "dashed", "color": "#06b6d4", "label": "PROVIDES_TEXT"},
            "MENTIONS": {"style": "dotted", "color": "#64748b", "label": "MENTIONS"},
        }
        for e in data.get("edges", []):
            rel = (e.get("relation") or "REQUIRES").upper()
            style_info = edge_styles.get(rel, {"style": "solid", "color": "#f59e0b", "label": rel})
            e["style"] = style_info["style"]
            e["color"] = style_info["color"]
            e["label"] = style_info["label"]

        return data, 200
    except Exception as exc:
        app.logger.warning("Error generating subgraph: %s", exc)
        return {"error": f"Subgraph generation failed: {exc}"}, 500
    finally:
        if engine:
            try:
                engine.close()
            except Exception:
                pass


@app.route("/api/ingest", methods=["POST", "OPTIONS"])
def proxy_ingest_upload():
    """Proxy multipart file upload to inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        files = {k: (v.filename, v.stream, v.content_type) for k, v in request.files.items()}
        headers = {}
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        upstream = _requests.post(f"{base}/api/ingest", files=files, data=request.form, headers=headers, timeout=60)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502

@app.route("/api/ingest/<job_id>", methods=["GET", "OPTIONS"])
def proxy_ingest_status(job_id):
    """Proxy ingestion job status."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        upstream = _requests.get(
            f"{base}/api/ingest/{job_id}",
            headers=_inference_auth_headers(),
            timeout=10,
        )
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502

@app.route("/api/ingest/<job_id>/cancel", methods=["POST", "GET", "OPTIONS"])
def proxy_ingest_cancel(job_id):
    """Proxy ingestion job cancellation."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        headers = {}
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        upstream = _requests.post(f"{base}/api/ingest/{job_id}/cancel", headers=headers, timeout=10)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502

@app.route("/api/documents", methods=["GET", "OPTIONS"])
def proxy_documents_list():
    """Proxy document list."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        upstream = _requests.get(f"{base}/api/documents", headers=_inference_auth_headers(), timeout=10)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502

@app.route("/api/documents/<path:doc_id>", methods=["DELETE", "OPTIONS"])
def proxy_document_delete(doc_id):
    """Proxy document deletion."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    try:
        headers = {}
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        upstream = _requests.delete(f"{base}/api/documents/{doc_id}", headers=headers, params=request.args, timeout=30)
        return Response(upstream.content, status=upstream.status_code,
                        content_type=upstream.headers.get("Content-Type", "application/json"))
    except Exception as exc:
        return {"error": f"inference upstream unreachable: {exc}"}, 502


@app.route("/<path:filename>")
def static_files(filename):
    """Serves any static resources within the chat_ui directory"""
    return send_from_directory(str(STATIC_DIR), filename)


if __name__ == "__main__":
    port = int(os.environ.get("ARCHIPELAGO_CHAT_PORT", os.environ.get("PORT", "5152")))
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Archipelago Chat UI Server                      ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Landing:      http://localhost:{port}/            ║")
    print(f"║  Chat:         http://localhost:{port}/chat        ║")
    print(f"║  Library:      http://localhost:{port}/library     ║")
    print(f"║  Performance:  http://localhost:{port}/performance ║")
    print(f"║  Safety:       http://localhost:{port}/safety      ║")
    print("╚══════════════════════════════════════════════════╝\n")
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port, debug=False)
