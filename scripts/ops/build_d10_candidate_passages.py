"""Build a local, deterministic PDF passage index from the approved HF inventory.

The output contains source text and must stay outside Git. No concept or graph
relation is inferred or published by this command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import fitz
from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "data/catalogs/hf_dataset_manifest.json"
REPO_ID = "Prataykarali/Library_books"
LIBRARY_REVISION = "b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd"
GRAPH_PATH = ROOT / "host_inference/fixtures/okf_graph.json"
MAX_PASSAGE_CHARS = 1600
PDF_SUFFIX = ".pdf"
APPROVED_PREFIXES = (
    "books/papers/",
    "books/textbooks/",
    "archipelago-books-cs/ostep_three_easy_pieces/",
)


def approved_paths() -> list[str]:
    """Return the canonical approved PDFs, excluding mirrors and test uploads."""
    manifest = json.loads(INVENTORY.read_text(encoding="utf-8"))
    paths = sorted(
        path
        for path in manifest["files"]
        if path.startswith(APPROVED_PREFIXES) and path.endswith(PDF_SUFFIX)
    )
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate canonical PDF path in approved inventory")
    return paths


def sha256_file(path: Path) -> str:
    """Hash a file without loading all of it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_pdf(path: Path, doc_id: str, pdf_sha256: str) -> list[dict[str, Any]]:
    """Extract fixed-size chunks confined to one physical PDF page."""
    passages: list[dict[str, Any]] = []
    with fitz.open(path) as document:
        has_labels = bool(document.get_page_labels())
        for page_index in range(document.page_count):
            page = document[page_index]
            text = page.get_text("text")
            for start in range(0, len(text), MAX_PASSAGE_CHARS):
                raw = text[start : start + MAX_PASSAGE_CHARS]
                if not raw.strip():
                    continue
                passages.append(
                    {
                        "doc_id": doc_id,
                        "pdf_sha256": pdf_sha256,
                        "passage_id": f"{pdf_sha256[:12]}:p{page_index + 1}:c{start}",
                        "page_number": page_index + 1,
                        "pdf_page_index": page_index,
                        "printed_page": page.get_label() if has_labels else None,
                        "text_offset_start": start,
                        "text_offset_end": min(start + MAX_PASSAGE_CHARS, len(text)),
                        "text": raw,
                    }
                )
    return passages


def build(output: Path, summary_path: Path, token: str) -> dict[str, Any]:
    """Download pinned approved PDFs, verify hashes, and write local passages."""
    if not token:
        raise ValueError("HF_TOKEN is required for the private approved inventory")
    paths = approved_paths()
    api = HfApi(token=token)
    repo = api.repo_info(
        REPO_ID, repo_type="dataset", revision=LIBRARY_REVISION, files_metadata=True
    )
    siblings = {item.rfilename: item for item in (repo.siblings or [])}
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    records: list[dict[str, Any]] = []
    passage_count = 0
    with temporary.open("w", encoding="utf-8") as target:
        for doc_id in paths:
            sibling = siblings.get(doc_id)
            if sibling is None:
                raise ValueError(f"Approved PDF absent at pinned revision: {doc_id}")
            local = Path(
                hf_hub_download(
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    filename=doc_id,
                    revision=LIBRARY_REVISION,
                    token=token,
                )
            )
            actual_hash = sha256_file(local)
            lfs = getattr(sibling, "lfs", None)
            expected_hash = lfs.get("sha256") if isinstance(lfs, dict) else None
            if expected_hash and actual_hash != expected_hash:
                raise ValueError(f"PDF checksum mismatch: {doc_id}")
            passages = extract_pdf(local, doc_id, actual_hash)
            for passage in passages:
                target.write(json.dumps(passage, ensure_ascii=False) + "\n")
            passage_count += len(passages)
            records.append(
                {
                    "doc_id": doc_id,
                    "sha256": actual_hash,
                    "remote_sha256_verified": bool(expected_hash),
                    "passages": len(passages),
                }
            )
    temporary.replace(output)
    report = {
        "schema": "archipelago.d10_s4_candidate_passages.v1",
        "repo_id": REPO_ID,
        "library_revision": LIBRARY_REVISION,
        "graph_sha256": sha256_file(GRAPH_PATH),
        "passage_index_sha256": sha256_file(output),
        "document_count": len(records),
        "passage_count": passage_count,
        "documents": records,
    }
    summary_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    """Build the local candidate index from command-line paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    arguments = parser.parse_args()
    result = build(arguments.output, arguments.summary, os.getenv("HF_TOKEN", "").strip())
    print(
        json.dumps(
            {
                "document_count": result["document_count"],
                "passage_count": result["passage_count"],
                "passage_index_sha256": result["passage_index_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
