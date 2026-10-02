"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from typing import Any
from . import _deps as _rt  # noqa: F401


def _search_by_isbn(isbn: str) -> list[_rt.MentionMatch]:
    """Look up an exact ISBN across the registry and Pearson catalogue."""
    if not isbn:
        return []
    out: list[_rt.MentionMatch] = []
    try:
        from archipelago.resolver.resource_registry import get_registry
        record = get_registry().get_by_isbn(isbn)
        if record is not None:
            out.append(_rt.MentionMatch(
                title=record.title or record.resource_id,
                match_kind=_rt.MATCH_KIND_EXACT_ISBN,
                source=_rt.SOURCE_NAMES[_rt.MATCH_KIND_EXACT_ISBN],
                confidence=100.0,
                source_url=record.blob_url or record.reader_url,
                doc_id=record.hf_file_path or record.resource_id,
                author=record.author,
                isbn=isbn,
                page_count=record.page_count,
                domain=record.domain,
            ))
    except Exception as exc:
        _rt.logger.debug("Registry ISBN lookup unavailable: %s", exc)
    try:
        from archipelago.ingestion.pearson_connector import PearsonCatalog
        catalog = PearsonCatalog.load_from_file(
            _rt._repo_root() / "data" / "catalogs" / "pearson_bookshelf.json"
        )
        book = catalog.find_by_isbn(isbn)
        if book is not None:
            out.append(_rt.MentionMatch(
                title=book.title,
                match_kind=_rt.MATCH_KIND_EXACT_ISBN,
                source=_rt.SOURCE_NAMES[_rt.MATCH_KIND_PEARSON],
                confidence=100.0,
                source_url=book.reader_base_url,
                doc_id=str(book.book_id or ""),
                author=str(book.author or ""),
                isbn=isbn,
            ))
    except Exception as exc:
        _rt.logger.debug("Pearson ISBN lookup unavailable: %s", exc)
    return out


def mention_book(query: str, limit: int = _rt.MAX_CANDIDATES) -> _rt.MentionResult:
    """Resolve a librarian's free-text book mention into ranked candidates."""
    text = str(query or "").strip()
    if not text:
        return _rt.MentionResult(
            query=text,
            no_match_reason="Mention is empty; type a book title, ISBN, or filename.",
        )

    tokens = _rt.title_tokens(text)
    isbn = _rt.extract_isbn(text)
    searched = [_rt.SOURCE_NAMES[k] for k in (
        _rt.MATCH_KIND_EXACT_ISBN, _rt.MATCH_KIND_CATALOG, _rt.MATCH_KIND_REGISTRY,
        _rt.MATCH_KIND_PEARSON, _rt.MATCH_KIND_HF, _rt.MATCH_KIND_LOCAL,
    )]
    candidates: list[_rt.MentionMatch] = []

    if isbn:
        candidates.extend(_search_by_isbn(isbn))
    if tokens:
        candidates.extend(_rt._search_registry(text, tokens))
        candidates.extend(_rt._search_pearson(text, tokens))
        candidates.extend(_rt._search_huggingface(text, tokens))
        candidates.extend(_rt._search_local_pdfs(text, tokens))
        candidates.extend(_rt._search_resource_catalog(text, tokens))

    matches = _rt._best(candidates)
    if limit and limit > 0:
        matches = matches[:limit]

    result = _rt.MentionResult(query=text, matches=matches, searched=searched)
    if not matches:
        result.no_match_reason = (
            "No indexed book, paper, or catalogue record matches that mention. "
            "Nothing was invented — upload the file or add a catalogue row instead."
        )
    return result


def is_trusted_match(match: _rt.MentionMatch) -> bool:
    """True when a match is specific enough to auto-fill a record.

    An exact ISBN hit, or a very high-confidence title hit, is trustworthy.
    Anything weaker may be a different work that shares the title, so its
    metadata must be confirmed by the librarian rather than auto-applied.
    """
    if match.match_kind == _rt.MATCH_KIND_EXACT_ISBN:
        return True
    return match.confidence >= _rt.METADATA_TRUST_MIN_CONFIDENCE


def prefill_from_match(match: _rt.MentionMatch, adopt_metadata: bool | None = None) -> dict[str, Any]:
    """Build the ingestion form payload for a chosen match.

    ``adopt_metadata`` controls whether bibliographic fields (author, ISBN,
    year, publisher) are copied across. It defaults to trusting the match only
    when that match is strong enough, so a fuzzy title hit never silently
    overwrites the details a librarian already read off the page.
    """
    if adopt_metadata is None:
        adopt_metadata = is_trusted_match(match)

    payload: dict[str, Any] = {
        "title": match.title,
        "source": match.source,
        "source_url": match.source_url,
        "match_kind": match.match_kind,
        "confidence": match.confidence,
        "metadata_trusted": adopt_metadata,
    }
    if adopt_metadata:
        payload["kind"] = "paper" if match.doc_id.startswith("papers/") else "textbook"

    optional = {
        "author": match.author,
        "isbn": match.isbn,
        "year": match.year,
        "publisher": match.publisher,
        "edition": match.edition,
        "domain": match.domain,
        "shelf_location": match.shelf_location,
        "doc_id": match.doc_id,
    }
    if adopt_metadata:
        payload.update({k: v for k, v in optional.items() if v})
    else:
        # Surfaced separately so the UI can offer them without applying them.
        suggestions = {k: v for k, v in optional.items() if v}
        if suggestions:
            payload["suggested_fields"] = suggestions

    if match.available_copies is not None:
        payload["available_copies"] = match.available_copies
    if match.is_catalog_only:
        # A catalogue-only record must not trigger a full text extraction.
        payload["license_mode"] = "metadata_only"
    if match.notes:
        payload["notes"] = match.notes
    return payload
