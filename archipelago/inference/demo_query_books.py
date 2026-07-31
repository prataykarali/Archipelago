"""Hardcoded demo-query book stack + availability + page links.

Spreadsheet: docs/demo_query_books.csv
doc_id values must match files under pdfs/ so Page/Split modes open real PDFs.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

_QUERY_MATCHERS: list[tuple[str, tuple[str, ...]]] = [
    ("lora_vs_bert", ("lora vs bert", "compare lora", "lora versus bert")),
    ("lora", ("low-rank adaptation", "what is lora", "lora?")),
    ("rag", ("main components of rag", "components of retrieval augmented", "components of rag")),
    ("bert", ("prerequisites for bert", "prerequisite for bert")),
    ("attention", ("attention mechanism", "how does the attention")),
    ("dbms_buffer", ("buffer pools", "silberschatz", "dbms buffer")),
    ("ostep_paging", ("paging vs segmentation", "virtual memory paging", "paging versus segmentation")),
    ("graphrag", ("graphrag", "graph + rag", "graph and rag")),
    ("peft_rank", ("rank top peft", "peft & rag", "peft and rag papers")),
    ("multi_rag_dbms", ("rag + dbms", "multi-topic: rag", "rag + dbms")),
]

# Aliases: booth / inventory ids → real corpus paths under pdfs/
DOC_ID_ALIASES: dict[str, str] = {
    "lewis2020_rag": "papers/Lewis2020_RAG.pdf",
    "hu2021_lora": "papers/Hu2021_LoRA.pdf",
    "devlin2018_bert": "papers/Devlin2018_BERT.pdf",
    "vaswani2017_attention": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "graphrag_ms": "papers/Edge2024_GraphRAG.pdf",
    "peft_survey": "papers/Hu2021_LoRA.pdf",
    "ostep_three_easy_pieces": "ostep_three_easy_pieces/08_Paging.pdf",
    "ostep_paging": "ostep_three_easy_pieces/08_Paging.pdf",
    "operating_system_concepts_silberschatz": "ostep_three_easy_pieces/08_Paging.pdf",
    # No full Silberschatz DBMS PDF in pilot — use OSTEP I/O chapter as related systems text
    # only when no better file exists; prefer summary-only for pure DBMS rows.
    "database_system_concepts_silberschatz": "",
    "database_management_systems_ramakrishnan": "",
}

DEMO_BOOK_ROWS: list[dict[str, Any]] = [
    {
        "query_key": "lora",
        "book_id": "hu2021_lora",
        "doc_id": "papers/Hu2021_LoRA.pdf",
        "book_title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Edward J. Hu et al.",
        "total_copies": 3,
        "available_copies": 2,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-PEFT-01",
        "page_number": 1,
        "topic": "Low-Rank Adaptation",
        "summary": (
            "LoRA freezes the pretrained weight matrix W0 and injects a trainable low-rank "
            "update ΔW = BA, where B ∈ R^{d×r}, A ∈ R^{r×k}, and rank r ≪ min(d, k). "
            "At inference the update can be merged: W = W0 + BA. This cuts trainable "
            "parameters while matching full fine-tuning quality on many tasks."
        ),
    },
    {
        "query_key": "lora",
        "book_id": "peft_survey",
        "doc_id": "papers/Dettmers2023_QLoRA.pdf",
        "book_title": "QLoRA / PEFT companion (library PEFT shelf)",
        "authors": "Dettmers et al. / PEFT collection",
        "total_copies": 2,
        "available_copies": 1,
        "availability": "Available",
        "is_reference": True,
        "shelf_location": "AIML-PEFT-REF",
        "page_number": 1,
        "topic": "parameter-efficient fine-tuning",
        "summary": (
            "QLoRA combines 4-bit quantization of the base model with LoRA adapters so "
            "large LMs can be fine-tuned on a single GPU. Adapters stay in higher precision; "
            "the frozen backbone stays quantized — a practical PEFT stack next to classic LoRA."
        ),
    },
    {
        "query_key": "rag",
        "book_id": "lewis2020_rag",
        "doc_id": "papers/Lewis2020_RAG.pdf",
        "book_title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
        "authors": "Patrick Lewis et al.",
        "total_copies": 4,
        "available_copies": 3,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-RAG-01",
        "page_number": 1,
        "topic": "retrieval-augmented generation",
        "summary": (
            "RAG pairs a parametric generator with a non-parametric retriever over a "
            "document index. Query → retrieve top-k passages → condition the seq2seq "
            "model on those passages. Main components: retriever (query encoder + "
            "document index), retrieved context, and generator that produces the answer."
        ),
    },
    {
        "query_key": "rag",
        "book_id": "graphrag_ms",
        "doc_id": "papers/Edge2024_GraphRAG.pdf",
        "book_title": "GraphRAG / hybrid retrieval notes",
        "authors": "Microsoft Research (Edge et al.)",
        "total_copies": 2,
        "available_copies": 2,
        "availability": "Available in library",
        "is_reference": True,
        "shelf_location": "AIML-RAG-REF",
        "page_number": 1,
        "topic": "GraphRAG",
        "summary": (
            "GraphRAG builds an entity/relation graph over the corpus, runs community "
            "detection, and uses community summaries plus local graph context at query "
            "time — extending classic RAG when answers need global structure."
        ),
    },
    {
        "query_key": "bert",
        "book_id": "devlin2018_bert",
        "doc_id": "papers/Devlin2018_BERT.pdf",
        "book_title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": "Jacob Devlin et al.",
        "total_copies": 5,
        "available_copies": 4,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-NLP-01",
        "page_number": 1,
        "topic": "BERT pre-training",
        "summary": (
            "BERT prerequisites: token/position/segment embeddings, multi-head self-attention, "
            "feed-forward blocks, and the Transformer encoder stack. Pre-training uses Masked "
            "LM and Next Sentence Prediction; fine-tuning adds a task head on [CLS]."
        ),
    },
    {
        "query_key": "bert",
        "book_id": "vaswani2017_attention",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "book_title": "Attention Is All You Need",
        "authors": "Ashish Vaswani et al.",
        "total_copies": 4,
        "available_copies": 3,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-NLP-02",
        "page_number": 3,
        "topic": "scaled dot-product attention",
        "summary": (
            "The Transformer attention prerequisite for BERT: "
            "Attention(Q, K, V) = softmax(QK^T / √d_k) V. Multi-head attention runs this "
            "in parallel subspaces; residual + LayerNorm stabilize deep stacks."
        ),
    },
    {
        "query_key": "attention",
        "book_id": "vaswani2017_attention",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "book_title": "Attention Is All You Need",
        "authors": "Ashish Vaswani et al.",
        "total_copies": 4,
        "available_copies": 3,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-NLP-02",
        "page_number": 3,
        "topic": "Attention mechanism",
        "summary": (
            "Scaled dot-product attention compares queries to keys, scales by √d_k to keep "
            "softmax in a stable range, then weights values. Multi-head attention lets the "
            "model jointly attend to different representation subspaces."
        ),
    },
    {
        "query_key": "attention",
        "book_id": "devlin2018_bert",
        "doc_id": "papers/Devlin2018_BERT.pdf",
        "book_title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": "Jacob Devlin et al.",
        "total_copies": 5,
        "available_copies": 4,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-NLP-01",
        "page_number": 2,
        "topic": "self-attention",
        "summary": (
            "BERT applies bidirectional self-attention so every token can condition on left "
            "and right context in every layer — the practical use of the Transformer encoder "
            "attention block for language understanding."
        ),
    },
    {
        "query_key": "dbms_buffer",
        "book_id": "database_system_concepts_silberschatz",
        "doc_id": "",
        "book_id_note": "pilot has metadata only — summary is hardcoded",
        "book_title": "Database System Concepts (Silberschatz / Korth / Sudarshan)",
        "authors": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "total_copies": 4,
        "available_copies": 4,
        "availability": "Available in library",
        "is_reference": True,
        "shelf_location": "DBMS-01",
        "page_number": 1,
        "topic": "buffer pool",
        "summary": (
            "Silberschatz: the buffer manager caches disk pages in a fixed buffer pool. "
            "On a request it checks the pool; on a miss it selects a victim (e.g. LRU/clock), "
            "writes dirty pages if needed, then reads the page from disk. Pins prevent eviction "
            "while a page is in use. Reference copy — library use only."
        ),
    },
    {
        "query_key": "dbms_buffer",
        "book_id": "database_management_systems_ramakrishnan",
        "doc_id": "",
        "book_title": "Database Management Systems (Ramakrishnan & Gehrke)",
        "authors": "Raghu Ramakrishnan, Johannes Gehrke",
        "total_copies": 5,
        "available_copies": 5,
        "availability": "Available in library",
        "is_reference": True,
        "shelf_location": "DBMS-02",
        "page_number": 1,
        "topic": "buffer manager",
        "summary": (
            "Ramakrishnan & Gehrke: buffer pool frames hold pages; replacement policy and "
            "dirty-bit handling decide I/O cost. Good policies cut random disk reads for "
            "index and heap scans. Reference companion to Silberschatz on buffer pools."
        ),
    },
    {
        "query_key": "ostep_paging",
        "book_id": "ostep_three_easy_pieces",
        "doc_id": "ostep_three_easy_pieces/08_Paging.pdf",
        "book_title": "Operating Systems: Three Easy Pieces — Paging",
        "authors": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "total_copies": 7,
        "available_copies": 4,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "OS-01",
        "page_number": 1,
        "topic": "paging",
        "summary": (
            "OSTEP paging: virtual address → VPN + offset; page table maps VPN to PFN. "
            "Fixed-size pages avoid external fragmentation. TLBs cache translations. "
            "Compared with segmentation, paging uses uniform pages instead of variable segments."
        ),
    },
    {
        "query_key": "ostep_paging",
        "book_id": "operating_system_concepts_silberschatz",
        "doc_id": "ostep_three_easy_pieces/07_Address_Translation.pdf",
        "book_title": "Address Translation (OSTEP) — segmentation vs paging context",
        "authors": "Arpaci-Dusseau (pilot stand-in for Silberschatz OS chapter)",
        "total_copies": 4,
        "available_copies": 4,
        "availability": "Available in library",
        "is_reference": True,
        "shelf_location": "OS-02",
        "page_number": 1,
        "topic": "address translation",
        "summary": (
            "Segmentation uses base+limit per logical segment (code/data/stack); paging "
            "splits address space into fixed pages. Hybrid schemes exist, but pure paging "
            "dominates modern OSes for simple free-list management and sharing."
        ),
    },
    {
        "query_key": "graphrag",
        "book_id": "graphrag_ms",
        "doc_id": "papers/Edge2024_GraphRAG.pdf",
        "book_title": "From Local to Global: GraphRAG",
        "authors": "Microsoft Research (Edge et al.)",
        "total_copies": 2,
        "available_copies": 1,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-RAG-03",
        "page_number": 1,
        "topic": "GraphRAG",
        "summary": (
            "GraphRAG extracts entities/relationships, clusters into communities, summarizes "
            "each community, then answers with local graph neighborhoods and/or global "
            "community summaries — graph structure plus RAG synthesis."
        ),
    },
    {
        "query_key": "graphrag",
        "book_id": "lewis2020_rag",
        "doc_id": "papers/Lewis2020_RAG.pdf",
        "book_title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
        "authors": "Patrick Lewis et al.",
        "total_copies": 4,
        "available_copies": 3,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-RAG-01",
        "page_number": 1,
        "topic": "RAG",
        "summary": (
            "Classic RAG baseline: dense retrieval of text chunks into the generator. "
            "GraphRAG extends this when multi-hop or corpus-global questions need structure "
            "beyond top-k independent passages."
        ),
    },
    {
        "query_key": "peft_rank",
        "book_id": "hu2021_lora",
        "doc_id": "papers/Hu2021_LoRA.pdf",
        "book_title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Edward J. Hu et al.",
        "total_copies": 3,
        "available_copies": 2,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-PEFT-01",
        "page_number": 1,
        "topic": "LoRA",
        "summary": "Top PEFT method in the pilot shelf: low-rank adapters BA on frozen W0.",
    },
    {
        "query_key": "peft_rank",
        "book_id": "lewis2020_rag",
        "doc_id": "papers/Lewis2020_RAG.pdf",
        "book_title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
        "authors": "Patrick Lewis et al.",
        "total_copies": 4,
        "available_copies": 3,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-RAG-01",
        "page_number": 1,
        "topic": "RAG",
        "summary": "Top RAG paper: retriever + generator for knowledge-intensive NLP.",
    },
    {
        "query_key": "peft_rank",
        "book_id": "peft_survey",
        "doc_id": "papers/Dettmers2023_QLoRA.pdf",
        "book_title": "QLoRA (PEFT efficiency companion)",
        "authors": "Dettmers et al.",
        "total_copies": 2,
        "available_copies": 1,
        "availability": "Available",
        "is_reference": True,
        "shelf_location": "AIML-PEFT-REF",
        "page_number": 1,
        "topic": "QLoRA",
        "summary": "Reference PEFT efficiency paper: 4-bit base + LoRA adapters.",
    },
    {
        "query_key": "multi_rag_dbms",
        "book_id": "lewis2020_rag",
        "doc_id": "papers/Lewis2020_RAG.pdf",
        "book_title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
        "authors": "Patrick Lewis et al.",
        "total_copies": 4,
        "available_copies": 3,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-RAG-01",
        "page_number": 1,
        "topic": "RAG",
        "summary": "RAG half: retrieve passages, then generate grounded answers.",
    },
    {
        "query_key": "multi_rag_dbms",
        "book_id": "database_system_concepts_silberschatz",
        "doc_id": "",
        "book_title": "Database System Concepts (Silberschatz)",
        "authors": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "total_copies": 4,
        "available_copies": 4,
        "availability": "Available in library",
        "is_reference": True,
        "shelf_location": "DBMS-01",
        "page_number": 1,
        "topic": "buffer pool",
        "summary": (
            "DBMS half: buffer pools cache pages so query operators avoid repeated disk I/O — "
            "the storage engine counterpart to RAG's retrieval cache over documents."
        ),
    },
    {
        "query_key": "lora_vs_bert",
        "book_id": "hu2021_lora",
        "doc_id": "papers/Hu2021_LoRA.pdf",
        "book_title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Edward J. Hu et al.",
        "total_copies": 3,
        "available_copies": 2,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-PEFT-01",
        "page_number": 1,
        "topic": "LoRA",
        "summary": (
            "LoRA side: keep W0 frozen; train tiny BA. Cheap multi-task adapters; merge at deploy."
        ),
    },
    {
        "query_key": "lora_vs_bert",
        "book_id": "devlin2018_bert",
        "doc_id": "papers/Devlin2018_BERT.pdf",
        "book_title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": "Jacob Devlin et al.",
        "total_copies": 5,
        "available_copies": 4,
        "availability": "Available",
        "is_reference": False,
        "shelf_location": "AIML-NLP-01",
        "page_number": 1,
        "topic": "BERT fine-tuning",
        "summary": (
            "BERT side: full (or head) fine-tuning of a bidirectional Transformer pretrained "
            "with MLM/NSP — more parameters updated than LoRA, classic transfer baseline."
        ),
    },
]

_CSV_PATH = Path(__file__).resolve().parents[2] / "docs" / "demo_query_books.csv"
_PDF_ROOT = Path(__file__).resolve().parents[2] / "pdfs"


def resolve_doc_id(doc_id: str) -> str:
    """Map alias / bare id to a path under pdfs/ when possible."""
    raw = (doc_id or "").strip().lstrip("/")
    if raw.startswith("pdfs/"):
        raw = raw[5:]
    if not raw:
        return ""
    if raw in DOC_ID_ALIASES:
        mapped = DOC_ID_ALIASES[raw]
        return mapped or ""
    low = raw.lower()
    for alias, target in DOC_ID_ALIASES.items():
        if alias.lower() == low or alias.lower() in low.replace("\\", "/"):
            return target or raw
    # bare filename → papers/
    if "/" not in raw and raw.lower().endswith(".pdf"):
        candidate = f"papers/{raw}"
        if (_PDF_ROOT / candidate).exists():
            return candidate
    return raw


def _coerce_row(raw: dict[str, str]) -> dict[str, Any]:
    ref = str(raw.get("is_reference", "")).strip().lower() in {"1", "true", "yes", "y"}
    doc = str(raw.get("doc_id") or raw.get("book_id") or "").strip()
    doc = resolve_doc_id(doc) if doc else ""
    return {
        "query_key": str(raw.get("query_key", "")).strip(),
        "book_id": str(raw.get("book_id", "")).strip(),
        "doc_id": doc,
        "book_title": str(raw.get("book_title", "")).strip(),
        "authors": str(raw.get("authors", "")).strip(),
        "total_copies": int(raw.get("total_copies") or 0),
        "available_copies": int(raw.get("available_copies") or 0),
        "availability": str(raw.get("availability", "")).strip() or "Unknown",
        "is_reference": ref,
        "shelf_location": str(raw.get("shelf_location", "")).strip(),
        "page_number": int(raw.get("page_number") or 1),
        "topic": str(raw.get("topic", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
    }


def _load_rows() -> list[dict[str, Any]]:
    # Prefer in-module DEMO_BOOK_ROWS (authoritative for booth); CSV is export.
    return [dict(r) for r in DEMO_BOOK_ROWS]


_ROWS: list[dict[str, Any]] = _load_rows()


def match_demo_query_key(query: str) -> str | None:
    q = re.sub(r"\s+", " ", (query or "").strip().lower())
    if not q:
        return None
    for key, needles in _QUERY_MATCHERS:
        if any(n in q for n in needles):
            return key
    return None


def books_for_query(query: str) -> list[dict[str, Any]]:
    key = match_demo_query_key(query)
    if not key:
        return []
    return [dict(r) for r in _ROWS if r["query_key"] == key]


def book_titles_phrase(books: list[dict[str, Any]]) -> str:
    titles = [str(b.get("book_title") or "").strip() for b in books if b.get("book_title")]
    titles = [t for t in titles if t]
    if not titles:
        return ""
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f"{titles[0]} and {titles[1]}"
    return ", ".join(titles[:-1]) + f", and {titles[-1]}"


def page_view_href(book: dict[str, Any]) -> str:
    doc = resolve_doc_id(str(book.get("doc_id") or book.get("book_id") or ""))
    if not doc:
        return ""
    page = int(book.get("page_number") or 1) or 1
    topic = str(book.get("topic") or "").strip()
    q = f"/api/page-view?doc_id={quote(doc, safe='')}&page={page}"
    if topic:
        q += f"&highlight={quote(topic[:120], safe='')}"
    return f"{q}#page={page}"


def format_availability_table(books: list[dict[str, Any]]) -> str:
    if not books:
        return ""
    lines = [
        "",
        "### Library holdings for this topic",
        "",
        "| Book | Page | Copies | Available | Reference? | Status | Shelf | Open |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for b in books:
        ref = "Yes (library use only)" if b.get("is_reference") else "No (circulating)"
        href = page_view_href(b)
        open_cell = f"[p.{int(b.get('page_number') or 1)} ↗]({href})" if href else "Passage only"
        lines.append(
            "| {title} | {page} | {total} | {avail} | {ref} | {status} | {shelf} | {open} |".format(
                title=str(b.get("book_title") or "—").replace("|", "/"),
                page=int(b.get("page_number") or 1),
                total=int(b.get("total_copies") or 0),
                avail=int(b.get("available_copies") or 0),
                ref=ref,
                status=str(b.get("availability") or "—").replace("|", "/"),
                shelf=str(b.get("shelf_location") or "—").replace("|", "/"),
                open=open_cell,
            )
        )
    lines.append("")
    return "\n".join(lines)


def format_inline_page_links(books: list[dict[str, Any]]) -> str:
    chips: list[str] = []
    for b in books:
        href = page_view_href(b)
        title = str(b.get("book_title") or "Source").strip()
        short = title if len(title) <= 42 else title[:40] + "…"
        page = int(b.get("page_number") or 1) or 1
        if href:
            chips.append(f"[📄 {short} · p.{page} ↗]({href})")
        else:
            chips.append(f"📄 {short} (reference summary — no pilot PDF)")
    if not chips:
        return ""
    return "\n\n**Open source pages:** " + " · ".join(chips) + "\n"


def enrich_reply_with_books(query: str, reply: str) -> str:
    books = books_for_query(query)
    if not books:
        return reply or ""
    body = (reply or "").rstrip()
    if "Library holdings for this topic" in body:
        return body
    phrase = book_titles_phrase(books)
    mention = (
        f"\n\n**Sources on the shelf:** This answer draws on **{phrase}** "
        f"from the library stack for this topic."
    )
    return body + mention + format_inline_page_links(books) + format_availability_table(books)


def citation_overlays_for_query(query: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, b in enumerate(books_for_query(query), start=1):
        doc = resolve_doc_id(str(b.get("doc_id") or b.get("book_id") or ""))
        page = int(b.get("page_number") or 1) or 1
        topic = str(b.get("topic") or "")
        title = str(b.get("book_title") or "Library book")
        href = page_view_href(b)
        out.append(
            {
                "evidence_id": f"B{i}",
                "doc_id": doc or str(b.get("book_id") or f"demo_book_{i}"),
                "title": title,
                "document_title": title,
                "source_title": title,
                "authors": b.get("authors") or "",
                "page_number": page,
                "topic": topic,
                "section_title": topic,
                "summary": b.get("summary") or "",
                "passage": b.get("summary") or "",
                "page_url": href,
                "url": href,
                "pdf": f"{doc}#page={page}" if doc else "",
                "is_reference": bool(b.get("is_reference")),
                "availability": b.get("availability") or "",
                "total_copies": int(b.get("total_copies") or 0),
                "available_copies": int(b.get("available_copies") or 0),
                "shelf_location": b.get("shelf_location") or "",
            }
        )
    return out


def merge_demo_citations(
    query: str,
    citations: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    overlays = citation_overlays_for_query(query)
    if not overlays:
        return list(citations or [])
    existing = list(citations or [])
    for c in existing:
        did = str(c.get("doc_id") or c.get("document_id") or c.get("source_id") or "")
        resolved = resolve_doc_id(did)
        if resolved:
            c["doc_id"] = resolved
        for o in overlays:
            o_doc = str(o.get("doc_id") or "")
            if o_doc and (o_doc == did or o_doc == resolved or o_doc in did or did in o_doc):
                c["title"] = o["title"]
                c["document_title"] = o["title"]
                c["source_title"] = o["title"]
                if o.get("page_url"):
                    c["page_url"] = o["page_url"]
                if o.get("summary") and not c.get("summary"):
                    c["summary"] = o["summary"]
                break
    seen = {
        str(c.get("title") or c.get("document_title") or "").strip().lower()
        for c in existing
    }
    merged = list(existing)
    for o in overlays:
        t = str(o.get("title") or "").strip().lower()
        if t and t not in seen:
            merged.insert(0, o)
            seen.add(t)
    return merged


def demo_passage_for_doc(doc_id: str, page: int = 1, highlight: str = "") -> dict[str, Any] | None:
    """Lookup hardcoded summary for page-view when graph has no chunk.

    Only matches by document id / alias — never by highlight alone (that would
    hijack unknown docs like paper.pdf into an unrelated booth summary).
    """
    raw = (doc_id or "").strip()
    if not raw:
        return None
    resolved = resolve_doc_id(raw)
    # Bare unknown filenames (paper.pdf) that do not alias → no demo hit
    if raw == resolved or (not resolved and "/" not in raw):
        # Still allow exact book_id / known alias keys
        low = raw.lower().replace("\\", "/")
        alias_hit = low in {k.lower() for k in DOC_ID_ALIASES} or any(
            low == str(r.get("book_id") or "").lower()
            or low == str(r.get("doc_id") or "").lower().replace("\\", "/")
            or low.endswith("/" + str(Path(str(r.get("doc_id") or "")).name).lower())
            for r in _ROWS
        )
        if not alias_hit and not (resolved and (_PDF_ROOT / resolved).is_file()):
            # If resolve left path unchanged and file missing → not a demo doc
            if not resolved or not (_PDF_ROOT / resolved).is_file():
                if low not in {k.lower() for k in DOC_ID_ALIASES}:
                    if not any(low == str(r.get("book_id") or "").lower() for r in _ROWS):
                        if "/" not in raw and raw.lower().endswith(".pdf"):
                            # unknown bare pdf stem
                            known = (
                                "lora", "bert", "rag", "lewis", "hu2021", "devlin",
                                "vaswani", "edge", "attention", "qlora", "dettmers",
                            )
                            if not any(k in low for k in known):
                                return None

    targets = {raw, resolved}
    if resolved:
        targets.add(Path(resolved).name)
    targets = {t for t in targets if t}
    targets_l = {t.lower().replace("\\", "/") for t in targets}

    for row in _ROWS:
        rdoc = resolve_doc_id(str(row.get("doc_id") or row.get("book_id") or ""))
        rid = str(row.get("book_id") or "")
        candidates = {rdoc, rid, Path(rdoc).name if rdoc else ""}
        candidates_l = {c.lower().replace("\\", "/") for c in candidates if c}
        if targets_l & candidates_l:
            return {
                "doc_id": rdoc or rid,
                "page": int(row.get("page_number") or page or 1),
                "highlight": highlight or str(row.get("topic") or ""),
                "passage": str(row.get("summary") or ""),
                "text": str(row.get("summary") or ""),
                "title": str(row.get("book_title") or ""),
                "authors": str(row.get("authors") or ""),
                "section_title": str(row.get("topic") or ""),
            }
    return None
