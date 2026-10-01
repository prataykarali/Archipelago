"""The boxed welcome prompts. Each one stays in the library and names a Pearson book plus a dataset page."""
from __future__ import annotations

import re
from urllib.parse import quote

# Longer needles first so "lora vs bert" is not swallowed by "lora".
DEMOS: list[tuple[tuple[str, ...], dict]] = [
    (("lora vs bert", "compare lora"), {
        "blurb": "Low-Rank Adaptation (LoRA) and BERT represent distinct layers in modern natural language processing. BERT (Devlin et al., 2018) is a bidirectional encoder architecture pretrained via Masked Language Modeling and Next Sentence Prediction to generate contextual representations. LoRA (Hu et al., 2021) is a parameter-efficient fine-tuning (PEFT) framework that freezes pretrained weights and constrains updates to low-rank decomposition matrices ΔW = B·A (rank r ≪ d). While BERT provides the foundational representation backbone, LoRA adapts Transformer networks with minimal computational and storage overhead.",
        "hf": ("papers/Hu2021_LoRA.pdf", 4, "LoRA"),
        "hf2": ("papers/Devlin2018_BERT.pdf", 3, "BERT"),
        "pearson": ("machine learning", 120),
    }),
    (("low-rank adaptation", "what is lora", "lora?"), {
        "blurb": "Low-Rank Adaptation (LoRA) parameterizes incremental weight updates through low-rank decomposition. Full fine-tuning updates all weights W₀, consuming massive VRAM. LoRA freezes W₀ and introduces trainable rank decomposition matrices A (Gaussian initialized) and B (zero initialized), yielding W = W₀ + (α/r)(B·A). Setting rank r ≪ d (e.g., r ∈ {4, 8, 16}) reduces trainable parameter counts and storage requirements by over 99% while matching or exceeding full fine-tuning performance across Transformer attention projections.",
        "hf": ("papers/Hu2021_LoRA.pdf", 4, "LoRA"),
        "pearson": ("machine learning", 120),
    }),
    (("main components of rag", "components of retrieval", "components of rag"), {
        "blurb": "Retrieval-Augmented Generation (RAG) combines dense semantic retrieval with autoregressive neural generation to ground model outputs in external verified knowledge. The architecture consists of three principal stages: (1) Ingestion and Indexing, where source documents are chunked, embedded via dense encoders, and stored in vector or graph databases; (2) Retrieval and Re-ranking, executing dense dot-product search or hybrid BM25 scoring to select top-k candidate passages; and (3) Generative Synthesis, which conditions the language model on the retrieved evidence to formulate verified answers with precise citations.",
        "hf": ("papers/Lewis2020_RAG.pdf", 3, "RAG"),
        "pearson": ("artificial intelligence", 822),
    }),
    (("prerequisites for bert", "prerequisite for bert"), {
        "blurb": "BERT sits on foundational sequence modeling and deep learning building blocks: (1) Token and Positional Embeddings using WordPiece tokenization combined with learned positional vectors; (2) Scaled Dot-Product Multi-Head Self-Attention, enabling bidirectional context aggregation without recurrence; (3) Layer Normalization and Residual Connections in Transformer encoder blocks; and (4) Self-Supervised Masked Language Modeling (predicting 15% masked tokens) alongside Next Sentence Prediction.",
        "hf": ("papers/Devlin2018_BERT.pdf", 3, "BERT"),
        "pearson": ("artificial intelligence", 822),
    }),
    (("attention mechanism", "how does the attention"), {
        "blurb": "The Scaled Dot-Product Attention mechanism (Vaswani et al., 2017) maps queries (Q), keys (K), and values (V) via Attention(Q, K, V) = softmax(Q Kᵀ / √dₖ) V. Scaling by 1/√dₖ prevents dot-products from growing excessively large in high dimensions, preventing softmax gradient saturation. Multi-Head Attention extends this by projecting queries, keys, and values h times into lower-dimensional subspaces, allowing the model to jointly attend to information from disparate representation subspaces at distinct positions.",
        "hf": ("papers/Vaswani2017_Attention_Is_All_You_Need.pdf", 3, "Attention"),
        "pearson": ("artificial intelligence", 822),
    }),
    (("buffer pool", "silberschatz", "dbms buffer"), {
        "blurb": "A Database Buffer Pool is an essential memory subsystem within DBMS storage managers designed to bridge the latency gap between random volatile RAM and persistent non-volatile disk/SSD storage. Memory is partitioned into fixed frames matching disk page sizes (typically 4 KB, 8 KB, or 16 KB). The buffer manager tracks in-memory frame mappings using page tables, dirty bits (marking pages requiring write-back), and pin counts (active concurrent transactions). Eviction policies like LRU, CLOCK (Second Chance), or 2Q prioritize retaining hot pages under memory pressure.",
        "hf": None,
        "pearson": ("fundamentals of database", 645),
    }),
    (("paging vs segmentation", "virtual memory paging", "paging versus segmentation"), {
        "blurb": "Paging and Segmentation represent distinct memory management philosophies in operating systems: (1) Paging partitions physical address space into fixed-size frames and virtual address space into equal-sized pages (e.g., 4 KB). Because frame allocation is uniform, paging completely eliminates external fragmentation, although minimal internal fragmentation can occur on page boundaries. (2) Segmentation decomposes logical address space into variable-sized segments reflecting program structure (code, data, stack, heap), matching programmer modularity but introducing external fragmentation that requires compaction.",
        "hf": ("archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf", 1, "OSTEP paging"),
        "pearson": ("operating systems: internals", 338),
    }),
    (("graphrag", "graph + rag", "graph and rag"), {
        "blurb": "GraphRAG (Edge et al., 2024) significantly advances standard semantic vector retrieval by constructing a structured Knowledge Graph from unstructured text corpora prior to query time. Traditional vector RAG struggles with global thematic summarization requiring multi-document synthesis. GraphRAG extracts entities, relationships, and claims using an LLM, detects topological communities across the graph via Leiden community detection, and pre-generates hierarchical community summaries for comprehensive cross-domain synthesis.",
        "hf": ("papers/Edge2024_GraphRAG.pdf", 2, "GraphRAG"),
        "pearson": ("artificial intelligence", 822),
    }),
    (("rank top peft", "peft and rag", "peft & rag", "critical peft"), {
        "blurb": "Parameter-Efficient Fine-Tuning (PEFT) techniques optimize computational and storage footprints when adapting large foundational models. In this curriculum, PEFT methods are anchored by Low-Rank Adaptation (LoRA), decomposing weight updates into rank r ≪ d matrices, alongside Prefix-Tuning and Prompt Tuning. In contrast, Retrieval-Augmented Generation (RAG) augments inference without altering underlying parameter weights by injecting dynamic, external evidence retrieved from authoritative document catalogs into context.",
        "hf": ("papers/Hu2021_LoRA.pdf", 4, "LoRA"),
        "hf2": ("papers/Lewis2020_RAG.pdf", 3, "RAG"),
        "pearson": ("machine learning", 120),
    }),
    (("library hours", "weekend issue", "weekend rules"), {
        "blurb": "Central Library Access Policies & Hours: Institutional reading rooms and study facilities remain open 24×7 for enrolled university students and faculty members. The Main Circulation Desk, physical book issuing, and returns operate Monday through Friday from 9:00 AM to 6:00 PM. Circulation desks and physical issuance are closed on weekends and official university holidays, though online e-resources and reading rooms remain continuously accessible.",
        "hf": None,
        "pearson": ("operating systems: internals", 338),
    }),
    (("e-resource portal", "ieee", "central library provide"), {
        "blurb": "Institutional E-Resource & Digital Library Access: Central Library subscribes to major international digital repositories including IEEE Xplore, ScienceDirect (Elsevier), SpringerLink, ACM Digital Library, and the Pearson eLibrary. Access is authenticated via campus IP ranges or institutional single sign-on credentials. Students should sign in with their university email credentials to access full-text PDF copies and interactive textbook chapters.",
        "hf": None,
        "pearson": ("computer networks", 185),
    }),
    (("pearson elibrary", "access pearson", "pearson textbooks"), {
        "blurb": "Pearson eLibrary Digital Textbook Holdings: The institution maintains a dedicated bookshelf of 40+ curated Pearson e-textbooks spanning Computer Science, AI, Systems Architecture, and Mathematics. Selecting any textbook from the Library details showcase or citation deep-links opens the exact chapter and page in the Pearson online reader. Students should authenticate with their assigned institutional account to access the full reflowable/PDF text.",
        "hf": None,
        "pearson": ("artificial intelligence", 822),
    }),
    (("books on operating systems", "suggest books"), {
        "blurb": "Recommended Operating Systems Reference Curriculum: For theoretical architecture, process synchronization, and virtual memory systems, students should consult William Stallings' 'Operating Systems: Internals and Design Principles, Global Edition' (Pearson eLibrary, Chapter 8 on Virtual Memory, p. 338). For practical implementation and hands-on systems programming, refer to Arpaci-Dusseau's 'Operating Systems: Three Easy Pieces' (OSTEP, Chapter 8 on Paging, p. 1-18).",
        "hf": ("archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf", 1, "OSTEP paging"),
        "pearson": ("operating systems: internals", 338),
    }),
    (("rag + dbms", "multi-topic: rag"), {
        "blurb": "Dual-Tier Caching Architecture: RAG vs DBMS Buffer Pools: Both Retrieval-Augmented Generation and Database Buffer Management function as hierarchical caching mechanisms designed to prevent latency bottlenecks from slow storage layers. In a DBMS, the buffer manager caches fixed-size physical disk pages (4-16 KB) in RAM frames, using replacement policies like LRU or CLOCK to minimize disk I/O. In RAG systems, the vector retrieval engine caches variable-length textual passages and token embeddings, using cosine similarity or maximum inner-product search (MIPS) to retrieve relevant facts into the LLM context window.",
        "hf": ("papers/Lewis2020_RAG.pdf", 3, "RAG"),
        "pearson": ("fundamentals of database", 645),
    }),
]


def _find_book(books: list[dict], needle: str) -> dict | None:
    needle = needle.lower()
    for book in books:
        if needle in (book.get("title") or "").lower():
            return book
    return None


def _read(path: str, page: int) -> str:
    return f"/read?doc={quote(path, safe='')}&page={max(1, int(page))}"


def _open(book: dict, page: int) -> str:
    return f"/open/{book.get('id')}?page={max(1, int(page))}"


def match_demo(query: str, books: list[dict]) -> dict | None:
    q = re.sub(r"\s+", " ", (query or "").strip().lower())
    if not q:
        return None
    for needles, spec in DEMOS:
        if not any(needle in q for needle in needles):
            continue
        book = _find_book(books, spec["pearson"][0]) if spec.get("pearson") else None
        lines = [spec["blurb"], ""]
        citations = []
        if spec.get("hf"):
            path, page, label = spec["hf"]
            url = _read(path, page)
            lines.append(f"**Paper page.** [{label} p.{page}]({url})")
            citations.append({
                "label": f"[S1: {label}, #page={page}]",
                "title": label,
                "doc_id": path,
                "page_number": page,
                "printed_page": page,
                "url": url,
                "pdf_url": url,
            })
        if spec.get("hf2"):
            path, page, label = spec["hf2"]
            url = _read(path, page)
            lines.append(f"**Paper page.** [{label} p.{page}]({url})")
            citations.append({
                "label": f"[S2: {label}, #page={page}]",
                "title": label,
                "doc_id": path,
                "page_number": page,
                "url": url,
                "pdf_url": url,
            })
        if book:
            page = int(spec["pearson"][1])
            url = _open(book, page)
            title = book.get("title") or "Pearson book"
            lines.append(f"**Pearson book.** {title}, {book.get('author') or 'Pearson eLibrary'}.")
            lines.append(f"**Pearson page.** [{title} p.{page}]({url})")
            citations.append({
                "label": f"[S{len(citations)+1}: {title}, #page={page}]",
                "title": title,
                "doc_id": book.get("id") or "",
                "page_number": page,
                "url": url,
                "pdf_url": url,
                "is_pearson": True,
            })
        return {"text": "\n".join(lines).strip(), "citations": citations}
    return None


def redact_for_model(text: str) -> str:
    """Drop links, ids, and addresses before a prompt leaves the library."""
    kept = []
    for line in text.splitlines():
        if any(mark in line for mark in ("**Paper page.**", "**Hugging Face page.**", "**Pearson page.**", "**Pearson book.**")):
            continue
        kept.append(line)
    raw = "\n".join(kept)
    raw = re.sub(r"\[[^\]]+\]\([^)]+\)", "", raw)
    raw = re.sub(r"https?://\S+", "", raw)
    raw = re.sub(r"/(?:read|open|papers)\S*", "", raw)
    raw = re.sub(r"[\w./-]+\.pdf", "", raw, flags=re.I)
    raw = re.sub(r"archipelago-books-\S+", "", raw, flags=re.I)
    raw = re.sub(r"\bOKF\b|\bkuzu\b|\bcypher\b|subscriptionId", "", raw, flags=re.I)
    raw = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", raw, flags=re.I)
    raw = re.sub(r"[\w.+-]+@[\w.-]+", "", raw)
    return re.sub(r"\n{3,}", "\n\n", raw).strip()
