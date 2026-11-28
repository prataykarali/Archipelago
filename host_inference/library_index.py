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
CORPUS_V3_ID = "corpus_v3_d14"
CORPUS_V2_ID = "corpus_v2_d10_3025"
ENV_CORPUS_VERSION = "ARCHIPELAGO_CORPUS_VERSION"
V3_PASSAGES_FILENAME = "d14_candidate_passages_v3.jsonl"
V2_PASSAGES_FILENAME = "d10_candidate_passages.jsonl"
V3_MANIFEST_REL = Path("docs") / "reports" / "d14" / "D14_CORPUS_V3_MANIFEST.json"
V2_MANIFEST_REL = Path("docs") / "reports" / "D10_S4_CANDIDATE_PASSAGE_MANIFEST.json"
V3_ARTIFACTS_REL = Path("data") / "artifacts" / "corpus_v3_d14" / V3_PASSAGES_FILENAME
_V2_ALIASES = frozenset({CORPUS_V2_ID, "v2", "v2_d10", "d10", "d5-775"})


def resolve_candidate_passages_path(here: Path = HERE) -> tuple[Path | None, str, str]:
    """Resolve versioned candidate passages JSONL path, source label, and corpus version.

    Defaults to ``corpus_v3_d14`` when available while preserving ``corpus_v2_d10_3025``
    as an explicit rollback target via ``ARCHIPELAGO_CORPUS_VERSION=corpus_v2_d10_3025``.
    """
    env_path = os.environ.get("ARCHIPELAGO_CANDIDATE_PASSAGES", "").strip()
    if env_path.lower() in {"0", "false", "none"}:
        return None, "disabled", ""
    if env_path:
        path = Path(env_path)
        ver = CORPUS_V3_ID if "v3" in path.name.lower() or "d14" in path.name.lower() else CORPUS_V2_ID
        return path, "env_path", ver

    env_version = os.environ.get(ENV_CORPUS_VERSION, "").strip().lower()
    v2_cache = here / "cache" / V2_PASSAGES_FILENAME
    if env_version in _V2_ALIASES:
        return (v2_cache, "local_cache_v2", CORPUS_V2_ID) if v2_cache.is_file() else (None, "remote", CORPUS_V2_ID)

    v3_candidates = (
        (here.parent / V3_ARTIFACTS_REL, "local_v3_artifacts"),
        (here / "cache" / V3_PASSAGES_FILENAME, "local_cache_v3"),
    )
    for candidate, src_label in v3_candidates:
        if candidate.is_file():
            return candidate, src_label, CORPUS_V3_ID

    if v2_cache.is_file():
        return v2_cache, "local_cache_v2", CORPUS_V2_ID
    return None, "remote", env_version or CORPUS_V3_ID


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
    from hf_revision import dataset_revision

    url = f"https://huggingface.co/api/datasets/{repo}/tree/{dataset_revision(repo)}?recursive=true"
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

    # Only perform live HF Hub tree fetches when local/manifest paths are absent,
    # avoiding up to 16s of synchronous cold-start blocking on Vercel.
    if token and not path_to_repo:
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
            "corpus_version": None,
        }
        self._retriever_cache: tuple[int, object] | None = None
        candidate_index = os.environ.get("ARCHIPELAGO_CANDIDATE_PASSAGES", "").strip()
        if candidate_index or not os.environ.get("PYTEST_CURRENT_TEST"):
            resolved_path, resolved_src, resolved_ver = resolve_candidate_passages_path(HERE)
            if resolved_path is not None:
                self._load_candidate_passages(
                    resolved_path, source=resolved_src, corpus_version=resolved_ver
                )
            elif resolved_src == "remote":
                self._load_remote_candidate_passages()

    def get_retriever(self) -> object | None:
        """Return a lazily cached HybridPassageRetriever over ``self.passages``."""
        count = len(self.passages)
        if count == 0:
            return None
        if self._retriever_cache is not None and self._retriever_cache[0] == count:
            return self._retriever_cache[1]
        try:
            from archipelago.inference.dense_retriever import HybridPassageRetriever
        except ImportError:
            return None
        corpus_ver = str(self.candidate_passages_info.get("corpus_version") or CORPUS_V2_ID)
        retriever = HybridPassageRetriever(self.passages, corpus_version=corpus_ver)
        self._retriever_cache = (count, retriever)
        return retriever

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
        cache_key = hashlib.sha256(storage_object.encode("utf-8")).hexdigest()[:12]
        cache_path = Path(f"/tmp/archipelago_candidate_passages_{cache_key}.jsonl")
        if not cache_path.is_file():
            try:
                resp = requests.get(
                    f"{url}/storage/v1/object/{storage_object.lstrip('/')}",
                    headers={"apikey": key, "Authorization": f"Bearer {key}"},
                    timeout=(3.0, 20.0),
                )
                if resp.status_code != 200 or not resp.content:
                    self.candidate_passages_info["error"] = f"remote_http_{resp.status_code}"
                    return
                cache_path.write_bytes(resp.content)
            except (requests.RequestException, OSError):
                self.candidate_passages_info["error"] = "remote_fetch_failed"
                return
        ver = CORPUS_V3_ID if "v3" in storage_object.lower() or "d14" in storage_object.lower() else CORPUS_V2_ID
        self._load_candidate_passages(cache_path, source="supabase_storage", corpus_version=ver)

    def _load_candidate_passages(
        self, index_path: Path, *, source: str = "local", corpus_version: str = ""
    ) -> None:
        """Add rights-approved, deterministic PDF body chunks to catalog retrieval."""
        if not index_path.is_file():
            return
        raw_bytes = index_path.read_bytes()
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = os.environ.get("ARCHIPELAGO_CANDIDATE_PASSAGES_SHA256", "").strip().lower()
        detected_version = corpus_version
        if not expected_sha:
            for manifest_rel, ver_id in (
                (V3_MANIFEST_REL, CORPUS_V3_ID),
                (V2_MANIFEST_REL, CORPUS_V2_ID),
            ):
                manifest_path = HERE.parent / manifest_rel
                if not manifest_path.is_file():
                    continue
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest_sha = str(manifest.get("passage_index_sha256") or "").strip().lower()
                    if manifest_sha and actual_sha == manifest_sha:
                        expected_sha = manifest_sha
                        detected_version = str(manifest.get("corpus_version") or ver_id)
                        break
                except (OSError, ValueError):
                    continue
        if expected_sha and actual_sha != expected_sha:
            self.candidate_passages_info = {
                "loaded": False,
                "count": 0,
                "document_count": 0,
                "sha256": actual_sha,
                "expected_sha256": expected_sha,
                "checksum_verified": False,
                "source": source,
                "corpus_version": detected_version or None,
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
            rec_version = str(passage.get("corpus_version") or "").strip()
            if rec_version and not detected_version:
                detected_version = rec_version
            concept_ids = passage.get("concept_ids")
            primary_cid = (
                str(concept_ids[0])
                if isinstance(concept_ids, list) and concept_ids
                else str(passage.get("concept_id") or "")
            )
            self.passages.append(
                {
                    "concept_id": primary_cid,
                    "concept_ids": list(concept_ids) if isinstance(concept_ids, list) else [],
                    "doc_id": doc_id,
                    "page": page,
                    "text": text,
                    "tokens": _tokens(text),
                    "passage_id": str(passage.get("passage_id") or ""),
                    "printed_page": passage.get("printed_page"),
                    "pdf_page_index": passage.get("pdf_page_index"),
                    "text_offset_start": passage.get("text_offset_start"),
                    "text_offset_end": passage.get("text_offset_end"),
                    "corpus_version": rec_version or detected_version or CORPUS_V2_ID,
                    "domain": str(passage.get("domain") or ""),
                    "secondary_domains": list(passage.get("secondary_domains") or []),
                    "source_title": str(passage.get("source_title") or ""),
                    "authors": str(passage.get("authors") or ""),
                    "section_title": str(passage.get("section_title") or ""),
                    "structural_class": str(passage.get("structural_class") or "BODY"),
                    "quality_score": passage.get("quality_score"),
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
            "corpus_version": detected_version or CORPUS_V2_ID,
        }
        self._retriever_cache = None

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
