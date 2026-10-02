"""Chat route handlers: library queries (details, hours, holdings, books, chapters)."""

from __future__ import annotations

import json

from flask import Response

from archipelago.inference.library_queries import (
    clean_topic_query,
    get_book_metadata_details,
    get_books_for_topic,
    get_chapters_containing_concept,
    get_chapters_of_book,
    get_library_holdings_response,
    get_library_hours_response,
    render_library_book_details,
)
from archipelago.inference.routes.chat.part00_shared import with_holdings
from archipelago.inference.synthesis import (
    render_library_books,
    render_library_chapter_lookup,
    render_library_chapters,
)


def handle_library_book_details(query, history, routing, wants_synthesis):
    """Book metadata & summaries."""
    meta = get_book_metadata_details(query)
    book_citations = []
    if meta:
        doc_id = meta.get("doc_id") or meta.get("book_id") or f"doc_{meta['title']}"
        reader_url = meta.get("reader_url") or meta.get("pdf_path") or ""
        book_citations.append(
            {
                "evidence_id": "S1",
                "doc_id": doc_id,
                "title": meta["title"],
                "document_title": meta["title"],
                "page_number": 1,
                "page": 1,
                "is_pearson": bool(meta.get("is_pearson")),
                "reader_url": reader_url,
                "url": reader_url,
                "shelf_location": meta.get("shelf_location", "PEARSON-ELIB"),
                "call_number": meta.get("call_number", "PEARSON-ELIB"),
                "total_copies": meta.get("total_copies", 10),
                "available_copies": meta.get("available_copies", 8),
            }
        )
        notes = render_library_book_details(meta)
        details = f"Retrieved comprehensive metadata for '{meta['title']}'."
    else:
        notes = f"### 📚 Book Details\nCould not find a specific indexed book or paper matching '{query}'. You can browse the complete e-book shelves at [/library](/library)."
        details = "No exact book match."

    def generate_book_details():
        payload = {
            "anchor_concept": None,
            "prerequisites": meta.get("prerequisites", []) if meta else [],
            "unlocks": meta.get("unlocks", []) if meta else [],
            "citations": book_citations,
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "library_book_details"},
            "logs": [
                {
                    "step": "Library Retrieval",
                    "status": "Success" if meta else "Not Found",
                    "details": details,
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, notes, citations=book_citations, meta=meta)

    return Response(generate_book_details(), mimetype="text/plain")


def handle_library_resources(query, history, routing, wants_synthesis):
    """Institutional portal guidance (redacted)."""
    from archipelago.inference.library_resource_access import render_resource_access

    resource_key = str((routing.get("slots") or {}).get("resource_key") or "")
    notes = render_resource_access(query, resource_key=resource_key)

    def generate_resource_access():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "library_resources"},
            "logs": [
                {
                    "step": "Library Access",
                    "status": "Success",
                    "details": "Returned redacted institutional portal guidance.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, notes)

    return Response(generate_resource_access(), mimetype="text/plain")


def handle_library_hours(query, history, routing, wants_synthesis):
    """Operating hours & access policies."""
    notes = get_library_hours_response()

    def generate_hours():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "library_hours"},
            "logs": [
                {
                    "step": "Library Retrieval",
                    "status": "Success",
                    "details": "Retrieved 24x7 operating hours & circulation policies.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, notes)

    return Response(generate_hours(), mimetype="text/plain")


def handle_library_holdings(query, history, routing, wants_synthesis):
    """Catalog inventory metrics."""
    notes = get_library_holdings_response(query)

    def generate_holdings():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "library_holdings"},
            "logs": [
                {
                    "step": "Library Retrieval",
                    "status": "Success",
                    "details": "Retrieved catalog inventory metrics (109 records / 904 copies).",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, notes)

    return Response(generate_holdings(), mimetype="text/plain")


def handle_library_books(query, history, routing, wants_synthesis):
    """Book recommendations by topic."""
    topic = clean_topic_query(query)
    limit = int((routing.get("slots") or {}).get("limit") or 5)
    books = get_books_for_topic(query, limit=limit)
    notes = render_library_books(topic, books)
    book_citations = []
    for i, b in enumerate(books):
        b_url = b.get("reader_url") or b.get("url") or ""
        book_citations.append(
            {
                "evidence_id": f"S{i + 1}",
                "doc_id": b.get("doc_id") or b.get("book_id") or b.get("id"),
                "title": b.get("title") or b.get("book_title"),
                "document_title": b.get("title") or b.get("book_title"),
                "page_number": int(b.get("page_number") or 1),
                "page": int(b.get("page_number") or 1),
                "is_pearson": bool(b.get("is_pearson")),
                "reader_url": b_url,
                "url": b_url,
                "shelf_location": b.get("shelf_location", "PEARSON-ELIB"),
                "call_number": b.get("call_number", "PEARSON-ELIB"),
                "total_copies": int(b.get("total_copies") or 10),
                "available_copies": int(b.get("available_copies") or 8),
            }
        )

    def generate_books():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": book_citations,
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "library_books"},
            "logs": [
                {
                    "step": "Library Retrieval",
                    "status": "Success",
                    "details": f"Found {len(books)} books for topic '{topic}'.",
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, notes, citations=book_citations, books=books)

    return Response(generate_books(), mimetype="text/plain")


def handle_library_chapters(query, history, routing, wants_synthesis):
    """Chapters of a book."""
    res = get_chapters_of_book(query)
    if res:
        book_title, chapters = res
        notes = render_library_chapters(book_title, chapters)
        details = f"Retrieved {len(chapters)} chapters for '{book_title}'."
    else:
        book_title = query
        notes = f"Could not find any matching book/paper for '{query}' in the database."
        details = "No book match found."

    def generate_chapters():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {"route": routing["route"], "score": 1.0, "reason": "library_chapters"},
            "logs": [
                {
                    "step": "Library Retrieval",
                    "status": "Success" if res else "Not Found",
                    "details": details,
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, notes)

    return Response(generate_chapters(), mimetype="text/plain")


def handle_library_chapter_lookup(query, history, routing, wants_synthesis):
    """Chapters containing a concept."""
    res = get_chapters_containing_concept(query)
    if res:
        book_title, concept_name, chapters = res
        notes = render_library_chapter_lookup(book_title, concept_name, chapters)
        details = f"Found {len(chapters)} chapters in '{book_title}' discussing '{concept_name}'."
    else:
        notes = f"Could not find matching book or concept for query: '{query}'."
        details = "No match found."

    def generate_lookup():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": [],
            "routing": {
                "route": routing["route"],
                "score": 1.0,
                "reason": "library_chapter_lookup",
            },
            "logs": [
                {
                    "step": "Library Retrieval",
                    "status": "Success" if res else "Not Found",
                    "details": details,
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, notes)

    return Response(generate_lookup(), mimetype="text/plain")
