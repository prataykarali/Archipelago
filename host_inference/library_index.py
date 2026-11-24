"""Match a question to any Pearson title or Hugging Face PDF and its exact page."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote

import requests

HERE = Path(__file__).resolve().parent
_HF_PATHS_LOCK = threading.Lock()
_HF_PATHS_CACHE: tuple[float, list[str], dict[str, str]] = (0.0, [], {})
_HF_PATHS_TTL_SEC = 300.0
_HF_TREE_TIMEOUT_SEC = 8.0
DEFAULT_LIBRARY_REPO = "Prataykarali/Library_books"
DEFAULT_GRAPHIER_REPO = "Prataykarali/graphier"
STOP = {
    "what",
    "whats",
    "how",
    "does",
    "the",
    "and",
    "for",
    "with",
    "book",
    "books",
    "paper",
    "papers",
    "textbook",
    "explain",
    "about",
    "from",
    "this",
    "that",
    "page",
    "pages",
    "chapter",
    "tell",
    "where",
    "find",
    "open",
    "read",
    "show",
    "using",
    "into",
    "your",
    "library",
    "please",
    "would",
    "like",
}
REQUESTED_PAGE_RE = re.compile(r"\b(?:page|p\.)\s*(\d+)\b", re.I)
MAX_REQUESTED_PAGE = 10000


def requested_page(query: str) -> int | None:
    """Return an explicitly requested page, bounded against abusive input."""
    match = REQUESTED_PAGE_RE.search(query)
    if not match:
        return None
    page = int(match.group(1))
    return page if 1 <= page <= MAX_REQUESTED_PAGE else None


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9]{4,}", (text or "").lower()) if tok not in STOP}


def _fetch_hf_repo_pdfs(repo: str, token: str) -> list[str]:
    """Fetch recursive PDF paths from a Hugging Face dataset repo."""
    if not repo:
        return []
    url = f"https://huggingface.co/api/datasets/{repo}/tree/main?recursive=true"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = requests.get(url, headers=headers, timeout=_HF_TREE_TIMEOUT_SEC)
        if resp.status_code != 200:
            return []
        items = resp.json()
        if not isinstance(items, list):
            return []
        return [
            str(item["path"])
            for item in items
            if isinstance(item, dict) and str(item.get("path", "")).lower().endswith(".pdf")
        ]
    except Exception:
        return []


def _load_hf_repo_map() -> tuple[list[str], dict[str, str]]:
    """Return ``(all_paths, path_to_repo)`` merged across Library_books and graphier."""
    global _HF_PATHS_CACHE
    now = time.monotonic()
    with _HF_PATHS_LOCK:
        if _HF_PATHS_CACHE[1] and (now - _HF_PATHS_CACHE[0]) < _HF_PATHS_TTL_SEC:
            return list(_HF_PATHS_CACHE[1]), dict(_HF_PATHS_CACHE[2])

    lib_repo = (
        os.environ.get("HF_LIBRARY_REPO", DEFAULT_LIBRARY_REPO).strip() or DEFAULT_LIBRARY_REPO
    )
    graph_repo = (
        os.environ.get("ARCHIPELAGO_SCHOLARLY_HF_REPO", DEFAULT_GRAPHIER_REPO).strip()
        or DEFAULT_GRAPHIER_REPO
    )
    token = os.environ.get("HF_TOKEN", "").strip()

    path_to_repo: dict[str, str] = {}
    try:
        from remote_cache import load_library_manifest

        paths = load_library_manifest().get("hf_paths", [])
        if isinstance(paths, list):
            for p in paths:
                sp = str(p).strip().lstrip("/")
                if sp.lower().endswith(".pdf"):
                    path_to_repo[sp] = lib_repo
    except Exception:
        pass

    if not path_to_repo:
        cache_path = HERE / "cache" / "hf_files.json"
        if cache_path.is_file():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                for p in payload.get("pdfs") or []:
                    sp = str(p).strip().lstrip("/")
                    if sp.lower().endswith(".pdf"):
                        path_to_repo[sp] = lib_repo
            except (OSError, json.JSONDecodeError):
                pass

    # Live HF Hub tree refresh for both Library_books and graphier when HF_TOKEN is set.
    if token:
        for repo in (lib_repo, graph_repo):
            for sp in _fetch_hf_repo_pdfs(repo, token):
                clean = sp.strip().lstrip("/")
                if clean and clean not in path_to_repo:
                    path_to_repo[clean] = repo

    resolved = list(path_to_repo.keys())
    with _HF_PATHS_LOCK:
        _HF_PATHS_CACHE = (now, resolved, path_to_repo)
    return resolved, path_to_repo


def load_hf_paths() -> list[str]:
    paths, _ = _load_hf_repo_map()
    return paths


def _norm_slug(value: str) -> str:
    stem = value.rsplit("/", 1)[-1]
    stem = re.sub(r"\.pdf$", "", stem, flags=re.I)
    stem = re.sub(r"^(?:doc|book|paper|pearson)_+", "", stem, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", stem.lower())


def resolve_hf_source(value: str) -> tuple[str, str]:
    """Resolve a reader request to ``(hf_repo, path)`` across Library_books & graphier."""
    raw = (value or "").strip().lstrip("/")
    if not raw:
        return "", ""
    paths, path_to_repo = _load_hf_repo_map()
    if not paths:
        return "", ""

    if raw in path_to_repo:
        return path_to_repo[raw], raw

    lower_map = {p.lower(): p for p in paths}
    if raw.lower() in lower_map:
        matched = lower_map[raw.lower()]
        return path_to_repo[matched], matched

    base = raw.rsplit("/", 1)[-1]
    candidates = (
        raw.removeprefix("papers/"),
        f"papers/{base}",
        f"books/papers/{base}",
        f"textbooks/{base}",
        f"books/textbooks/{base}",
        f"archipelago-books-cs/{raw}",
        f"archipelago-books-cs/{base}",
    )
    for candidate in candidates:
        matched = lower_map.get(candidate.lower())
        if matched:
            return path_to_repo[matched], matched

    # Case-insensitive basename match across any subdirectory in Library_books or graphier.
    base_lower = base.lower()
    for p in paths:
        if p.rsplit("/", 1)[-1].lower() == base_lower:
            return path_to_repo[p], p

    # Normalized slug match for doc_ / book_ / paper_ identifiers.
    target_slug = _norm_slug(raw)
    if len(target_slug) >= 5:
        for p in paths:
            p_slug = _norm_slug(p)
            if p_slug == target_slug or (
                len(p_slug) >= 6 and (target_slug in p_slug or p_slug in target_slug)
            ):
                return path_to_repo[p], p

    return "", ""


def resolve_hf_path(value: str) -> str:
    """Resolve a reader request only to a dataset file present in the HF datasets."""
    _, path = resolve_hf_source(value)
    return path


def hf_title(path: str) -> str:
    parts = [
        part.rsplit(".", 1)[0] if part.lower().endswith(".pdf") else part
        for part in path.split("/")
    ]
    return " ".join(parts).replace("_", " ").replace("-", " ")


def paper_url(path: str, page: int | None) -> str:
    base = f"/read?doc={quote(path, safe='')}"
    return f"{base}&page={page}" if page and page > 0 else base


def pearson_open(book_id: str, page: int | None) -> str:
    base = f"/open/{book_id}"
    return f"{base}?page={page}" if page and page > 0 else base


class Catalog:
    def __init__(self, nodes: dict, books: list[dict]):
        self.books = books
        self.hf = [
            {"path": path, "title": hf_title(path), "tokens": _tokens(hf_title(path))}
            for path in load_hf_paths()
        ]
        self.passages: list[dict] = []
        for cid, node in nodes.items():
            for source in node.get("sources") or []:
                doc = str(source.get("doc_id") or "").lstrip("/")
                text = source.get("text_passage") or ""
                if not doc or not text:
                    continue
                self.passages.append(
                    {
                        "concept_id": cid,
                        "doc_id": doc,
                        "page": int(source.get("page_number") or 1),
                        "text": text,
                        "tokens": _tokens(text),
                    }
                )
        self.candidate_passages_info: dict[str, object] = {
            "loaded": False,
            "count": 0,
            "document_count": 0,
            "sha256": None,
            "expected_sha256": None,
            "checksum_verified": False,
            "source": None,
        }
        candidate_index = os.environ.get("ARCHIPELAGO_CANDIDATE_PASSAGES", "").strip()
        if candidate_index and candidate_index not in {"0", "false", "none"}:
            self._load_candidate_passages(Path(candidate_index), source="env_path")
        elif not candidate_index and not os.environ.get("PYTEST_CURRENT_TEST"):
            default_cache = HERE / "cache" / "d10_candidate_passages.jsonl"
            if default_cache.is_file():
                self._load_candidate_passages(default_cache, source="local_cache")
            else:
                self._load_remote_candidate_passages()

    def _load_remote_candidate_passages(self) -> None:
        """Fetch the checksum-verified passage index from private staging Supabase Storage."""
        storage_object = os.environ.get("ARCHIPELAGO_CANDIDATE_PASSAGES_STORAGE", "").strip()
        if not storage_object:
            return
        url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
        key = (
            os.environ.get("SUPABASE_SECRET_KEY", "").strip()
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        )
        if not url or not key:
            return
        cache_path = Path("/tmp/archipelago_d10_candidate_passages.jsonl")
        if not cache_path.is_file():
            try:
                resp = requests.get(
                    f"{url}/storage/v1/object/{storage_object.lstrip('/')}",
                    headers={"apikey": key, "Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                if resp.status_code != 200 or not resp.content:
                    self.candidate_passages_info["error"] = f"remote_http_{resp.status_code}"
                    return
                cache_path.write_bytes(resp.content)
            except (requests.RequestException, OSError):
                self.candidate_passages_info["error"] = "remote_fetch_failed"
                return
        self._load_candidate_passages(cache_path, source="supabase_storage")

    def _load_candidate_passages(self, index_path: Path, *, source: str = "local") -> None:
        """Add rights-approved, deterministic PDF body chunks to catalog retrieval."""
        if not index_path.is_file():
            return
        raw_bytes = index_path.read_bytes()
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = os.environ.get("ARCHIPELAGO_CANDIDATE_PASSAGES_SHA256", "").strip().lower()
        if not expected_sha:
            manifest_path = HERE.parent / "docs" / "reports" / "D10_S4_CANDIDATE_PASSAGE_MANIFEST.json"
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest_sha = str(manifest.get("passage_index_sha256") or "").strip().lower()
                    if manifest_sha and actual_sha == manifest_sha:
                        expected_sha = manifest_sha
                except (OSError, ValueError):
                    pass
        if expected_sha and actual_sha != expected_sha:
            self.candidate_passages_info = {
                "loaded": False,
                "count": 0,
                "document_count": 0,
                "sha256": actual_sha,
                "expected_sha256": expected_sha,
                "checksum_verified": False,
                "source": source,
                "error": "checksum_mismatch",
            }
            return
        loaded_count = 0
        loaded_docs: set[str] = set()
        # Split strictly on LF (\n) so PDF form-feeds (\x0c) or Unicode line separators
        # inside JSON strings are never misinterpreted as JSONL record boundaries.
        for line in raw_bytes.decode("utf-8", errors="replace").split("\n"):
            if not line.strip():
                continue
            try:
                passage = json.loads(line)
                doc_id = str(passage["doc_id"])
                page = int(passage["page_number"])
                text = str(passage["text"])
            except (ValueError, KeyError, TypeError):
                continue
            if page < 1 or not doc_id or not text.strip():
                continue
            self.passages.append(
                {
                    "concept_id": "",
                    "doc_id": doc_id,
                    "page": page,
                    "text": text,
                    "tokens": _tokens(text),
                    "passage_id": str(passage.get("passage_id") or ""),
                    "printed_page": passage.get("printed_page"),
                    "pdf_page_index": passage.get("pdf_page_index"),
                    "text_offset_start": passage.get("text_offset_start"),
                    "text_offset_end": passage.get("text_offset_end"),
                }
            )
            loaded_count += 1
            loaded_docs.add(doc_id)
        self.candidate_passages_info = {
            "loaded": loaded_count > 0,
            "count": loaded_count,
            "document_count": len(loaded_docs),
            "sha256": actual_sha,
            "expected_sha256": expected_sha or None,
            "checksum_verified": bool(expected_sha and actual_sha == expected_sha),
            "source": source,
        }

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
            if (
                hint
                and hint not in passage["doc_id"].lower()
                and passage["doc_id"].split("/")[-1].lower() not in hint
            ):
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
        hf_ok = hf is not None and (
            hf_score >= 2 or any(len(tok) >= 8 and tok in hf["tokens"] for tok in _tokens(query))
        )
        book_ok = book is not None and (
            book_score >= 2
            or any(
                len(tok) >= 8 and tok in _tokens(book.get("title") or "") for tok in _tokens(query)
            )
        )
        if hf_ok and (not book_ok or hf_score >= book_score):
            return self._hf_reply(query, hf)
        if book_ok:
            return self._pearson_reply(query, book)
        return None

    def _hf_reply(self, query: str, item: dict) -> dict:
        passage = self.best_passage(query, item["path"]) or self.best_passage(query, item["title"])
        requested = requested_page(query)
        if passage and requested and requested != int(passage["page"]):
            passage = None
        page = int(passage["page"]) if passage else None
        url = paper_url(item["path"], requested or page)
        excerpt = " ".join((passage["text"] if passage else "").split())[:420]
        if excerpt:
            body = f"**{item['title']}.** {excerpt}"
        else:
            body = (
                f"**{item['title']}.** This file is in the Hugging Face library dataset. "
                "No scanned passage is indexed beyond the file itself, so the reply does not invent a chapter."
            )
        text = "\n\n".join(
            [
                body,
                (
                    f"**Verified PDF page.** [{item['title']} p.{page}]({url})"
                    if page
                    else f"**Document access.** [Open {item['title']}]({url}); exact supporting page not verified."
                ),
            ]
        )
        return {
            "text": text,
            "citation": {
                "label": f"[S1: {item['path'].split('/')[-1]}{f', #page={page}' if page else ''}]",
                "doc_id": item["path"],
                "page_number": page,
                "printed_page": passage.get("printed_page") if passage else None,
                "passage_id": passage.get("passage_id") if passage else None,
                "chunk_id": passage.get("passage_id") if passage else None,
                "pdf_page_index": passage.get("pdf_page_index") if passage else None,
                "text_offset_start": passage.get("text_offset_start") if passage else None,
                "text_offset_end": passage.get("text_offset_end") if passage else None,
                "url": url,
                "pdf_url": url,
            },
        }

    def _pearson_reply(self, query: str, book: dict) -> dict:
        title = book.get("title") or "Pearson book"
        author = book.get("author") or "Institutional collection"
        page_count = int(book.get("page_count") or 0)
        passage = self.best_passage(query, title)
        requested = requested_page(query)
        if passage and requested and requested != int(passage["page"]):
            passage = None
        if requested and page_count and requested > page_count:
            requested = None
            passage = None
        page = int(passage["page"]) if passage else None
        url = pearson_open(book.get("id") or "", requested or page)
        if passage:
            excerpt = " ".join(passage["text"].split())[:420]
            body = f"**{title}.** {author}. {excerpt}"
        else:
            body = (
                f"**{title}.** {author}. Pearson e-book. "
                "This reply uses the catalog record. It does not invent a chapter that is not indexed."
            )
        text = "\n\n".join(
            [
                body,
                (
                    f"**Verified e-book page.** [{title} p.{page}]({url})"
                    if page
                    else f"**E-book access.** [Open {title}]({url}); exact supporting page not verified."
                ),
            ]
        )
        return {
            "text": text,
            "citation": {
                "label": f"[S1: {title}{f', #page={page}' if page else ''}]",
                "doc_id": book.get("id") or "",
                "page_number": page,
                "printed_page": None,
                "url": url,
                "pdf_url": url,
                "book_id": book.get("id"),
                "is_pearson": True,
            },
        }
