"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
import json
import os
import re
from pathlib import Path
import requests as _requests
from .merged01_repo_root import BASE_DIR, app  # noqa: F401


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
    #
    # Credentials are read ONLY from the environment and never carry a
    # source-code default, so the repository never holds a live secret. If they
    # are not configured the panel is simply omitted.
    p_user = os.environ.get("PEARSON_ACCOUNT_USERNAME", "").strip()
    p_pass = os.environ.get("PEARSON_ACCOUNT_PASSWORD", "").strip()
    expose_reader_credentials = os.environ.get(
        "ARCHIPELAGO_EXPOSE_READER_CREDENTIALS", "0"
    ).strip().lower() in {"1", "true", "yes"}
    pearson_hint = ""
    if "pearson" in target_url.lower() and expose_reader_credentials and p_user and p_pass:
        safe_user = _html.escape(p_user, quote=True)
        safe_pass = _html.escape(p_pass, quote=True)
        safe_user_js = json.dumps(p_user)
        safe_pass_js = json.dumps(p_pass)
        pearson_hint = f"""
    <div style="margin-top: 1.25rem; padding: 1rem; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 0.75rem; font-size: 0.85rem; color: #fde68a; line-height: 1.5; text-align: left;">
      <div style="font-weight: 700; margin-bottom: 0.5rem; color: #fbbf24;">🔑 Institutional Access Credentials:</div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
        <span>User: <strong id="cas-user">{safe_user}</strong></span>
        <button type="button" onclick="navigator.clipboard.writeText({safe_user_js});this.textContent='Copied!'" style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; cursor: pointer;">Copy</button>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>Pass: <strong id="cas-pass">{safe_pass}</strong></span>
        <button type="button" onclick="navigator.clipboard.writeText({safe_pass_js});this.textContent='Copied!'" style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; cursor: pointer;">Copy</button>
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
