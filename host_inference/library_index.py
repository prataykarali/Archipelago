"""Match a question to any Pearson title or Hugging Face PDF and its exact page."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
STOP = {
    "what", "whats", "how", "does", "the", "and", "for", "with", "book", "books",
    "paper", "papers", "textbook", "explain", "about", "from", "this", "that",
    "page", "pages", "chapter", "tell", "where", "find", "open", "read", "show",
    "using", "into", "your", "library", "please", "would", "like",
}


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9]{4,}", (text or "").lower()) if tok not in STOP}


def load_hf_paths() -> list[str]:
    try:
        from remote_cache import load_library_manifest

        paths = load_library_manifest().get("hf_paths", [])
        if isinstance(paths, list):
            return [str(path) for path in paths if str(path).endswith(".pdf")]
    except Exception:
        pass
    path = HERE / "cache" / "hf_files.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("pdfs") or [])


def resolve_hf_path(value: str) -> str:
    """Resolve a reader request only to a dataset file present in the cloud manifest."""
    raw = (value or "").strip().lstrip("/")
    if not raw:
        return ""
    paths = set(load_hf_paths())
    if raw in paths:
        return raw
    base = raw.rsplit("/", 1)[-1]
    candidates = (
        raw.removeprefix("papers/"),
        f"books/papers/{base}",
        f"textbooks/{base}",
        f"books/textbooks/{base}",
        f"archipelago-books-cs/{raw}",
    )
    for candidate in candidates:
        if candidate in paths:
            return candidate
    return ""


def hf_title(path: str) -> str:
    parts = [part.rsplit(".", 1)[0] if part.lower().endswith(".pdf") else part for part in path.split("/")]
    return " ".join(parts).replace("_", " ").replace("-", " ")


def paper_url(path: str, page: int) -> str:
    page_n = max(1, int(page or 1))
    return f"/read?doc={quote(path, safe='')}&page={page_n}"


def pearson_open(book_id: str, page: int) -> str:
    page_n = max(1, int(page or 1))
    return f"/open/{book_id}?page={page_n}"


class Catalog:
    def __init__(self, nodes: dict, books: list[dict]):
        self.books = books
        self.hf = [{"path": path, "title": hf_title(path), "tokens": _tokens(hf_title(path))} for path in load_hf_paths()]
        self.passages: list[dict] = []
        for cid, node in nodes.items():
            for source in node.get("sources") or []:
                doc = str(source.get("doc_id") or "").lstrip("/")
                text = source.get("text_passage") or ""
                if not doc or not text:
                    continue
                self.passages.append({
                    "concept_id": cid,
                    "doc_id": doc,
                    "page": int(source.get("page_number") or 1),
                    "text": text,
                    "tokens": _tokens(text),
                })

    def match_hf(self, query: str) -> tuple[dict | None, int]:
        wanted = _tokens(query)
        best, score = None, 0
        for item in self.hf:
            overlap = len(wanted & item["tokens"])
            if overlap > score:
                best, score = item, overlap
        return best, score

    def match_pearson(self, query: str) -> tuple[dict | None, int]:
        wanted = _tokens(query)
        best, score = None, 0
        for book in self.books:
            tokens = _tokens(f"{book.get('title') or ''} {book.get('author') or ''}")
            overlap = len(wanted & tokens)
            if overlap > score:
                best, score = book, overlap
        return best, score

    def best_passage(self, query: str, doc_hint: str = "") -> dict | None:
        wanted = _tokens(query)
        hint = doc_hint.lower()
        best, score = None, 0
        for passage in self.passages:
            if hint and hint not in passage["doc_id"].lower() and passage["doc_id"].split("/")[-1].lower() not in hint:
                continue
            overlap = len(wanted & passage["tokens"])
            if overlap > score:
                best, score = passage, overlap
        if best and score >= 2:
            return best
        if hint:
            for passage in self.passages:
                if hint in passage["doc_id"].lower():
                    return passage
        return None

    def reply(self, query: str) -> dict | None:
        hf, hf_score = self.match_hf(query)
        book, book_score = self.match_pearson(query)
        # One shared word is too weak ("networks"). Two distinctive words, or one long title word.
        hf_ok = hf is not None and (hf_score >= 2 or any(len(tok) >= 8 and tok in hf["tokens"] for tok in _tokens(query)))
        book_ok = book is not None and (book_score >= 2 or any(len(tok) >= 8 and tok in _tokens(book.get("title") or "") for tok in _tokens(query)))
        if hf_ok and (not book_ok or hf_score >= book_score):
            return self._hf_reply(query, hf)
        if book_ok:
            return self._pearson_reply(query, book)
        return None

    def _hf_reply(self, query: str, item: dict) -> dict:
        passage = self.best_passage(query, item["path"]) or self.best_passage(query, item["title"])
        page = int(passage["page"]) if passage else 1
        url = paper_url(item["path"], page)
        excerpt = " ".join((passage["text"] if passage else "").split())[:420]
        if excerpt:
            body = f"**{item['title']}.** {excerpt}"
        else:
            body = (
                f"**{item['title']}.** This file is in the Hugging Face library dataset. "
                "No scanned passage is indexed beyond the file itself, so the reply does not invent a chapter."
            )
        text = "\n\n".join([
            body,
            f"**Paper page.** [{item['title']} p.{page}]({url})",
        ])
        return {
            "text": text,
            "citation": {
                "label": f"[S1: {item['path'].split('/')[-1]}, #page={page}]",
                "doc_id": item["path"],
                "page_number": page,
                "printed_page": page,
                "url": url,
                "pdf_url": url,
            },
        }

    def _pearson_reply(self, query: str, book: dict) -> dict:
        title = book.get("title") or "Pearson book"
        author = book.get("author") or "Institutional collection"
        page_count = int(book.get("page_count") or 1)
        passage = self.best_passage(query, title)
        page = int(passage["page"]) if passage else 1
        if page > page_count:
            page = 1
            passage = None
        url = pearson_open(book.get("id") or "", page)
        if passage:
            excerpt = " ".join(passage["text"].split())[:420]
            body = f"**{title}.** {author}. {excerpt}"
        else:
            body = (
                f"**{title}.** {author}. Pearson e-book, {page_count} pages. "
                "This reply uses the catalog record. It does not invent a chapter that is not indexed."
            )
        text = "\n\n".join([
            body,
            f"**Pearson page.** [{title} p.{page}]({url})",
        ])
        return {
            "text": text,
            "citation": {
                "label": f"[S1: {title}, #page={page}]",
                "doc_id": book.get("id") or "",
                "page_number": page,
                "printed_page": page,
                "url": url,
                "pdf_url": url,
                "book_id": book.get("id"),
                "is_pearson": True,
            },
        }
