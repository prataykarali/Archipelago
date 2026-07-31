#!/usr/bin/env python3
"""Build a copyright-compliant chunk set from _pdf_chunks.json.

Per the 2026-07-21 stakeholder meeting, book uploads must be limited to
metadata: index pages, content (TOC) pages, subheadings, and author details —
no body text. Research papers stay in full (approved priority content).

For each book this keeps:
  * chunks whose section/file name marks them as index or table of contents
  * one synthetic "structure" chunk per source PDF, listing the doc title,
    edition and the ordered unique section headings (TOC reconstruction) —
    headings are metadata, not expressive text.

Everything else (chapters, prefaces, forewords, appendix prose) is dropped.

Also merges open-access pilot papers from pdfs/papers/ (arXiv etc.) so the
pilot can demo paper retrieval (meeting target: ~10–15 papers).

Usage:
    python scripts/build_compliant_corpus.py [-o OUT.json]
"""
import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

SRC = BASE / "pdfs" / "archipelago-books-cs" / "_pdf_chunks.json"
OPEN_ACCESS_PAPERS_DIR = BASE / "pdfs" / "papers"

# Only structural/metadata sections are compliant. Prefaces and forewords are
# expressive text and are excluded on purpose.
KEEP_SECTION = re.compile(r"^\s*(index|contents|table of contents)\s*$", re.I)
KEEP_FILE = re.compile(r"(^|[-_])(index|contents|toc)([-_.]|$)", re.I)

MAX_HEADINGS_PER_STRUCT = 80  # keep synthetic chunks within model context


def is_metadata_chunk(chunk: dict) -> bool:
    if KEEP_SECTION.match(chunk.get("section_title") or ""):
        return True
    return bool(KEEP_FILE.search(Path(chunk["doc_id"]).stem))


def _normalize_chunk(c: dict) -> dict:
    """Ensure text field is present (pipeline accepts text or text_passage)."""
    if not c.get("text") and c.get("text_passage"):
        c = {**c, "text": c["text_passage"]}
    return c


def load_open_access_paper_chunks(max_chunks_per_paper: int = 15) -> list:
    """Chunk open-access PDFs under pdfs/papers/ (full text allowed).

    Caps chunks per paper so pilot extraction finishes in reasonable time while
    still covering abstract/intro/core sections (meeting: ~10–15 papers).
    """
    if not OPEN_ACCESS_PAPERS_DIR.is_dir():
        return []
    try:
        from archipelago.ingestion.pdf_io import ingest_folder
    except Exception as e:
        print(f"  [warn] cannot import pdf_io for pilot papers: {e}")
        return []
    raw = ingest_folder(str(OPEN_ACCESS_PAPERS_DIR))
    by_doc: dict[str, list] = OrderedDict()
    for c in raw:
        # Prefer prose for concept extraction; skip pure ref tables when capped.
        kind = (c.get("chunk_kind") or "").lower()
        if kind and kind not in ("prose", "body", "text", ""):
            # keep a few non-prose only if we have room later
            pass
        doc_id = c.get("doc_id") or c.get("source") or ""
        if not str(doc_id).startswith("papers/"):
            name = Path(doc_id).name if doc_id else Path(c.get("path", "unknown.pdf")).name
            doc_id = f"papers/{name}"
            c = {**c, "doc_id": doc_id}
        by_doc.setdefault(doc_id, []).append(_normalize_chunk(c))

    out = []
    for doc_id, doc_chunks in by_doc.items():
        # Prefer prose chunks first, then fill with the rest up to the cap.
        prose = [c for c in doc_chunks if (c.get("chunk_kind") or "prose") in ("prose", "body", "text", "")]
        other = [c for c in doc_chunks if c not in prose]
        selected = (prose + other)[:max_chunks_per_paper]
        out.extend(selected)
    return out


def build(out_path: str, max_oa_chunks_per_paper: int = 15, max_structure_chunks: int | None = None):
    chunks = json.load(open(SRC))
    papers = [_normalize_chunk(c) for c in chunks if c["doc_id"].startswith("papers/")]
    books = [c for c in chunks if not c["doc_id"].startswith("papers/")]

    kept_meta = [_normalize_chunk(c) for c in books if is_metadata_chunk(c)]

    # Synthetic TOC chunks: ordered unique section headings per source PDF.
    by_doc = OrderedDict()
    for c in books:
        by_doc.setdefault(c["doc_id"], []).append(c)

    structure_chunks = []
    for doc_id, doc_chunks in by_doc.items():
        headings = list(OrderedDict.fromkeys(
            (c.get("section_title") or "").strip()
            for c in doc_chunks if (c.get("section_title") or "").strip()
        ))[:MAX_HEADINGS_PER_STRUCT]
        if not headings:
            continue
        first = doc_chunks[0]
        title = first.get("doc_title") or doc_id.split("/")[0]
        lines = [f"Book: {title}"]
        if first.get("edition"):
            lines.append(f"Edition: {first['edition']}")
        lines.append(f"Chapter file: {Path(doc_id).stem}")
        lines.append("Contents / section headings:")
        lines += [f"  - {h}" for h in headings]
        structure_chunks.append({
            **{k: first.get(k) for k in
               ("doc_id", "doc_hash", "page_count", "doc_title", "edition")},
            "chunk_id": f"{Path(doc_id).stem}__structure",
            "section_title": "Contents (structure metadata)",
            "page_number": first.get("page_number", 1),
            "text": "\n".join(lines),
        })

    # One structure chunk per book folder is enough for pilot demos; full per-file
    # structure list is large and mostly redundant for concept extraction.
    if max_structure_chunks is not None and len(structure_chunks) > max_structure_chunks:
        # Keep one structure chunk per top-level book folder.
        seen_folders = set()
        slim = []
        for sc in structure_chunks:
            folder = sc["doc_id"].split("/")[0]
            if folder in seen_folders:
                continue
            seen_folders.add(folder)
            slim.append(sc)
        structure_chunks = slim[:max_structure_chunks]

    # Open-access arXiv / pilot papers (full text — meeting priority content)
    oa_papers = load_open_access_paper_chunks(max_chunks_per_paper=max_oa_chunks_per_paper)
    existing_paper_docs = {c["doc_id"] for c in papers}
    oa_new = [c for c in oa_papers if c.get("doc_id") not in existing_paper_docs]
    papers = papers + oa_new

    # Cap the single large HF paper too (still full-text, just pilot-sized)
    paper_by_doc: dict[str, list] = OrderedDict()
    for c in papers:
        paper_by_doc.setdefault(c["doc_id"], []).append(c)
    papers_capped = []
    for doc_id, doc_chunks in paper_by_doc.items():
        if len(doc_chunks) > max_oa_chunks_per_paper * 2:
            papers_capped.extend(doc_chunks[: max_oa_chunks_per_paper * 2])
        else:
            papers_capped.extend(doc_chunks)
    papers = papers_capped

    out = papers + kept_meta + structure_chunks
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w"), indent=1)

    n_book_docs = len(by_doc)
    n_paper_docs = len({c["doc_id"] for c in papers})
    n_book_folders = len({d.split("/")[0] for d in by_doc})
    print(f"source chunks          : {len(chunks)}")
    print(f"kept paper chunks      : {len(papers)}  across {n_paper_docs} paper docs (full text — approved)")
    print(f"  of which open-access : {len(oa_new)} new chunks from pdfs/papers/")
    print(f"kept book index/TOC    : {len(kept_meta)}")
    print(f"synthetic TOC chunks   : {len(structure_chunks)} (from {n_book_docs} book files / {n_book_folders} books)")
    print(f"dropped book body text : {len(books) - len(kept_meta)}")
    print(f"compliant total        : {len(out)} -> {out_path}")
    print(f"\nJul 21 pilot alignment : books={n_book_folders} (index/TOC only), papers={n_paper_docs}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(BASE / "pilot_corpus" / "_compliant_chunks.json"))
    ap.add_argument("--max-oa-chunks", type=int, default=15,
                    help="Max chunks per open-access paper (default 15)")
    ap.add_argument("--max-structure", type=int, default=10,
                    help="Max synthetic TOC structure chunks (default 10; one per book is enough)")
    args = ap.parse_args()
    build(args.out, max_oa_chunks_per_paper=args.max_oa_chunks,
          max_structure_chunks=args.max_structure)
