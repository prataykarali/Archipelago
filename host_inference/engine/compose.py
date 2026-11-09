"""Grounded reply composition for the hosted librarian engine.

One concern: turning graph facts into the specific prose protocols
(synthesis, relation chain, comparative matrix, shelf card, auth card).
"""

from __future__ import annotations

import re

from .constants import KILL_SWITCH, PORTALS, SCHEDULE, SHELF
from .multi_hop import VERIFIED_CONCEPT_FOUNDATIONS
from .render import arrow, lineage, neighborhood_block

# Comparative matrix cells are trimmed to keep the table readable.
MATRIX_CELL_CHARS = 180


def domain_pair(engine, query: str):
    """Recognised B+ tree / vector-RAG comparison pair, or ``None``."""
    q = query.lower()
    left = right = None
    if re.search(r"\bb\+\s*tree\b|\bb-tree\b|\bdbms\b|\brelational\b", q):
        left = ("third_normal_form", "Relational B+ tree / DBMS")
    if re.search(r"\bhnsw\b|\bvector search\b|\brag\b", q):
        right = ("rag", "HNSW / vector RAG")
    graph = engine.graph
    if left and right and left[0] in graph.nodes and right[0] in graph.nodes:
        return left, right
    return None


def split_pair(query: str):
    """Split an ``X and Y`` relationship query into its two fragments."""
    clean_q = re.sub(r"\s*\([Ee]arlier user topics?:.*?\)", "", query or "").strip()
    patterns = (
        r"how (?:does|do|are|is)\s+(.+?)\s+(?:connect|relate|connected|related)\s+(?:to|with)\s+(.+)",
        r"how (?:are|is|do)\s+(.+?)\s+and\s+(.+?)\s+(?:connected|related)",
        r"relation(?:ship)? between\s+(.+?)\s+and\s+(.+)",
        r"compare\s+(.+?)\s+(?:with|and|to|versus|vs\.?)\s+(.+)",
        r"difference between\s+(.+?)\s+and\s+(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, clean_q, re.I)
        if match:
            g1, g2 = match.group(1).strip(), match.group(2).strip()
            # If the second fragment has multiple coordinated items, do not treat as a simple pair
            if re.search(r"\b(and|with|versus|vs\.?)\b|,", g2, re.I):
                return None
            return g1, g2
    return None


def resolve_fragment(engine, fragment: str) -> tuple[str | None, bool]:
    """Resolve a query fragment to a known concept id (phrase hit, else cosine)."""
    hits = engine.graph.phrase_hits(fragment)
    if hits:
        return hits[0], True
    ranked = engine.graph.rank(fragment, top_k=1)
    if ranked and ranked[0][0] >= KILL_SWITCH:
        return ranked[0][1], True
    return None, False


def synthesis(engine, cid: str) -> str:
    """Put the answer first and show only relevant verified follow-on detail."""
    graph = engine.graph
    node = graph.nodes[cid]
    foundation = VERIFIED_CONCEPT_FOUNDATIONS.get(cid)
    if foundation:
        summary = foundation
    else:
        summary = (node.get("summary") or "Indexed catalog concept.").strip()
    cite = graph.citation(cid)
    formula = graph.formula(cid)
    query = str(getattr(graph, "_query", ""))
    lines = [f"**{graph.label(cid)}.** {summary} {cite}".strip()]
    if formula and re.search(r"\b(equation|formula|math|derive|how|explain)\b", query, re.I):
        lines.extend(["", "**How it works.**", formula])
    if re.search(r"\b(prerequisite|learning path|roadmap|before|after|connect)\b", query, re.I):
        lines.extend(["", "**Verified learning path.**", lineage(graph, cid)])
    link = engine.pearson_line(cid)
    if link:
        lines.extend(["", link])
    return "\n".join(lines)


def relation(engine, a: str, b: str, path: list[tuple[str, str]]) -> str:
    """Render the dependency chain connecting two concepts."""
    graph = engine.graph
    rendered = []
    cursor = a
    for kind, nxt in path:
        rel = "UNLOCKS" if "UNLOCKS" in kind else "REQUIRES"
        rendered.append(arrow(graph.label(cursor), rel, graph.label(nxt)))
        cursor = nxt
    hops = len(path)
    kind = "a direct dependency" if hops == 1 else f"a {hops}-hop structural bridge"
    lines = [
        f"**{graph.label(a)}** and **{graph.label(b)}** share {kind} in the catalog graph.",
        "",
        "**Traversal chain.** " + " ".join(rendered),
        "",
        f"**Document evidence.** {graph.citation(a, 1)} {graph.citation(b, 2)}",
    ]
    return "\n".join(lines)


def matrix(
    engine, a: str, b: str, left_name: str | None = None, right_name: str | None = None
) -> str:
    """Render the comparative matrix for two concepts."""
    graph = engine.graph
    left = left_name or graph.label(a)
    right = right_name or graph.label(b)

    def cell(cid: str) -> str:
        return (graph.nodes[cid].get("summary") or graph.label(cid)).strip()[:MATRIX_CELL_CHARS]

    if left_name and "B+" in left_name:
        data_l = "Ordered keys in leaf-linked pages of a B+ tree."
        data_r = "High-dimensional embedding vectors in an HNSW graph."
        search_l = "Exact descent from root to leaf, then a sequential sibling scan."
        search_r = "Greedy beam search over layered navigable small-world links."
        io_l = "Few sequential page reads once the leaf is reached."
        io_r = "Random hops through the vector index; more irregular I/O."
        recall_l = "Exact for the indexed key range."
        recall_r = "Approximate; recall depends on the beam and the graph degree."
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    else:
        data_l, data_r = cell(a), cell(b)
        search_l = search_r = "Retrieved from the indexed concept summary only."
        io_l = io_r = "Textbook pages cited below."
        recall_l = recall_r = "Limited to indexed chunks; no unstated guarantee."
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    lines = [
        f"**Comparative matrix: {left} × {right}**",  # noqa: RUF001
        "",
        "| Axis | " + left + " | " + right + " |",
        "| --- | --- | --- |",
        f"| Data representation | {data_l} | {data_r} |",
        f"| Search mechanics | {search_l} | {search_r} |",
        f"| Disk I/O | {io_l} | {io_r} |",
        f"| Recall | {recall_l} | {recall_r} |",
        "",
        cites,
    ]
    return "\n".join(lines)


def disconnected(engine, a: str, b: str) -> str:
    """Render the honest 'no indexed dependency connects these' reply."""
    graph = engine.graph
    return (
        f"**{graph.label(a)}** and **{graph.label(b)}** are both indexed catalog nodes. "
        "No pedagogical prerequisite or structural dependency connects them within this corpus.\n\n"
        "Independent neighborhoods:\n"
        f"{neighborhood_block(graph, a)}\n"
        f"{neighborhood_block(graph, b)}"
    )


def shelf(engine, cid: str) -> str:
    """Render the indexed physical shelf card for ``cid``."""
    graph = engine.graph
    card = SHELF[cid]
    cite = graph.citation(cid)
    return "\n".join(
        [
            f"**{graph.label(cid)}.** {card['definition']} {cite}",
            "",
            f"**Title & author.** {card['title']}, {card['author']}.",
            f"**Call number.** {card['call_number']}.",
            f"**Shelf.** {card['place']}.",
            f"**System barcode.** {card['barcode']}.",
            f"**Live availability.** {card['available']} physical copies currently on shelf (out of {card['total']} total).",
        ]
    )


def shelf_generic(engine, cid: str) -> str:
    """Render the honest 'no physical shelf card indexed' reply."""
    graph = engine.graph
    return (
        f"**{graph.label(cid)}.** {(graph.nodes[cid].get('summary') or '').strip()} {graph.citation(cid)}\n\n"
        "No separate physical shelf card is indexed for this concept. "
        "Ask at the Central Library circulation desk and search the OPAC at http://uemk-opac.l2c2.co.in."
    )


def auth_card(query: str) -> str:
    """Render sign-in links without exposing shared institutional credentials."""
    del query
    return "\n".join(
        [
            "[RENDER_AUTH_CARD]",
            "### Central Library E-Resource Access",
            "",
            "Open the institutional portal and sign in with your own campus account. "
            "This assistant does not store or reveal shared passwords.",
            "",
            "| Portal | Sign-in page |",
            "| :--- | :--- |",
            "| Pearson eLibrary | [Open Pearson](https://elibrary.in.pearson.com/) |",
            "| IEEE Xplore | [Open IEEE Xplore](https://ieeexplore.ieee.org) |",
            "| Scopus and ScienceDirect | [Open ScienceDirect](https://www.sciencedirect.com) |",
            "| SpringerLink | [Open SpringerLink](https://link.springer.com) |",
            "| National Digital Library of India | [Open NDLI](https://ndl.iitkgp.ac.in/) |",
            "| OPAC Catalogue | [Open OPAC](https://uemk-opac.l2c2.co.in) |",
        ]
    )


def admin_card(query: str, wants_hours: bool, wants_access: bool) -> str:
    """Contract type 3: the schedule and the access portals in one card.

    Students ask both halves in a single sentence ("how do I access IEEE
    off-campus, and what are library Sunday hours?").  Routing that to *either*
    the schedule sheet or the portal list silently drops half the question, and
    dropping the schedule half loses the one fact the student cannot look up.
    So: render whichever halves were actually asked for, and never a graph.
    """
    q = query.lower()
    if wants_hours and wants_access:
        lines = [
            "[RENDER_AUTH_CARD]",
            "**Institutional access.** Sign in with your own campus account. This assistant does not store or reveal passwords.",
            "",
            "**Central Library schedule**",
            "",
            *SCHEDULE,
            "",
            *[_portal_row(line) for line in _portal_lines(q)],
            "",
            "If a title is paywalled outside these portals, borrow a reciprocal membership card "
            "(British Council Library or American Library) from the Central Library front desk.",
        ]
        return "\n".join(lines)
    if wants_hours:
        lines = ["**Central Library schedule**", "", *SCHEDULE, ""]
        lines.append("Source: Central Library Academic Schedule.")
        return "\n".join(lines)
    return auth_card(query)


def _portal_rows(query: str) -> list[str]:
    """Portal bullet lines for the databases named in ``query``."""
    return [_portal_row(line) for line in _portal_lines(query)]


def _portal_row(line: str) -> str:
    """Prefix a portal description with the bullet the chat UI expects."""
    return line if line.startswith("- ") else f"- {line}"


def _portal_lines(query: str) -> list[str]:
    """The portal descriptions matching ``query``, defaulting to the core four."""
    q = query.lower()
    chosen = [row for row in PORTALS if row[0].split()[0].lower() in q or row[0].lower() in q]
    if not chosen:
        chosen = PORTALS[:4]
    return [f"**{name}.** {url} — {how}." for name, url, how in chosen]


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
        s for s in sources if str(s.get("source_category", "")).lower() == "paper" or "papers/" in str(s.get("doc_id", ""))
    ]
    best_src = paper_sources[0] if paper_sources else (sources[0] if sources else {})

    doc_id = str(best_src.get("doc_id") or "")
    doc_stem = doc_id.split("/")[-1].replace(".pdf", "").replace("_", " ")

    year_match = re.search(r"\b(19\d\d|20\d\d)\b", doc_id)
    year = year_match.group(1) if year_match else "Verified publication"

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
    """Provide concise institutional holdings and journal inventory without an interactive graph."""
    lines = [
        "**Institutional Library & Journal Inventory**",
        "",
        "The Central Library catalog provides access to print reserve texts, licensed electronic resources, and departmental reference collections:",
        "",
        "**Monograph & Course Reserve Catalog:**",
        "• *Database System Concepts* — Silberschatz, Korth, Sudarshan (Physical reserve & Pearson eLibrary)",
        "• *Operating System Concepts* — Silberschatz, Galvin, Gagne (Physical circulation & Digital reserve)",
        "• *Artificial Intelligence: A Modern Approach* — Russell & Norvig (Physical reference)",
        "• *Deep Learning* — Goodfellow, Bengio, Courville (Digital open access & Campus library stack)",
        "• *Speech and Language Processing* — Jurafsky & Martin (Draft 3rd ed. digital repository)",
        "",
        "**Electronic Journal & Database Subscriptions:**",
        "• IEEE Xplore Digital Library (full-text conference & journal access via campus IP/EZProxy)",
        "• ScienceDirect & Scopus (institutional subscription for Elsevier computer science journals)",
        "• SpringerLink (Springer lecture notes in computer science LNCS)",
        "",
        "For real-time shelf availability, accession numbers, or loan renewals, consult the OPAC terminal (http://uemk-opac.l2c2.co.in) or visit the circulation desk during operating hours (Mon–Sat 9:00 AM – 8:00 PM).",
    ]
    return "\n".join(lines)

