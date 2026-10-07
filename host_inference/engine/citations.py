"""Select distinct, reader-backed source pages for a concept answer."""

from __future__ import annotations

from pathlib import PurePosixPath

from library_index import load_hf_paths, paper_url, resolve_hf_path

from .docmap import hf_doc_path
from .withdrawal import withdrawn_documents

MAX_REPLY_CITATIONS = 6


def citation_bundle(graph, anchor: str | None, primary: list[dict]) -> list[dict]:
    """Keep supplied citations and add pages from the same indexed concept."""
    records: list[dict] = []
    seen: set[tuple[str, int]] = set()

    manifest_paths = load_hf_paths()

    def add(record: dict) -> None:
        if not isinstance(record, dict) or not record.get("url"):
            return
        doc_id = str(record.get("doc_id") or "")
        if manifest_paths and not record.get("is_pearson") and not resolve_hf_path(doc_id):
            return
        page = int(record.get("page_number") or 1)
        key = (doc_id, page)
        if key in seen:
            return
        seen.add(key)
        entry = dict(record)
        named = str(record.get("title") or "").strip()
        entry.setdefault(
            "doc_title",
            named
            if len(named) > 12
            else PurePosixPath(doc_id).stem.replace("_", " ").replace("-", " "),
        )
        records.append(entry)

    for record in primary:
        add(record)
    if anchor and anchor in graph.nodes:
        retired = withdrawn_documents()
        for source in graph.nodes[anchor].get("sources") or []:
            if len(records) >= MAX_REPLY_CITATIONS:
                break
            raw_id = str(source.get("doc_id") or "")
            if not raw_id or raw_id in retired:
                continue
            doc_id = hf_doc_path(raw_id)
            page = int(source.get("page_number") or 1)
            add(
                {
                    "doc_id": doc_id,
                    "page_number": page,
                    "url": paper_url(doc_id, page),
                    "text_passage": source.get("text_passage") or "",
                }
            )
    return records[:MAX_REPLY_CITATIONS]


def source_link_lines(citations: list[dict]) -> list[str]:
    """Render readable paper/book and page labels for source routes."""
    lines = []
    for record in citations[:MAX_REPLY_CITATIONS]:
        url = str(record.get("url") or "")
        if not url:
            continue
        doc_id = str(record.get("doc_id") or "")
        title = str(record.get("doc_title") or record.get("title") or PurePosixPath(doc_id).stem)
        title = title.replace("_", " ").replace("-", " ").strip() or "Source"
        page = int(record.get("page_number") or 1)
        lines.append(f"[{title} — page {page}]({url})")
    return lines
