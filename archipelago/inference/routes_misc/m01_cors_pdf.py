"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote
from flask import jsonify, send_from_directory, request, redirect
from archipelago.inference import state as st


@st.app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Archipelago-Token,X-Librarian-Token,X-API-Token")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response


@st.app.route("/pdfs/<path:filename>")
def serve_pdf(filename):
    """Serve local papers/textbooks from the pdfs folder.

    Searches recursively under pdfs/ and falls back to remote arXiv/publisher URLs.
    """
    pdf_dir = Path(st.PDF_DIR)
    target_name = Path(filename).name

    # 1. Check exact path
    candidate = pdf_dir / filename
    if candidate.is_file():
        return send_from_directory(str(candidate.parent), candidate.name)

    # 2. Check direct stem under pdf_dir or subfolders (papers/, textbooks/, etc.)
    for match in pdf_dir.glob(f"**/{target_name}"):
        if match.is_file():
            return send_from_directory(str(match.parent), match.name)

    # 3. Check arXiv regex pattern (e.g. 1706.03762v7.pdf)
    arxiv_match = re.search(r"(\d{4}\.\d{4,5})", target_name)
    if arxiv_match:
        return redirect(f"https://arxiv.org/pdf/{arxiv_match.group(1)}", code=302)

    # 4. Check remote URL fallback registry
    remote = REMOTE_PDF_SOURCES.get(target_name)
    if remote:
        return redirect(remote, code=302)

    # 4.5 Check Pearson eLibrary Catalog resolution
    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve
        pearson_url = pearson_resolve(filename)
        if not pearson_url and target_name != filename:
            pearson_url = pearson_resolve(target_name)
        if pearson_url:
            return redirect(pearson_url, code=302)
    except Exception:
        pass

    # 5. Hugging Face Cloud Gateway fallback for non-Pearson books & papers
    hf_cloud_url = f"https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/{quote(target_name, safe='')}"
    return redirect(hf_cloud_url, code=302)


REMOTE_PDF_SOURCES = {
    "Vaswani2017_Attention_Is_All_You_Need.pdf": "https://arxiv.org/pdf/1706.03762",
    "Hu2021_LoRA.pdf": "https://arxiv.org/pdf/2106.09685",
    "Dettmers2023_QLoRA.pdf": "https://arxiv.org/pdf/2305.14314",
    "Lewis2020_RAG.pdf": "https://arxiv.org/pdf/2005.11401",
    "Devlin2018_BERT.pdf": "https://arxiv.org/pdf/1810.04805",
    "Edge2024_GraphRAG.pdf": "https://arxiv.org/pdf/2404.16130",
    "Bahdanau2014_Attention.pdf": "https://arxiv.org/pdf/1409.0473",
    "Kwon2023_vLLM.pdf": "https://arxiv.org/pdf/2309.06180",
    "Brown2020_GPT3.pdf": "https://arxiv.org/pdf/2005.14165",
    "Wei2022_ChainOfThought.pdf": "https://arxiv.org/pdf/2201.11903",
    "Yao2022_ReAct.pdf": "https://arxiv.org/pdf/2210.03629",
    "Rafailov2023_DPO.pdf": "https://arxiv.org/pdf/2305.18290",
    "Karpukhin2020_DPR.pdf": "https://arxiv.org/pdf/2004.04906",
    "Willard2023_Outlines.pdf": "https://arxiv.org/pdf/2307.09702",
    "Ouyang2022_InstructGPT.pdf": "https://arxiv.org/pdf/2203.02155",
    "Deisenroth_Math_For_ML.pdf": "https://mml-book.github.io/book/mml-book.pdf",
}
