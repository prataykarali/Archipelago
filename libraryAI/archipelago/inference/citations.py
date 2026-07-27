
."""Citation map, payloads, validation, and narrative recipe."""
from __future__ import annotations

import itertools

from archipelago.inference import state as st
from urllib.parse import quote

from archipelago.inference.aliases import (
    _node_name, pdf_page_url, markdown_pdf_link, page_view_markdown_link,
)
from archipelago.inference.neighborhood import get_concept_citations
from archipelago.inference.graph_access import _default_graph_db

def compile_narrative_recipe(query, target_concept, prereqs, unlocks, citations):
    target_name = target_concept.get("label", target_concept.get("name", ""))
    target_summary = target_concept.get("summary", "")
    
    prereqs_str = "\n".join([f"   - {p['name']}: {p['summary']}" for p in prereqs]) if prereqs else "   - None extracted"
    unlocks_str = ", ".join([u['name'] for u in unlocks]) if unlocks else "None extracted"
    
    citations_str = ""
    if citations:
        for i, c in enumerate(citations, 1):
            passage = c.get('text_passage') or ""
            passage = str(passage).strip()
            citations_str += (
                f"Citation {i}:\n"
                f"- Document: {c['doc_id']} (Page: {c['page_number']}, Section: {c['section_title']})\n"
                f"- Text Passage: \"{passage}\"\n\n"
            )
    else:
        citations_str = "No specific source citations found in the database.\n"
        
    recipe = (
        f"USER QUERY:\n"
        f"{query}\n\n"
        f"STRUCTURED TOPOLOGY (Narrative Recipe):\n"
        f"1. Upstream Prerequisites:\n"
        f"{prereqs_str}\n\n"
        f"2. Target Concept:\n"
        f"   - {target_name}: {target_summary}\n\n"
        f"3. Downstream Applications (Unlocks):\n"
        f"   - {unlocks_str}\n\n"
        f"TEXTUAL CITATIONS:\n"
        f"{citations_str}"
        f"INSTRUCTION:\n"
        f"You are the Generator model for the Archipelago knowledge system. Synthesize the user query, structured topology (Prerequisite -> Target -> Unlock), and textual citations into a coherent, fluid, and natural explanation. Do NOT output a JSON list of concepts. Instead, write a conversational and academic response explaining the relationship, using direct references to the concepts and citations above."
    )
    return recipe


def _resolve_printed_page(evidence):
    """Reverse-map a physical PDF page to its printed label, if a map exists.

    ``page_label_map`` maps printed labels to physical (1-based) PDF pages;
    return the label whose page matches, or None when no map exists or the
    page does not resolve.  We never guess a printed page.
    """
    label_map = evidence.get("page_label_map")
    page_number = evidence.get("page_number")
    if not isinstance(label_map, dict) or not isinstance(page_number, int):
        return None
    for label, pdf_page in label_map.items():
        try:
            if int(pdf_page) == page_number:
                return str(label)
        except (TypeError, ValueError):
            continue
    return None


def _page_display(evidence):
    """Render 'p. <printed>' only when a label map resolves; else 'PDF page <n>'."""
    printed = _resolve_printed_page(evidence)
    if printed is not None:
        return f"p. {printed}"
    page = evidence.get("page_number")
    if isinstance(page, int) and page > 0:
        return f"PDF page {page}"
    return ""


def _citation_label(topic_name, evidence_list):
    """Format only provenance we actually retrieved; never invent a page."""
    if not evidence_list:
        return ""
    evidence = evidence_list[0]
    evidence_id = evidence.get("evidence_id") or "S?"
    document = evidence.get("doc_id") or "Unknown document"
    page_display = _page_display(evidence)
    page_suffix = f", {page_display}" if page_display else ""
    return f" [{evidence_id}: {topic_name} | {document}{page_suffix}]"


def _normalize_legacy_citation(citation):
    """Lift a legacy get_concept_citations record into the evidence contract."""
    return {
        "chunk_id": None,
        "doc_id": citation.get("doc_id"),
        "page_number": citation.get("page_number"),
        "section_title": citation.get("section_title"),
        "text": citation.get("text_passage"),
        "text_offset_start": None,
        "text_offset_end": None,
        "block_bbox": None,
        "doc_title": None,
        "page_label_map": None,
    }


def _evidence_for_concept(graph_db, concept_id, concept_name):
    """Fetch evidence for one concept, falling back to the legacy Kuzu lookup."""
    if graph_db is not None:
        try:
            evidence = graph_db.get_evidence_for_concept(concept_name)
            if evidence:
                return evidence
        except Exception as e:
            print(f"Evidence retrieval error for concept '{concept_name}': {e}")
    return [_normalize_legacy_citation(c) for c in get_concept_citations(concept_id, limit=1)]


def _evidence_for_prerequisite(graph_db, prereq_name, target_name):
    """Fetch edge-level evidence for a prerequisite relation, if indexed.

    REQUIRES edges are stored target -> prerequisite (see get_graph_neighborhood),
    but the evidence API's source/target orientation is the edge author's call,
    so both orders are tried before giving up.
    """
    if graph_db is None:
        return None
    for source, target in ((target_name, prereq_name), (prereq_name, target_name)):
        try:
            evidence = graph_db.get_evidence_for_edge(source, target)
        except Exception as e:
            print(f"Evidence retrieval error for edge {source} -> {target}: {e}")
            return None
        if evidence:
            # Accept either a single evidence dict or a list of them.
            return [evidence] if isinstance(evidence, dict) else evidence
    return None


def build_concept_citation_map(target_concept, prereqs, unlocks, graph_db=None):
    """Return evidence keyed by concept id for all displayed roadmap steps.

    Evidence IDs (``S1``, ``S2``, ...) come from a single counter assigned in
    render order — prerequisites, then the target, then unlocks — so the IDs
    in the rendered text, the model contract, and the structured payloads all
    agree.  Prerequisite steps prefer edge-level evidence (the passage that
    grounds the REQUIRES relation itself) and fall back to concept-level
    evidence.  ``graph_db`` may be injected (e.g. a mock) for tests; it
    defaults to okf.graph_db, with the legacy Kuzu lookup as a last resort.
    """
    if graph_db is None:
        graph_db = _default_graph_db()
    
    # Accept both dict (with "id" key) and string (concept_id) for target_concept
    if isinstance(target_concept, str):
        target_id = target_concept
        target_name = target_concept
    else:
        target_id = target_concept.get("id", "")
        target_name = _node_name(target_concept)
    
    counter = itertools.count(1)
    citation_map = {}

    def assign(concept_id, evidence_list):
        tagged = []
        for evidence in (evidence_list or [])[:st.EVIDENCE_PER_CONCEPT]:
            entry = dict(evidence)
            entry["evidence_id"] = f"S{next(counter)}"
            tagged.append(entry)
        citation_map[concept_id] = tagged

    for item in prereqs[:st.MAX_PREREQS_SHOWN]:
        concept_id = item.get("id")
        if not concept_id or concept_id in citation_map:
            continue
        name = _node_name(item)
        evidence = _evidence_for_prerequisite(graph_db, name, target_name)
        if not evidence:
            evidence = _evidence_for_concept(graph_db, concept_id, name)
        assign(concept_id, evidence)

    if target_id not in citation_map:
        assign(target_id, _evidence_for_concept(graph_db, target_id, target_name))

    for item in unlocks[:st.MAX_UNLOCKS_SHOWN]:
        concept_id = item.get("id")
        if not concept_id or concept_id in citation_map:
            continue
        assign(concept_id, _evidence_for_concept(graph_db, concept_id, _node_name(item)))

    return citation_map


def validate_citations(model_output, evidence_ids):
    """Check that model output cites only supplied evidence IDs.

    Returns a ``(is_valid, offending_ids)`` tuple: ``is_valid`` is True when
    every ``[S<n>:`` citation bracket found in ``model_output`` names an ID
    from ``evidence_ids``; ``offending_ids`` lists the hallucinated IDs in
    numeric order (empty when valid).
    """
    supplied = set(evidence_ids or [])
    found = set(st.CITATION_ID_PATTERN.findall(model_output or ""))
    offending = sorted(found - supplied, key=lambda eid: int(eid[1:]))
    return (not offending, offending)


def citation_payload(evidence, topic, evidence_id=None):
    """Build one structured citation metadata dict for the response JSON.

    ``page_number`` is the physical (1-based) PDF page; ``printed_page`` is
    the document's printed label resolved via ``page_label_map`` (None when
    no map exists or the page does not resolve).  ``text_span`` is the exact
    supporting text: the offset-sliced span when the offsets index into the
    chunk text, otherwise the full chunk text.
    """
    if evidence_id is None:
        evidence_id = evidence.get("evidence_id")
    doc_id = evidence.get("doc_id") or ""
    page_number = evidence.get("page_number")
    # Prefer the page-view endpoint (encoded) so the chat modal can open
    # passages even when the PDF filename contains spaces/colons.
    page_param = page_number if isinstance(page_number, int) and page_number > 0 else 1
    url = (
        f"{st.PDF_BASE_URL}/api/page-view"
        f"?doc_id={quote(str(doc_id), safe='')}"
        f"&page={page_param}"
        f"&highlight={quote(str(topic or ''), safe='')}"
        f"#page={page_param}"
    )
    text = evidence.get("text") or ""
    start = evidence.get("text_offset_start")
    end = evidence.get("text_offset_end")
    text_span = text
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
        text_span = text[start:end]
    return {
        "evidence_id": evidence_id,
        "topic": topic,
        "doc_id": doc_id,
        "page_number": page_number,
        "printed_page": _resolve_printed_page(evidence),
        "section_title": evidence.get("section_title") or "",
        "url": url,
        "text_span": text_span,
    }


def build_citation_payloads(target_concept, prereqs, unlocks, citation_map):
    """Flatten the citation map into payload dicts in evidence-ID order."""
    topics = {target_concept.get("id", ""): _node_name(target_concept)}
    for item in list(prereqs) + list(unlocks):
        topics.setdefault(item.get("id"), _node_name(item))
    payloads = []
    for concept_id, evidence_list in citation_map.items():
        for evidence in evidence_list:
            payloads.append(citation_payload(evidence, topics.get(concept_id, "")))
    return payloads


def build_library_source_payloads(books, topic, seeds=None):
    """Return clickable source records for a book-recommendation response.

    Book search is an index result rather than a claim about a particular
    passage, so it cannot use :func:`citation_payload` (which represents exact
    chunk evidence).  The chat protocol nevertheless needs a stable source
    contract: every openable recommendation has an ID, a page-view URL, and a
    clearly labelled ``source_type``.  This lets the client render the same
    clickable source cards for recommendations and concept answers without
    pretending that catalogue ranking is a passage citation.

    Seed titles are included **only** when ``doc_id_hint`` resolves to a local
    PDF (openable).  Pure metadata seeds stay out of the evidence rail.
    """
    records = []
    seen_docs = set()

    def _pdf_ok(doc_id: str) -> bool:
        if not doc_id:
            return False
        # Graph-backed ids are always eligible; seed hints need a local file.
        try:
            from archipelago.inference.routes_misc import resolve_pdf_file
            return resolve_pdf_file(doc_id) is not None
        except Exception:
            return True  # fail open for graph docs already in ``books``

    def add(record, *, title="", reason="", source_type="indexed_document", require_file=False):
        doc_id = str(
            (record or {}).get("id")
            or (record or {}).get("doc_id_hint")
            or (record or {}).get("doc_id")
            or ""
        ).strip()
        if not doc_id or doc_id in seen_docs:
            return
        if require_file and not _pdf_ok(doc_id):
            return
        seen_docs.add(doc_id)
        page = (record or {}).get("page_number")
        page = page if isinstance(page, int) and page > 0 else 1
        evidence_id = f"S{len(records) + 1}"
        url = (
            f"{st.PDF_BASE_URL}/api/page-view"
            f"?doc_id={quote(doc_id, safe='')}&page={page}"
            f"&highlight={quote(str(topic or title)[:120], safe='')}#page={page}"
        )
        records.append({
            "evidence_id": evidence_id,
            "topic": topic or title,
            "doc_id": doc_id,
            "doc_title": title or (record or {}).get("title") or doc_id,
            "page_number": page,
            "printed_page": None,
            "section_title": "Catalog recommendation",
            "url": url,
            "text_span": reason or (record or {}).get("rank_reason") or "",
            "source_type": source_type,
        })

    for book in books or []:
        add(
            book,
            title=book.get("title") or book.get("id") or "",
            reason=(
                f"Matched concepts: {', '.join(book.get('matched') or [])}."
                if book.get("matched") else "Indexed corpus recommendation."
            ),
        )
    for seed in seeds or []:
        add(
            seed,
            title=seed.get("title") or seed.get("doc_id_hint") or "",
            reason=seed.get("rank_reason") or "Librarian seed with local PDF.",
            source_type="seed_local_pdf",
            require_file=True,
        )
    return records


# How many distinct (doc, page) links one concept contributes to a rendered
# line.  The graph stores up to EVIDENCE_PER_CONCEPT chunks per concept but the
# renderer used to emit only evidence[0], which capped every deterministic
# answer at one page link per concept.
_LINKS_PER_CONCEPT = 15  # show more page links per concept in the answer body

# How many bare [S#] IDs per concept appear in the generator's notes.  Keep it
# small: every marker costs prompt tokens on a CPU-bound 0.5B model.
# Increased from 2→4 so the model has more citation IDs to choose from,
# resulting in more page links in the final answer.
_MARKERS_PER_CONCEPT_IN_NOTES = 6  # give the model more citation IDs to choose from


def _evidence_page_key(evidence):
    """Identity of one citation target: the (document, page) pair it opens."""
    page = evidence.get("page_number")
    return (str(evidence.get("doc_id") or ""), page if isinstance(page, int) else 0)


def _cite_with_link(name, evidence_list):
    """Citation bracket plus page-view markdown links for chat bubbles.

    Uses the encoded ``/api/page-view`` URL (not a raw ``/pdfs/…`` path) so
    filenames with spaces never truncate in markdown and the in-app modal
    receives the full ``doc_id`` + page + highlight + section title.  Emits up
    to ``_LINKS_PER_CONCEPT`` links, one per distinct (doc, page), so a concept
    backed by several indexed pages surfaces more than one of them.
    """
    base = _citation_label(name, evidence_list)
    if not evidence_list:
        return base
    links = []
    seen_pages = set()
    for ev in evidence_list:
        doc_id = ev.get("doc_id")
        if not doc_id:
            continue
        key = _evidence_page_key(ev)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        page = ev.get("page_number")
        section = (ev.get("section_title") or "").strip()
        # Build a descriptive label: prefer section title, fall back to page display
        page_disp = _page_display(ev) or "source"
        link_label = section if section else page_disp
        links.append(page_view_markdown_link(
            link_label,
            doc_id,
            page if isinstance(page, int) else None,
            highlight=name,
            section=section,
        ))
        if len(links) >= _LINKS_PER_CONCEPT:
            break
    if not links:
        return base
    return f"{base} ({', '.join(links)})"


def _citation_marker(evidence_list, bare_markers=False):
    """Bare ' [S#] [S#]' markers for the generator contract (expanded post-hoc).

    build_concept_citation_map assigns up to ``EVIDENCE_PER_CONCEPT`` IDs per
    concept, but the notes used to advertise only the first one.  The model then
    saw a sparse, non-contiguous set (S1, S5, S9, ...) while the prompt told it
    to cite "[S1]..[S6]", so it guessed IDs that belonged to other concepts.
    Surfacing ``_MARKERS_PER_CONCEPT_IN_NOTES`` IDs per concept gives the model
    real, adjacent IDs to cite without pasting the whole evidence table.
    """
    if not bare_markers or not evidence_list:
        return ""
    ids = [
        evidence.get("evidence_id")
        for evidence in evidence_list[:_MARKERS_PER_CONCEPT_IN_NOTES]
        if evidence.get("evidence_id")
    ]
    return "".join(f" [{eid}]" for eid in ids)


def render_citation_from_payload(payload):
    """Format one evidence payload as a single clean page-view Markdown link.

    Pipeline contract: the LLM only emits bare ``[S1]`` markers; this Python
    filter expands them into clickable PDF page links. One link only — never
    a long ``[S1: topic | doc…]`` label plus a second link (that doubled chips
    in the chat bubble).
    """
    topic = (payload.get("topic") or "Concept").strip() or "Concept"
    doc_id = payload.get("doc_id") or ""
    printed = payload.get("printed_page")
    page_number = payload.get("page_number")
    if printed is not None:
        page_disp = f"p.{printed}"
        page_num = int(printed) if str(printed).isdigit() else (page_number or 1)
    elif isinstance(page_number, int) and page_number > 0:
        page_disp = f"p.{page_number}"
        page_num = page_number
    else:
        page_disp = "source"
        page_num = 1
    if not doc_id:
        return f"({page_disp})"
    # Short chip label: (p.12 ↗) — UI styles curriculum-pdf-link chips.
    link_label = f"{page_disp} ↗"
    return page_view_markdown_link(link_label, doc_id, page_num, highlight=topic)


_MARKER_WITH_TAIL_RE = None  # compiled lazily in cleanse_model_citations


# Max inline citations shown in the bubble (side panel holds the full set).
# Set to a generous cap — the actual count is bounded by the real payloads
# available from the graph (EVIDENCE_PER_CONCEPT × concepts shown).
# Show several page chips inline (prereq + target + unlocks), not just 1–2.
# Increased from 20→40 to ensure enough page links appear in the answer body.
_MAX_INLINE_CITATIONS = 50  # allow more inline citations in the answer body

# Chips appended to a single paragraph by the fallback inserter.  Spreads links
# across the answer instead of stacking every page of one concept on one line.
# Increased from 8→12 to allow more citations per paragraph without flooding.
_MAX_LINKS_PER_PARAGRAPH = 16  # spread more links across paragraphs

# Shortest topic word that may anchor a citation.  Below this, matches are noise.
_MIN_TOPIC_WORD_CHARS = 3  # reduce false negatives in topic matching

# Words a topic needs before its initials count as a mention.  Two-letter
# acronyms collide far too often to be evidence that a concept is discussed.
_MIN_WORDS_FOR_ACRONYM = 3

# Trailing bibliography / source-dump blocks the model sometimes still emits.
_SOURCE_DUMP_RE = None  # compiled lazily


def _strip_source_dump_footer(text: str) -> str:
    """Remove trailing Sources/References dumps without touching inline [S#]."""
    import re as _re
    global _SOURCE_DUMP_RE
    if _SOURCE_DUMP_RE is None:
        # Handles: Sources: / **Sources:** / ## References / Works Cited etc.
        _SOURCE_DUMP_RE = _re.compile(
            r"\n+(?:#{1,4}\s*)?(?:\*\*|__)?"
            r"(?:Sources?|References?|Works?\s+Cited|Bibliography|Further\s+Reading|"
            r"Source\s+List|Citations?)"
            r"(?:\*\*|__)?"
            r"\s*:?\s*"
            r"(?:\*\*|__)?"
            r"\s*\n[\s\S]*\Z",
            _re.IGNORECASE,
        )
    cleaned = _SOURCE_DUMP_RE.sub("", text or "")
    # Also drop a final bullet list of bare .pdf filenames (literary dump smell).
    cleaned = _re.sub(
        r"\n+(?:[-*•]\s+\S+\.pdf(?:\s*\([^)]*\))?\s*\n?){2,}\s*\Z",
        "",
        cleaned,
        flags=_re.IGNORECASE,
    )
    return cleaned.rstrip()

def cleanse_model_citations(text, citation_payloads):
    """Post-generation provenance pass (the anti-hallucination 'filler').

    The generator is only allowed bare ``[S1]`` markers. This pass:
      1. normalizes any ``[S1: invented stuff]`` back to ``[S1]``;
      2. strips markers whose ID has no real evidence payload;
      3. drops markers whose surrounding paragraph never mentions the concept
         that evidence belongs to (misattached citations);
      4. expands surviving markers into a PDF deep-link rendered from graph
         provenance, one per distinct (doc, page), capped at
         ``_MAX_INLINE_CITATIONS``;
      5. if no inline markers survived, attaches citations to the paragraphs
         that name their concept. It never creates a bibliography/footer.
      6. strips any trailing Sources/References dump the model still emitted.

    Returns the cleansed text. Never invents pages, docs, or IDs: every link is
    rendered from a supplied payload, and every payload must be earned by the
    concept being named in the prose it is attached to.
    """
    import re as _re

    if not text:
        return text
    # Drop literary source dumps BEFORE marker expansion so we don't expand
    # citations that only lived inside a footer the user never wants.
    text = _strip_source_dump_footer(text)
    payloads = [p for p in (citation_payloads or []) if p.get("evidence_id")]
    by_id = {p["evidence_id"]: p for p in payloads}

    # 1. Normalize model-embellished brackets to bare markers.
    text = _re.sub(r"\[\s*(S\d+)\s*:[^\]]*\]", r"[\1]", text)
    # Also collapse comma-run markers like [S1, S2] into [S1] [S2].
    text = _re.sub(
        r"\[\s*(S\d+(?:\s*,\s*S\d+)+)\s*\]",
        lambda m: " ".join(f"[{x.strip()}]" for x in m.group(1).split(",")),
        text,
    )

    def _topic_tokens(topic):
        """Surface forms that prove a block of prose discusses ``topic``."""
        words = [
            w for w in _re.split(r"[^a-z0-9]+", (topic or "").lower())
            if len(w) >= _MIN_TOPIC_WORD_CHARS
        ]
        if not words:
            return []
        tokens = list(words)
        # Multi-word concepts are routinely written as their initials ("RAG"
        # for "Retrieval Augmented Generation"). The acronym is derived from
        # the topic itself, so accepting it adds no ungrounded surface.
        if len(words) >= _MIN_WORDS_FOR_ACRONYM:
            tokens.append("".join(w[0] for w in words))
        return tokens

    def _topic_mentioned(block, topic):
        tokens = _topic_tokens(topic)
        if not tokens:
            return True
        haystack = (block or "").lower()
        return any(
            _re.search(rf"(?<![a-z0-9]){_re.escape(t)}(?![a-z0-9])", haystack)
            for t in tokens
        )

    def _enclosing_block(prefix):
        """Prose block a marker belongs to: the paragraph or list item it ends.

        Checking only the marker's own sentence dropped valid citations whenever
        the claim spanned two sentences ("RAG pairs retrieval with generation.
        It reduces hallucination [S4].").  A paragraph is the unit of a claim in
        these answers, so it is the honest attribution window.
        """
        boundary = max(prefix.rfind("\n\n"), prefix.rfind("\n- "), prefix.rfind("\n* "))
        return prefix[boundary + 1:] if boundary >= 0 else prefix

    marker_hits = list(_re.finditer(r"\[\s*(S\d+)\s*\]", text))
    out = []
    last = 0
    seen_inline = 0
    linked_pages = set()
    for m in marker_hits:
        out.append(text[last:m.start()])
        last = m.end()
        payload = by_id.get(m.group(1))
        if payload is None:
            continue  # invented ID → strip silently
        # Cap: keep prose clean; extra evidence stays in the side panel.
        if seen_inline >= _MAX_INLINE_CITATIONS:
            continue
        page_key = _evidence_page_key(payload)
        if page_key in linked_pages:
            continue  # same page already linked → no duplicate chip
        # 3. Grounding check: the paragraph carrying the marker must name the
        #    concept whose evidence it points at.
        if not _topic_mentioned(_enclosing_block(text[:m.start()]), payload.get("topic")):
            continue  # misattached → drop the marker, keep the prose
        out.append(" " + render_citation_from_payload(payload))
        linked_pages.add(page_key)
        seen_inline += 1
    out.append(text[last:])
    cleansed = _re.sub(r"[^\S\n]+([.,;:!?])", r"\1", "".join(out))
    # Collapse horizontal runs only — never turn newlines into spaces
    cleansed = _re.sub(r"[^\S\n]{2,}", " ", cleansed)

    # 5. Guaranteed INLINE citation placement if no inline marker survived.
    #    Every payload is a candidate: slicing the pool used to hide the target
    #    concept's own evidence behind three prerequisites' worth of chunks, so
    #    an answer about the target got zero page links.
    if seen_inline == 0 and payloads:
        paragraphs = cleansed.split("\n\n")
        used_payloads = set()
        new_paragraphs = []
        full_lower = cleansed.lower()
        for p in paragraphs:
            p_text = p
            in_paragraph = 0
            for payload in payloads:
                if len(used_payloads) >= _MAX_INLINE_CITATIONS:
                    break
                if in_paragraph >= _MAX_LINKS_PER_PARAGRAPH:
                    break
                if payload["evidence_id"] in used_payloads:
                    continue
                page_key = _evidence_page_key(payload)
                if page_key in linked_pages:
                    continue
                if not _topic_tokens(payload.get("topic")):
                    continue  # unnamed topic proves nothing → never attach
                if not _topic_mentioned(p_text, payload.get("topic")):
                    continue
                cit_str = render_citation_from_payload(payload)
                if cit_str not in p_text:
                    p_text = p_text.rstrip() + " " + cit_str
                    in_paragraph += 1
                linked_pages.add(page_key)
                used_payloads.add(payload["evidence_id"])
            new_paragraphs.append(p_text)

        cleansed = "\n\n".join(new_paragraphs)
        if not used_payloads:
            # Nothing matched paragraph-by-paragraph. Fall back to the whole
            # answer as the attribution window before giving up on provenance —
            # a reply with zero page links is the failure we are fixing.
            matched = [
                p for p in payloads
                if _topic_tokens(p.get("topic")) and _topic_mentioned(full_lower, p.get("topic"))
            ]
            if matched:
                parts = cleansed.rstrip().split("\n")
                seen_links = set()
                extras = []
                for p in matched:
                    if len(extras) >= _MAX_LINKS_PER_PARAGRAPH:
                        break
                    page_key = _evidence_page_key(p)
                    if page_key in linked_pages:
                        continue
                    cit_str = render_citation_from_payload(p)
                    if cit_str not in seen_links and cit_str not in cleansed:
                        seen_links.add(cit_str)
                        linked_pages.add(page_key)
                        extras.append(" " + cit_str)
                joined = "".join(extras)
                if joined:
                    for i in range(len(parts) - 1, -1, -1):
                        if parts[i].strip():
                            parts[i] = parts[i].rstrip() + joined
                            break
                    else:
                        parts.append(joined.strip())
                    cleansed = "\n".join(parts)

    # 6. Final pass: model may have regenerated a footer after markers.
    return _strip_source_dump_footer(cleansed)
