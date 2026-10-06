"""synthesis_library.py — Renderers and link injectors for physical library and catalog resources."""
from __future__ import annotations

import re
import urllib.parse
from typing import Any


def view_page_url(doc_id: str, page: int | None = None, highlight: str | None = None) -> str:
    """Generate a legacy-compatible deep link handled by the chat reader."""
    if not doc_id:
        return ""
    p_num = page if isinstance(page, int) and page > 0 else 1
    try:
        from archipelago.resolver.pearson import resolve as pearson_resolve
        pearson_url = pearson_resolve(str(doc_id), page=p_num)
        if pearson_url:
            return pearson_url
    except Exception:
        pass
    params = [f"doc={urllib.parse.quote(doc_id, safe="")}"]
    if page is not None:
        params.append(f"page={p_num}")
    if highlight:
        params.append(f"highlight={urllib.parse.quote(highlight)}")
    return f"view-page?{"&".join(params)}"


def _availability_line(total: int | None, available: int | None) -> str:
    """Format copy availability line."""
    if total is None or available is None:
        return "Availability not tracked in central catalog."
    copy_str = "copy" if total == 1 else "copies"
    if available == 0:
        return f"All {total} {copy_str} are currently checked out."
    return f"{available} of {total} {copy_str} available for checkout."


def inject_view_page_links(text: str, known_docs: list[tuple[str, str]] | None = None) -> str:
    """Inject view-page deep links for references formatted as (Book Title, Concept, page N)."""
    if not known_docs or not text:
        return text

    doc_map = {}
    for doc_id, doc_title in known_docs:
        doc_map[doc_title.lower()] = (doc_id, doc_title)
        # Add short name mapping if applicable
        short = doc_title.split(":")[0].strip().lower()
        doc_map[short] = (doc_id, doc_title)
        if "mathematics for machine learning" in doc_title.lower():
            doc_map["math for ml"] = (doc_id, doc_title)
        if "low-rank adaptation" in doc_title.lower():
            doc_map["lora"] = (doc_id, doc_title)

    pattern = re.compile(r"\(([^,]+),\s*([^,]+),\s*page\s*(\d+)\)", re.IGNORECASE)

    def _replace(match: re.Match) -> str:
        book_raw = match.group(1).strip()
        concept = match.group(2).strip()
        page_str = match.group(3).strip()
        book_lower = book_raw.lower()

        matched_entry = None
        for key, entry in doc_map.items():
            if key in book_lower or book_lower in key:
                matched_entry = entry
                break

        if not matched_entry:
            return match.group(0)

        doc_id, full_title = matched_entry
        url = view_page_url(doc_id, page=int(page_str), highlight=concept)
        return f"[View Page {page_str} of {book_raw}]({url})"

    return pattern.sub(_replace, text)


def render_physical_resources(concept: str, resources: list[dict[str, Any]]) -> str:
    """Format physical book holdings into markdown."""
    lines = [f"### 📚 Library Holdings for '{concept}'\n"]
    if not resources:
        lines.append(f"No physical resources or holdings are currently indexed for '{concept}'.")
        return "\n".join(lines)

    for r in resources:
        title = r.get("title", "Unknown Title")
        author = r.get("author", "Unknown Author")
        avail = _availability_line(r.get("total_copies"), r.get("available_copies"))
        shelf = r.get("shelf_location") or r.get("shelf", "Central Stack")
        lines.append(f"- **{title}** by {author}")
        lines.append(f"  - Status: {avail}")
        lines.append(f"  - Location: `{shelf}`")
        barcodes = r.get("barcodes")
        if barcodes:
            lines.append(f"  - Accession numbers: {barcodes}")
        subjects = r.get("subjects")
        if subjects:
            if isinstance(subjects, list):
                subjects = ", ".join(str(item) for item in subjects)
            lines.append(f"  - Subjects: {subjects}")
        if r.get("doc_id"):
            url = view_page_url(r["doc_id"], page=r.get("page_number", 1))
            lines.append(f"  - [View Document]({url})")
    return "\n".join(lines)


def render_catalog_resources(query: str, resources: list[dict[str, Any]]) -> str:
    """Format catalog search results."""
    return render_physical_resources(query, resources)


def render_resource_availability(title: str | dict[str, Any], resource: dict[str, Any] | None = None) -> str:
    """Format availability for a title or a resource record."""
    if resource is None and isinstance(title, dict):
        resource = title
        title = str(resource.get("title") or resource.get("resource_title") or "Unknown resource")
    resource = resource or {}
    avail = _availability_line(resource.get("total_copies"), resource.get("available_copies"))
    kind = "periodical" if resource.get("is_periodical") else "resource"
    return f"**{title}** ({kind}): {avail}"


def render_journal_status(subject: str | dict[str, Any], journals: list[dict[str, Any]] | None = None) -> str:
    """Format subscription and issue status from a subject or status record."""
    if isinstance(subject, dict):
        summary = subject
        subject = str(summary.get("name") or summary.get("subject") or "library")
        journals = summary.get("issues") or summary.get("journals") or []
        only_late = bool(summary.get("only_late"))
    else:
        only_late = False
    journals = journals or []
    heading = "Late issues" if only_late else f"Journal & Periodical Status: {subject}"
    lines = [f"### 📰 {heading}\n"]
    if not journals:
        message = f"No late issues were reported for {subject}; verify the latest receipt feed with the library." if only_late else f"No active periodical subscriptions found for {subject}."
        lines.append(message)
        return "\n".join(lines)
    for journal in journals:
        title = journal.get("resource_title") or journal.get("journal_title") or journal.get("title") or "Unknown Journal"
        status = journal.get("status") or "Status unknown"
        lines.append(f"- **{title}**: **{status}**")
    return "\n".join(lines)
