"""Upload the graph and Pearson catalog to private Supabase storage and the HF dataset.

Pearson subscription ids stay in the private bucket. The HF dataset gets the
graph plus a public catalog with those ids removed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BUCKET = "archipelago-cache"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env.setdefault(key.strip(), value.strip())
    return env


def _supabase_headers(env: dict[str, str]) -> tuple[str, dict[str, str]]:
    url = env["SUPABASE_URL"].rstrip("/")
    key = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }
    return url, headers


def ensure_bucket(url: str, headers: dict[str, str]) -> None:
    response = requests.post(
        f"{url}/storage/v1/bucket",
        headers={**headers, "Content-Type": "application/json"},
        json={"id": BUCKET, "name": BUCKET, "public": False},
        timeout=30,
    )
    if response.status_code not in {200, 201, 409}:
        # 400 "already exists" is also success on some projects.
        if "exists" not in response.text.lower():
            raise SystemExit(f"bucket create failed: {response.status_code} {response.text[:180]}")


def upload_object(url: str, headers: dict[str, str], name: str, payload: bytes, content_type: str) -> None:
    response = requests.post(
        f"{url}/storage/v1/object/{BUCKET}/{name}",
        headers={**headers, "Content-Type": content_type, "x-upsert": "true"},
        data=payload,
        timeout=120,
    )
    if response.status_code not in {200, 201}:
        response = requests.put(
            f"{url}/storage/v1/object/{BUCKET}/{name}",
            headers={**headers, "Content-Type": content_type, "x-upsert": "true"},
            data=payload,
            timeout=120,
        )
    if response.status_code not in {200, 201}:
        raise SystemExit(f"upload {name} failed: {response.status_code} {response.text[:180]}")
    print(f"supabase {name} {len(payload)} bytes")


def public_catalog(books: list[dict]) -> bytes:
    slim = []
    for book in books:
        slim.append({
            "id": book.get("id"),
            "title": book.get("title"),
            "author": book.get("author"),
            "isbn": book.get("isbn"),
            "slug": book.get("slug"),
            "domain": book.get("domain"),
            "book_type": book.get("book_type"),
            "page_count": book.get("page_count"),
            "page_link_pattern": "/open/{id}?page={n}",
        })
    return json.dumps({"total_books": len(slim), "books": slim}, ensure_ascii=False).encode()


def public_library_manifest() -> bytes:
    """Export only reader-backed shelf items and separate holdings metadata.

    Raises:
        RuntimeError: when the library catalogue API is unavailable. The hosted
        image is built from ``host_inference`` alone and does not carry the
        ``archipelago`` package, so this publisher only works from the library
        workstation — better a clear error than a silently empty manifest.
    """
    try:
        from archipelago.inference.library_catalog_api import build_library_data_payload
    except ImportError as exc:
        raise RuntimeError(
            "public_library_manifest needs the archipelago package; it runs on "
            "the library workstation, not the hosted deploy"
        ) from exc

    source = build_library_data_payload(REPO)
    hf_manifest = REPO / "data" / "catalogs" / "hf_dataset_manifest.json"
    hf_payload = json.loads(hf_manifest.read_text(encoding="utf-8"))
    hf_paths = [str(path) for path in hf_payload.get("files", []) if str(path).endswith(".pdf")]
    allowed_book_fields = {
        "id", "title", "author", "year", "domain", "desc", "isbn", "isPearson",
        "isPaper", "primaryColor", "accentColor", "page_count", "toc", "pdfUrl",
        "reader_url", "resolveUrl", "isCatalogOnly", "availability", "total_copies",
        "available_copies", "shelf_location", "call_number", "library_scope",
    }
    source_shelf = list(source.get("ebook_shelf", []))
    by_id = {str(book.get("id") or ""): book for book in source_shelf}
    shelf = []
    seen_ids: set[str] = set()
    for book in source_shelf:
        if not book.get("isPearson"):
            continue
        item_id = str(book.get("id") or "")
        if item_id and item_id not in seen_ids:
            shelf.append({key: value for key, value in book.items() if key in allowed_book_fields})
            seen_ids.add(item_id)

    for path in hf_paths:
        if path in seen_ids:
            continue
        book = by_id.get(path, {})
        is_textbook = path.startswith(("textbooks/", "books/textbooks/", "archipelago-books-cs/"))
        shelf.append({
            "id": path,
            "title": book.get("title") or path.rsplit("/", 1)[-1].removesuffix(".pdf").replace("_", " "),
            "author": book.get("author") or "Archipelago Hugging Face Library",
            "year": book.get("year") or "",
            "domain": book.get("domain") or ("Textbooks & Course Material" if is_textbook else "Research Papers & Preprints"),
            "desc": "Verified Hugging Face library PDF. Opens in the cloud reader.",
            "isbn": book.get("isbn") or "",
            "isPearson": False,
            "isPaper": not is_textbook,
            "primaryColor": book.get("primaryColor") or "#7c3aed",
            "accentColor": book.get("accentColor") or "#ddd6fe",
            "page_count": book.get("page_count") or 0,
            "toc": book.get("toc") or [{"title": "Open verified source", "page": 1}],
        })
        seen_ids.add(path)
    payload = {
        "ebook_shelf": shelf,
        "hf_paths": hf_paths,
        "ebook_stats": (
            f"{len(shelf)} reader-backed titles · {len([book for book in shelf if book.get('isPearson')])} Pearson eBooks · "
            f"{len(hf_paths)} Hugging Face PDFs · {len(source.get('holdings', []))} catalog holdings"
        ),
        "holdings": source.get("holdings", []),
        "holdings_stats": source.get("holdings_stats", {}),
        "journal_issues": source.get("journal_issues", []),
        "subject_counts": source.get("subject_counts", []),
        "subject_titles": source.get("subject_titles", []),
    }
    return json.dumps(payload, ensure_ascii=False).encode()


def upload_hf(env: dict[str, str], graph: bytes, catalog: bytes) -> None:
    token = env.get("HF_TOKEN", "").strip()
    repo = env.get("HF_DATASET_REPO", "").strip()
    if not token or not repo:
        print("hf skipped")
        return
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    api.create_repo(repo, repo_type="dataset", exist_ok=True)
    for name, data in (("okf_graph.json", graph), ("pearson_public.json", catalog)):
        api.upload_file(
            path_or_fileobj=data,
            path_in_repo=name,
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"Publish inference cache {name}",
        )
        print(f"hf {repo}/{name}")


def main() -> None:
    env = _env()
    graph_path = REPO / "okf_graph.json"
    book_path = REPO / "data" / "catalogs" / "pearson_bookshelf.json"
    graph = graph_path.read_bytes()
    books = json.loads(book_path.read_text(encoding="utf-8"))
    book_bytes = json.dumps(books).encode()
    library_bytes = public_library_manifest()
    url, headers = _supabase_headers(env)
    ensure_bucket(url, headers)
    upload_object(url, headers, "okf_graph.json", graph, "application/json")
    upload_object(url, headers, "pearson_bookshelf.json", book_bytes, "application/json")
    upload_object(url, headers, "library_manifest.json", library_bytes, "application/json")
    upload_hf(env, graph, public_catalog(books.get("books") or []))
    print("Supabase cache published", len(books.get("books") or []), "Pearson books")


if __name__ == "__main__":
    main()
