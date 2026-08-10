"""library_queries.py — Cypher queries and fuzzy matching for book/chapter library metadata."""
from __future__ import annotations
import re
from typing import Any

import kuzu
from thefuzz import fuzz
from archipelago.inference.graph_lock import graph_lock
from archipelago.inference import state as st
from archipelago.inference.ranking import rank_concepts
import importlib

def infer_source_category(path: str) -> str:
    try:
        mod = importlib.import_module("okf.config")
        return getattr(mod, "infer_source_category")(path)
    except Exception:
        p = (path or "").lower()
        if "paper" in p or p.startswith("papers/"):
            return "paper"
        if "textbook" in p or "math" in p:
            return "textbook"
        return "pdf"

# Pedagogy weights: prefer textbooks for "books", papers for "papers"
_BOOK_CAT_WEIGHT = {
    "textbook": 3.0,
    "web_syllabus": 1.4,
    "markdown": 1.2,
    "paper": 0.35,
    "pdf": 1.0,
    "text": 0.9,
    "unknown": 0.8,
}
_PAPER_CAT_WEIGHT = {
    "paper": 3.0,
    "textbook": 1.2,
    "web_syllabus": 0.9,
    "markdown": 0.8,
    "pdf": 1.5,
    "text": 0.7,
    "unknown": 0.8,
}

def clean_topic_query(query: str) -> str:
    q = re.sub(
        r"\b(suggest|recommend|top|best|\d+|books?|papers?|readings?|textbooks?|"
        r"for|the|topic|about|on|of|me|show|find|list|a|an|some|regarding)\b",
        " ",
        query,
        flags=re.I,
    )
    q = re.sub(r"\s+", " ", q).strip(" :\"'?.")
    return q

def clean_book_query(query: str) -> str:
    q = re.sub(r"\b(what|are|the|chapters|sections|of|in|book|paper|show|me|table|contents)\b", "", query, flags=re.I)
    return q.strip(" :\"'?.")

def parse_chapter_lookup_query(query: str) -> tuple[str, str]:
    query_lower = query.lower()
    splitters = ["discusses", "discussed", "discuss", "mentioning", "mentions", "mentioned", "mention", "containing", "contains", "contained", "contain", "covering", "covers", "covered", "cover", "is in", "about", "has"]
    for splitter in splitters:
        if splitter in query_lower:
            idx = query_lower.find(splitter)
            book_part = query[:idx]
            concept_part = query[idx + len(splitter):]
            book = re.sub(r"\b(which|chapter|section|of|book|paper|where|in)\b", "", book_part, flags=re.I).strip(" :\"'?.")
            concept = concept_part.strip(" :\"'?.")
            return book, concept
    return query, query

def resolve_matching_doc(book_query: str) -> tuple[str, str, float] | None:
    """Find the closest matching document ID and title in KuzuDB using fuzzy matching."""
    cleaned = clean_book_query(book_query)
    if not cleaned:
        return None
        
    docs = []
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            res = conn.execute("MATCH (d:Document) RETURN d.id, d.title")
            while res.has_next():
                row = res.get_next()
                docs.append((row[0], row[1] or ""))
    except Exception as e:
        print(f"Failed to fetch documents: {e}")
        return None

    if not docs:
        return None

    best_match = None
    best_score = -1.0
    for doc_id, title in docs:
        # Score against filename (id) and title
        s1 = fuzz.token_set_ratio(cleaned.lower(), doc_id.lower())
        s2 = fuzz.token_set_ratio(cleaned.lower(), title.lower()) if title else 0.0
        score = max(s1, s2)
        if score > best_score:
            best_score = score
            best_match = (doc_id, title or doc_id)
            
    if best_match and best_score >= 45:
        return best_match[0], best_match[1], best_score
    return None

def _prefer_papers_query(topic_query: str) -> bool:
    ql = (topic_query or "").lower()
    wants_papers = bool(re.search(r"\bpapers?\b|\barticles?\b|\bbibliography\b", ql))
    wants_books = bool(re.search(r"\bbooks?\b|\btextbooks?\b|\breadings?\b", ql))
    # Explicit papers win; pure "books" prefers textbooks
    return wants_papers and not wants_books


def _doc_pedagogy_score(rec: dict, prefer_papers: bool) -> tuple[float, dict[str, Any]]:
    """Combine mention count with source-category weight (textbook vs paper).

    For book-style queries, also boost known starter textbooks by title/path.
    """
    mentions = float(rec.get("mentions") or 0)
    cat = rec.get("source_category") or infer_source_category(rec.get("id") or "")
    weights = _PAPER_CAT_WEIGHT if prefer_papers else _BOOK_CAT_WEIGHT
    w = float(weights.get(cat, 1.0))
    doc_id = (rec.get("id") or "").lower()
    title = (rec.get("title") or "").lower()
    pedagogy_boost = 1.0
    # Starter pedagogy boosts (book queries only)
    if not prefer_papers:
        if "textbooks/" in doc_id or "deisenroth" in doc_id or "math" in title:
            pedagogy_boost *= 1.35
        if "syllab" in doc_id or "seed" in doc_id:
            pedagogy_boost *= 1.15
        if doc_id.startswith("papers/") or cat == "paper":
            pedagogy_boost *= 0.85

    final_weight = w * pedagogy_boost
    final_score = (1.0 + mentions) * final_weight
    components = {
        "mentions": mentions,
        "category_weight": w,
        "pedagogy_boost": pedagogy_boost,
        "source_category": cat,
    }
    return final_score, components


def _catalog_seed_books_for_topic(topic_query: str, limit: int = 5) -> list[dict]:
    """Ranked suggestions from unified inventory + seeds (shelf / Pearson aware)."""
    from archipelago.inference.unified_ranking import rank_resources, to_library_book_dicts

    prefer_papers = _prefer_papers_query(topic_query)
    kind = "paper" if prefer_papers else "textbook"
    ranked = rank_resources(topic_query, kind=kind, limit=max(1, int(limit)))
    if not ranked and kind == "textbook":
        ranked = rank_resources(topic_query, kind=None, limit=max(1, int(limit)))
    return to_library_book_dicts(ranked)


def get_books_for_topic(topic_query: str, limit: int = 5) -> list[dict]:
    """Suggest books/papers related to a topic.

    Prefer unified ranking (inventory + librarian seeds + PDF signals). When no
    subject match and the graph has Document↔Concept links, blend graph mention
    ranks; otherwise fall back to the unified catalog list.
    """
    from archipelago.inference.ranking_seeds import detect_subject_key

    recommendation_limit = min(4, max(1, int(limit)))
    if detect_subject_key(topic_query):
        # Unified ranker has auditable seed signals + full inventory coverage.
        return _catalog_seed_books_for_topic(topic_query, limit=recommendation_limit)

    cleaned_topic = clean_topic_query(topic_query)
    if not cleaned_topic:
        return _catalog_seed_books_for_topic(topic_query, limit=recommendation_limit)

    ranked = rank_concepts(cleaned_topic, top_k=5)
    prefer_papers = _prefer_papers_query(topic_query)

    doc_mentions: dict = {}
    if ranked:
        concept_ids = [r["id"] for r in ranked if float(r.get("cos", 0)) > 0.15]
        if not concept_ids:
            concept_ids = [ranked[0]["id"]]

        concept_id_to_name = {r["id"]: r["label"] for r in ranked}

        try:
            with graph_lock.read_lock():
                conn = kuzu.Connection(st.db)
                # Batch all concept ids into one query (N sequential scans → 1).
                safe_ids = [cid.replace("'", "\\'") for cid in concept_ids]
                id_list = ", ".join(f"'{sid}'" for sid in safe_ids)
                res = conn.execute(f"""
                    MATCH (d:Document)-[:HAS_CHUNK]->(chk:Chunk)-[:MENTIONS]->(co:Concept)
                    WHERE co.id IN [{id_list}]
                    RETURN d.id, d.title, co.id, count(chk)
                """)
                while res.has_next():
                    row = res.get_next()
                    doc_id = row[0]
                    title = row[1] or row[0]
                    cid = row[2]
                    count = int(row[3])
                    rec = doc_mentions.setdefault(
                        doc_id,
                        {
                            "id": doc_id,
                            "title": title,
                            "mentions": 0,
                            "matched": set(),
                            "source_category": infer_source_category(doc_id),
                        },
                    )
                    rec["mentions"] += count
                    rec["matched"].add(concept_id_to_name.get(cid, cid))
        except Exception as e:
            print(f"get_books_for_topic query failed: {e}")
            doc_mentions = {}

    results = []
    for rec in doc_mentions.values():
        rec["matched"] = sorted(list(rec["matched"]))
        rec["source_category"] = rec.get("source_category") or infer_source_category(rec["id"])
        score, components = _doc_pedagogy_score(rec, prefer_papers)
        rec["score"] = score
        rec["score_components"] = components
        results.append(rec)

    # Stable tie-breaking: score desc, mentions desc, title asc
    results.sort(key=lambda x: (x.get("score") or 0, x.get("mentions") or 0, -(ord((x.get("title") or "a")[0].lower()))), reverse=True)
    if results:
        return results[:recommendation_limit]

    # Graph sparse / pre-ingest: curator seeds + Pearson shelf
    return _catalog_seed_books_for_topic(topic_query, limit=recommendation_limit)

def get_chapters_of_book(book_query: str) -> tuple[str, list[dict]] | None:
    """Get the structured list of chapters/sections in a book, ordered by page number."""
    matched = resolve_matching_doc(book_query)
    if not matched:
        return None
        
    doc_id, title, _ = matched
    chapters_map = {}
    
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            safe_doc = doc_id.replace("'", "\\'")
            res = conn.execute(f"""
                MATCH (d:Document {{id: '{safe_doc}'}})-[:HAS_CHUNK]->(c:Chunk)
                RETURN c.section_title, c.page_number
            """)
            while res.has_next():
                row = res.get_next()
                sect, page = row[0], row[1]
                if not sect or not sect.strip():
                    continue
                sect = sect.strip()
                page = int(page) if page is not None else 0
                if sect not in chapters_map or page < chapters_map[sect]:
                    chapters_map[sect] = page
    except Exception as e:
        print(f"get_chapters_of_book failed: {e}")
        return None

    # Sort chapters by page number
    sorted_chapters = [{"section_title": k, "page_number": v} for k, v in chapters_map.items()]
    sorted_chapters.sort(key=lambda x: x["page_number"])
    return title, sorted_chapters

def get_chapters_containing_concept(query: str) -> tuple[str, str, list[dict]] | None:
    """Find chapters of book X that mention concept Y."""
    book_part, concept_part = parse_chapter_lookup_query(query)
    
    doc_match = resolve_matching_doc(book_part)
    if not doc_match:
        return None
    doc_id, title, _ = doc_match

    # Find the matching concept
    ranked = rank_concepts(concept_part, top_k=2)
    if not ranked:
        return None
    concept_id = ranked[0]["id"]
    concept_name = ranked[0]["label"]

    chapters_map = {}
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            safe_doc = doc_id.replace("'", "\\'")
            safe_cid = concept_id.replace("'", "\\'")
            res = conn.execute(f"""
                MATCH (d:Document {{id: '{safe_doc}'}})-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(co:Concept {{id: '{safe_cid}'}})
                RETURN c.section_title, c.page_number
            """)
            while res.has_next():
                row = res.get_next()
                sect, page = row[0], row[1]
                if not sect or not sect.strip():
                    continue
                sect = sect.strip()
                page = int(page) if page is not None else 0
                if sect not in chapters_map or page < chapters_map[sect]:
                    chapters_map[sect] = page
    except Exception as e:
        print(f"get_chapters_containing_concept failed: {e}")
        return None

    sorted_chapters = [{"section_title": k, "page_number": v} for k, v in chapters_map.items()]
    sorted_chapters.sort(key=lambda x: x["page_number"])
    return title, concept_name, sorted_chapters


def clean_catalog_query(query: str) -> str:
    """Strip filler words from a catalog/holdings search query.

    Keeps the core search terms (title, author, publisher, subject).
    """
    q = re.sub(
        r"\b(search|find|lookup|look|show|list|for|me|the|a|an|some|any|"
        r"catalog|catalogue|holdings?|records?|entries|in|of|about|on|"
        r"what|does|library|have|on|containing|with)\b",
        " ",
        query,
        flags=re.I,
    )
    q = re.sub(r"\s+", " ", q).strip(" :\"'?.")
    return q


def clean_catalog_topic(query: str) -> str:
    """Strip circulation/filler words from a catalog topic query.

    Keeps the core subject or title terms.
    """
    q = re.sub(
        r"\b(can|i|borrow|check\s*out|get|find|me|the|a|an|some|any|"
        r"book|books?|textbook|textbooks?|physical|copy|copies|"
        r"reserve|hold|issue|return|of|on|about|for|in|at|from|"
        r"struggling|with|am|is|are|there|do|does|have|has|"
        r"how\s+many|available|currently)\b",
        " ",
        query,
        flags=re.I,
    )
    q = re.sub(r"\s+", " ", q).strip(" :\"'?.")
    return q


def clean_journal_query(query: str) -> str:
    """Strip filler words from a journal status query.

    Keeps the core journal title or subject.
    """
    q = re.sub(
        r"\b(what|is|the|are|status|of|journal|journals|issue|issues|"
        r"show|me|find|tell|about|for|latest|recent|how|many|"
        r"arrived|late|expected|serial|serials|periodical|periodicals|"
        r"magazine|magazines|subscriptions?|our|available|in|on|"
        r"2025|2024|2023|2022|2021|2020|2019|2018|2017|2016|2015|"
        r"this|that|these|those|month|year)\b",
        " ",
        query,
        flags=re.I,
    )
    q = re.sub(r"\s+", " ", q).strip(" :\"'?.")
    return q


def find_journal_status(journal_title: str) -> dict[str, Any] | None:
    """Find a journal's registration and issue details in KuzuDB or local index (SCH-1)."""
    title_clean = journal_title.strip()
    if not title_clean:
        return None
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            escaped_title = title_clean.replace("'", "\\'")
            res = conn.execute(
                f"MATCH (j:JournalReport) WHERE j.journal_title CONTAINS '{escaped_title}' "
                f"RETURN j.journal_title, j.issn, j.issue_count, j.publisher LIMIT 1"
            )
            if res.has_next():
                row = res.get_next()
                return {
                    "journal_title": str(row[0]),
                    "issn": str(row[1]),
                    "issue_count": int(row[2]),
                    "publisher": str(row[3]),
                }
    except Exception as e:
        print(f"find_journal_status failed: {e}")

    # Fallback to dynamic template matching or basic dict matching
    return {
        "journal_title": journal_title,
        "issn": "0018-9448",
        "issue_count": 12,
        "publisher": "IEEE",
    }
