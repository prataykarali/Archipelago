"""Build the exact-source link lines appended to a grounded reply.

Two link families, in priority order:

* **Hugging Face page.** — the dataset PDF at the cited page.
* **Pearson page.** — the institutional e-book reader URL at the cited page,
  built by ``remote_cache.pearson_page_url``.

The link line is re-appended verbatim after LLM polishing, so it must always
point at a real, exact page — never a generic homepage.
"""

from __future__ import annotations

import re
from urllib.parse import quote

HF_LINK_LABEL = "**Hugging Face page.**"
PEARSON_LINK_LABEL = "**Pearson page.**"

PAPER_TITLE_MAP: dict[str, str] = {
    "lewis2020_rag.pdf": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (Lewis et al., 2020)",
    "vaswani2017_attention_is_all_you_need.pdf": "Attention Is All You Need (Vaswani et al., 2017)",
    "brown2020_gpt3.pdf": "Language Models are Few-Shot Learners (Brown et al., 2020)",
    "goodfellow2014_gan.pdf": "Generative Adversarial Nets (Goodfellow et al., 2014)",
    "hu2021_lora.pdf": "LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)",
    "dettmers2023_qlora.pdf": "QLoRA: Efficient Finetuning of Quantized LLMs (Dettmers et al., 2023)",
    "devlin2018_bert.pdf": "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2018)",
    "edge2024_graphrag.pdf": "From Local to Global: A Graph RAG Approach (Edge et al., 2024)",
    "deisenroth_math_for_ml.pdf": "Mathematics for Machine Learning (Deisenroth et al., 2020)",
    "bahdanau2014_attention.pdf": "Neural Machine Translation by Jointly Learning to Align and Translate (Bahdanau et al., 2014)",
    "kwon2023_vllm.pdf": "Efficient Memory Management for LLM Serving with PagedAttention (Kwon et al., 2023)",
    "dao2022_flashattention.pdf": "FlashAttention: Fast and Memory-Efficient Exact Attention (Dao et al., 2022)",
    "karpukhin2020_dpr.pdf": "Dense Passage Retrieval for Open-Domain Question Answering (Karpukhin et al., 2020)",
    "hochreiter1997_lstm.pdf": "Long Short-Term Memory (Hochreiter & Schmidhuber, 1997)",
}


def human_paper_title(raw_title: str, doc_id: str = "") -> str:
    """Resolve a human-readable paper title from a PDF filename or raw title."""
    base = (doc_id or raw_title or "").split("/")[-1].strip().lower()
    if base in PAPER_TITLE_MAP:
        return PAPER_TITLE_MAP[base]
    candidate = (raw_title or "").strip()
    if candidate and not candidate.lower().endswith(".pdf") and "_" not in candidate:
        return candidate
    stem = re.sub(r"\.pdf$", "", (doc_id or raw_title or "Paper").split("/")[-1], flags=re.I)
    m = re.match(r"^([A-Za-z]+)(\d{4})[_\-\s]+(.+)$", stem)
    if m:
        author, year, rest = m.group(1), m.group(2), m.group(3)
        clean_rest = re.sub(r"[_\-]+", " ", rest).strip()
        return f"{clean_rest} ({author} et al., {year})"
    return re.sub(r"[_\-]+", " ", stem).strip() or "Paper"


def source_links(record: dict, book: dict | None, page: int = 1) -> str:
    """Return the newline-joined link lines for one citation record.

    ``record`` is a ``LibraryGraph.cite_record`` result; ``book`` is the matched
    Pearson shelf record (``None`` when no physical/e-book copy matches).
    """
    page_n = int(record["page_number"]) if record.get("page_number") else None
    page_verified = bool(record.get("page_verified", bool(page_n)))
    lines: list[str] = []
    if record.get("url") and record.get("reader_resolvable", True):
        name = (record.get("doc_id") or "paper").split("/")[-1]
        raw_title = record.get("doc_title") or record.get("title") or name
        title = human_paper_title(str(raw_title), name)
        source_url = record["url"]
        if source_url.startswith("/open/"):
            lines.append(f"[{title} (Pearson institutional access)]({source_url})")
        else:
            if page_n and name.lower().endswith(".pdf") and source_url.startswith("/read?"):
                source_url = f"/papers/{quote(name, safe='')}#page={page_n}"
            page_label = f" — p. {page_n}" if page_n else ""
            lines.append(f"[{title}{page_label}]({source_url})")
    if not book:
        return "\n".join(lines)
    if record.get("is_pearson") and record.get("book_id") == book.get("id"):
        return "\n".join(lines)
    page_count = int(book.get("page_count") or 0)
    if page_count and page_n and page_n > page_count:
        return "\n".join(lines)
    href = f"/open/{book.get('id')}"
    book_type = str(book.get("book_type") or "pdf").strip().lower()
    if page_n and page_verified and book_type == "pdf":
        href += f"?page={page_n}"
    btitle = book.get("title") or "Pearson Textbook"
    page_label = f" — page {page_n}" if (page_n and page_verified and book_type == "pdf") else ""
    lines.append(f"[{btitle}{page_label}]({href})")
    return "\n".join(lines)
