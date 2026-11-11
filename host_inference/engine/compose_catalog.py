"""Paper and catalog reply composition for the hosted engine."""

from __future__ import annotations

import re

from . import catalogue
from .constants import KILL_SWITCH

VERIFIED_BIBLIOGRAPHIC_RECORDS: dict[str, dict[str, str]] = {
    "low_rank_adaptation": {
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen",
        "year": "2021",
        "venue": "ICLR 2022 / arXiv:2106.09685",
        "doc_id": "papers/Hu2021_LoRA.pdf",
        "summary": "Freezes pre-trained model weights and injects trainable rank decomposition matrices into Transformer attention layers, reducing trainable parameters by up to 10,000x without adding inference latency.",
    },
    "transformer": {
        "title": "Attention Is All You Need",
        "authors": "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin",
        "year": "2017",
        "venue": "NeurIPS 2017 / arXiv:1706.03762",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "summary": "Introduces the Transformer sequence transduction architecture based entirely on multi-headed self-attention mechanisms, dispensing with recurrence and convolutions.",
    },
    "bert": {
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "authors": "Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova",
        "year": "2018",
        "venue": "NAACL 2019 / arXiv:1810.04805",
        "doc_id": "papers/Devlin2018_BERT.pdf",
        "summary": "Introduces deep bidirectional Transformer representations pretrained jointly on Masked Language Modeling (MLM) and Next Sentence Prediction (NSP).",
    },
    "rag": {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "authors": "Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela",
        "year": "2020",
        "venue": "NeurIPS 2020 / arXiv:2005.11401",
        "doc_id": "papers/Lewis2020_RAG.pdf",
        "summary": "Combines pre-trained parametric neural sequence-to-sequence generators with non-parametric dense vector retrieval over Wikipedia, updating retrieval outputs per token or sequence.",
    },
    "graph_rag": {
        "title": "From Local to Global: A Graph RAG Approach to Query-Focused Summarization",
        "authors": "Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt, Jonathan Larson",
        "year": "2024",
        "venue": "arXiv:2404.16130 (Microsoft Research)",
        "doc_id": "papers/Edge2024_GraphRAG.pdf",
        "summary": "Combines knowledge graph extraction, hierarchical community detection (Leiden), and recursive community summarization to enable global dataset-wide reasoning in retrieval-augmented generation.",
    },
    "qlora": {
        "title": "QLoRA: Efficient Finetuning of Quantized LLMs",
        "authors": "Tim Dettmers, Artidoro Pagnoni, Ari Holtzman, Luke Zettlemoyer",
        "year": "2023",
        "venue": "NeurIPS 2023 / arXiv:2305.14314",
        "doc_id": "papers/Dettmers2023_QLoRA.pdf",
        "summary": "Enables 33B/65B parameter model fine-tuning on a single 48GB GPU by introducing 4-bit NormalFloat (NF4), Double Quantization (DQ), and Paged Optimizers without performance degradation.",
    },
}


def paper_lookup_reply(engine, query: str, cid: str | None = None) -> tuple[str, dict]:
    """Provide crisp bibliographic answers for paper lookup queries without displaying a learning graph."""
    graph = engine.graph
    target_cid = cid
    if not target_cid:
        hits = graph.phrase_hits(query)
        target_cid = hits[0] if hits else None
    if not target_cid:
        ranked = graph.rank(query, top_k=1)
        target_cid = ranked[0][1] if ranked and ranked[0][0] >= KILL_SWITCH else None

    # Check catalog if no concept node found
    if not target_cid:
        catalog_hit = engine.catalog.reply(query)
        if catalog_hit:
            return catalog_hit["text"], catalog_hit["citation"]

    if not target_cid or target_cid not in graph.nodes:
        return (
            "I could not identify a specific indexed paper matching that bibliographic query. "
            "Please specify the title, authors, or primary concept (e.g. LoRA, BERT, Transformers).",
            {},
        )

    label = graph.label(target_cid)

    # Use authoritative bibliographic record if catalogued
    if target_cid in VERIFIED_BIBLIOGRAPHIC_RECORDS:
        rec = VERIFIED_BIBLIOGRAPHIC_RECORDS[target_cid]
        lines = [
            f"**Paper Identification: {label}**",
            "",
            f"• **Title:** *{rec['title']}*",
            f"• **Authors:** {rec['authors']} ({rec['year']})",
            f"• **Venue / Citation:** {rec['venue']}",
            f"• **Repository Document:** `{rec['doc_id']}`",
            "",
            f"**Core Scientific Contribution:**\n> {rec['summary']}",
        ]
        cite_record = {
            "source_category": "paper",
            "doc_id": rec["doc_id"],
            "title": rec["title"],
            "authors": rec["authors"],
            "year": rec["year"],
            "venue": rec["venue"],
            "verified": True,
        }
        return "\n".join(lines), cite_record

    node = graph.nodes[target_cid]
    sources = node.get("sources") or []
    paper_sources = [
        s
        for s in sources
        if str(s.get("source_category", "")).lower() == "paper"
        or "papers/" in str(s.get("doc_id", ""))
    ]
    best_src = paper_sources[0] if paper_sources else (sources[0] if sources else {})

    doc_id = str(best_src.get("doc_id") or "")
    doc_stem = doc_id.split("/")[-1].replace(".pdf", "").replace("_", " ")

    author_match = re.search(r"([A-Z][a-z]+)(\d{4})", doc_id)
    if author_match:
        authors = f"{author_match.group(1)} et al. ({author_match.group(2)})"
    else:
        authors = "Identified in corpus records"

    passage = str(best_src.get("text_passage") or node.get("summary") or "").strip()
    doi_match = re.search(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b", passage)
    arxiv_match = re.search(r"\barXiv:\s*(\d{4}\.\d{4,5})\b", passage, re.I)

    lines = [
        f"**Paper Identification: {label}**",
        "",
        f"• **Core Title / Work:** {doc_stem.title() if doc_stem else label}",
        f"• **Authors / Date:** {authors}",
    ]
    if doi_match:
        lines.append(f"• **DOI:** https://doi.org/{doi_match.group(1)}")
    elif arxiv_match:
        lines.append(f"• **arXiv:** https://arxiv.org/abs/{arxiv_match.group(1)}")

    page = best_src.get("page_number")
    if page:
        lines.append(f"• **Repository Document:** `{doc_id}` (page {page})")
    elif doc_id:
        lines.append(f"• **Repository Document:** `{doc_id}`")

    summary_text = node.get("summary") or ""
    if summary_text:
        lines.extend(["", f"**Core Concept Summary:**\n> {summary_text}"])

    cite_record = graph.cite_record(target_cid, query)
    return "\n".join(lines), cite_record


def library_inventory_reply(engine, query: str) -> str:
    """Show catalog metadata while withholding unverified stock claims."""

    records = catalogue.load_catalogue()
    topic = query.casefold()
    keywords = {
        "operating systems": ("operating system", "ostep"),
        "database": ("database", "dbms"),
        "algorithms": ("algorithm", "data structure"),
    }
    selected = next(
        (
            terms
            for label, terms in keywords.items()
            if label in topic or any(term in topic for term in terms)
        ),
        (),
    )
    if "journal" in topic:
        return (
            "Journal inventory is not verified in the hosted catalog. "
            "Search the [campus OPAC](https://uemk-opac.l2c2.co.in/) for current records."
        )
    matched = [
        record
        for record in records
        if not selected
        or any(term in str(record.get("title") or "").casefold() for term in selected)
    ]
    if not matched:
        return (
            "Not verified in the catalog. "
            "Search the [campus OPAC](https://uemk-opac.l2c2.co.in/) for a matching title."
        )
    lines = [
        "**Library catalog records**",
        "",
        "| Title | Author | Edition / ISBN | Call number | Copies | Available | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in matched[:8]:

        def cell(value: object) -> str:
            return str(value or "—").replace("|", "/")

        link = str(record.get("reader_base_url") or "")
        source = (
            f"[Pearson reader]({link})"
            if link.startswith("https://")
            else "[Search OPAC](https://uemk-opac.l2c2.co.in/)"
        )
        lines.append(
            f"| {cell(record.get('title'))} | {cell(record.get('author'))} | "
            f"{cell(record.get('isbn'))} | — | — | — | {source} |"
        )
    lines.extend(["", "Stock and shelf locations are not verified in the hosted catalog."])
    return "\n".join(lines)
