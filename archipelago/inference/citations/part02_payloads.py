"""Citation payload builders: page-anchored links, structured payloads, library sources."""

from __future__ import annotations

from urllib.parse import quote

from archipelago.inference import state as st
from archipelago.inference.aliases import _node_name
from archipelago.inference.citations.part01_evidence import _resolve_printed_page
from archipelago.resolver.pearson import PEARSON_READER_VERSION as _reader_version


def _huggingface_source_url(doc_id: str) -> str:
    """Exact Hugging Face dataset file page for an indexed document.

    Returns the per-file ``blob/main/...`` page (never the dataset homepage) so
    the citation always points at the specific document that was read.
    """
    if not doc_id or not doc_id.endswith(".pdf"):
        return ""
    try:
        from archipelago.resolver.huggingface import resolve_huggingface_url
    except Exception:
        return ""
    try:
        result = resolve_huggingface_url(doc_id, filename=doc_id, verify_existence=False)
    except Exception:
        return ""
    blob = (result or {}).get("blob_url") or ""
    if not blob:
        return ""
    # Guard against a bare repo root ever being surfaced.
    if blob.rstrip("/").endswith("/Library_books"):
        return ""
    return blob


def build_citation_link(chunk: dict, doc: dict) -> str:
    """Build a page-anchored citation URL for a chunk.

    For Pearson eLibrary books, produces a reader URL with #book/{uuid}/page/{page} fragment.
    For standard PDFs, produces /api/page-view?doc_id=...&page=...#page=... URL.
    """
    page = chunk.get("page_number", 1)
    if not isinstance(page, int) or page < 1:
        page = 1
    doc_id = chunk.get("doc_id") or doc.get("doc_id") or doc.get("id") or ""
    title = doc.get("title") or chunk.get("title") or ""

    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve

        pearson_url = pearson_resolve(doc_id, page=page)
        if not pearson_url and title:
            pearson_url = pearson_resolve(title, page=page)
        if pearson_url:
            return pearson_url
    except Exception:
        pass

    reader_url = doc.get("reader_base_url") or doc.get("reader_url") or ""
    if reader_url and "pearson" in reader_url.lower():
        try:
            from archipelago.resolver.pearson import build_reader_url

            return build_reader_url(doc, page=page)
        except Exception:
            pass

    url = f"/read/{quote(doc_id, safe='')}?page={page}#page={page}"
    return url


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
    url = f"/api/page-view?doc_id={quote(doc_id, safe='')}"
    if isinstance(page_number, int) and page_number > 0:
        url += f"&page={page_number}#page={page_number}"
    text = evidence.get("text") or ""
    start = evidence.get("text_offset_start")
    end = evidence.get("text_offset_end")
    text_span = text
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
        text_span = text[start:end]
    # Always emit a human-readable title. When chunk metadata omits it,
    # fall back to prettified doc basename so the UI never renders "Source".
    title = (evidence.get("doc_title") or evidence.get("title") or "").strip()
    if not title and doc_id:
        from archipelago.inference.synthesis import prettify_doc_title

        title = prettify_doc_title(doc_id)

    # Check for Pearson textbook match
    is_pearson = False
    reader_url = ""
    book_id = ""
    subscription_id = ""
    isbn = ""
    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve
        from archipelago.resolver.pearson import resolve_pearson_url

        p_res = resolve_pearson_url(book_id=doc_id, title=title)
        if p_res.get("working") and p_res.get("book_id"):
            is_pearson = True
            book_id = p_res.get("book_id", "")
            subscription_id = p_res.get("subscription_id", "")
            isbn = p_res.get("isbn", "")
            p_page = page_number if isinstance(page_number, int) and page_number > 0 else 1
            p_url = pearson_resolve(book_id, page=p_page)
            if p_url:
                reader_url = p_url
                url = p_url
            if not title and p_res.get("title"):
                title = p_res["title"]
    except Exception:
        pass

    payload = {
        "evidence_id": evidence_id,
        "topic": topic,
        "doc_id": doc_id,
        "title": title,
        "page_number": page_number,
        "printed_page": _resolve_printed_page(evidence),
        "section_title": evidence.get("section_title") or "",
        "url": url,
        "reader_url": reader_url or url,
        "text_span": text_span,
        "is_pearson": is_pearson,
        "book_id": book_id,
        "subscription_id": subscription_id,
        "isbn": isbn,
    }
    # When the document is indexed from the Hugging Face dataset, also expose the
    # exact dataset file page so a reader can reach the original source directly
    # (never the dataset homepage).
    source_url = _huggingface_source_url(doc_id)
    if source_url:
        payload["hf_url"] = source_url
        payload["source_dataset"] = "huggingface"
    payload["pearson_version"] = _reader_version if is_pearson else ""
    # Circulation fields are emitted only for an exact match to Koha ODS.
    from archipelago.inference.corpus_inventory import inventory_for_books

    inventory = inventory_for_books([{"book_title": title, "doc_id": doc_id}])[0]
    if inventory.get("koha_record_verified"):
        payload.update(
            {
                key: inventory[key]
                for key in (
                    "koha_record_verified",
                    "total_copies",
                    "available_copies",
                    "availability",
                    "accession",
                    "publisher",
                )
                if key in inventory
            }
        )
    return payload


def build_library_source_payloads(books, topic):
    """Build citation payloads for library book search results (SCH-1)."""
    from archipelago.inference.routes_page_view import _is_known_catalog_path

    payloads = []
    for idx, b in enumerate(books, 1):
        doc_id = b.get("id") or b.get("doc_id") or ""
        if not doc_id:
            continue

        # Exclude unindexed seeds
        if not (doc_id.endswith(".pdf") or "/" in doc_id):
            continue
        try:
            if not _is_known_catalog_path(doc_id):
                continue
        except Exception:
            pass

        url = f"{st.PDF_BASE_URL}/api/page-view?doc_id={quote(doc_id, safe='')}&page=1&highlight={quote(topic, safe='')}#page=1"
        payloads.append(
            {
                "evidence_id": f"S{idx}",
                "source_type": "indexed_document",
                "doc_id": doc_id,
                "page_number": 1,
                "url": url,
                "topic": topic,
                "text_span": b.get("title") or doc_id,
            }
        )
    return payloads


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
