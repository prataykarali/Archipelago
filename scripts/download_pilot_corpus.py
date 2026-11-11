#!/usr/bin/env python3
"""
download_pilot_corpus.py — Download papers & create book directories for
the Archipelago pilot project, then upload to HuggingFace.

Papers: 25 total (5 existing + 20 new) in 5 conceptual clusters
Books:  6 CS textbooks (DBMS x2, DSA x2, OS x2)

Usage:
    python scripts/download_pilot_corpus.py                     # download only
    python scripts/download_pilot_corpus.py --upload-hf         # download + upload to HF
    python scripts/download_pilot_corpus.py --skip-download     # upload existing files only
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.request

BASE = Path(__file__).resolve().parent.parent
PAPERS_DIR = BASE / "pdfs" / "papers"
BOOKS_BASE = BASE / "pdfs" / "archipelago-books-cs"

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_REPO = "Prataykarali/archipelago-books-cs"

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from scripts.pilot_corpus_books import BOOKS  # noqa: E402
from scripts.pilot_corpus_papers import PAPERS  # noqa: E402
from scripts.pilot_corpus_upload import upload_to_huggingface  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ArchipelagoBot/1.0 (research; pratay.karali@uem.edu.in)",
    "Accept": "application/pdf,*/*",
}


def _download_file(url: str, dest: Path, retries: int = 3) -> bool:
    """Download a file from url to dest with retries. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  ✓ Already exists: {dest.name} ({dest.stat().st_size:,} bytes)")
        return True

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                data = resp.read()

            if len(data) < 1000:
                print(f"  ⚠ Too small ({len(data)} bytes) from {url}")
                return False

            if dest.name.endswith(".pdf") and not data.startswith(b"%PDF-"):
                print(f"  ⚠ Invalid PDF header (received HTML/error response) from {url}")
                return False

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(f"  ✓ Downloaded: {dest.name} ({len(data):,} bytes)")
            return True

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            print(f"  ⚠ Attempt {attempt}/{retries} failed for {dest.name}: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)  # backoff

    return False


# ═══════════════════════════════════════════════════════════════════════
# Phase 1: Download papers
# ═══════════════════════════════════════════════════════════════════════


def download_papers() -> dict:
    """Download all papers to pdfs/papers/. Returns stats."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    ok, skip, fail = 0, 0, 0

    print("\n" + "=" * 70)
    print("  📄 Downloading Research Papers")
    print("=" * 70)

    for paper in PAPERS:
        name = paper["filename"]
        dest = PAPERS_DIR / name

        if paper.get("exists") and dest.exists() and dest.stat().st_size > 1000:
            print(f"  ✓ Exists: {name}")
            skip += 1
            continue

        success = False
        for url in paper["urls"]:
            if _download_file(url, dest):
                success = True
                break
            time.sleep(1)  # be polite between URL attempts

        if success:
            ok += 1
        else:
            fail += 1
            print(f"  ✗ FAILED: {name}")

        time.sleep(1.5)  # rate limiting between papers

    stats = {"downloaded": ok, "skipped": skip, "failed": fail}
    print(f"\n  Papers: {ok} downloaded, {skip} skipped, {fail} failed")
    return stats


# ═══════════════════════════════════════════════════════════════════════
# Phase 2: Create book directories with metadata
# ═══════════════════════════════════════════════════════════════════════


def prepare_books() -> dict:
    """Create book directories with metadata JSON files.

    For open-access books (OSTEP), also downloads chapters.
    For copyrighted books, creates placeholder metadata.
    """
    print("\n" + "=" * 70)
    print("  📚 Preparing Book Directories")
    print("=" * 70)

    ok, chapters_dl = 0, 0
    need_user_pdfs = []

    for book in BOOKS:
        book_dir = BOOKS_BASE / book["dirname"]
        book_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata JSON
        meta = {
            "title": book["title"],
            "authors": book["authors"],
            "publisher": book["publisher"],
            "subject": book["subject"],
            "requires": book["requires"],
            "unlocks": book["unlocks"],
            "open_access": book["open_access"],
            "compliance_note": "Per Jul 21 meeting: only index, TOC, content pages, "
            "subheadings, and author info will be extracted — NO body text.",
        }
        meta_path = book_dir / "METADATA.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"\n  📁 {book['dirname']}/")
        print(f"     Title: {book['title']}")
        print(f"     Authors: {book['authors']}")
        print(f"     Subject: {book['subject']}")

        # Download OSTEP chapters (open-access)
        if book.get("ostep_chapters"):
            print(f"     Downloading {len(book['ostep_chapters'])} OSTEP chapters...")
            for url, chap_name in book["ostep_chapters"]:
                dest = book_dir / chap_name
                if _download_file(url, dest):
                    chapters_dl += 1
                time.sleep(0.5)

        elif not book["open_access"]:
            # Create README for user to add PDFs
            readme = (
                f"# {book['title']}\n\n"
                f"**Authors:** {book['authors']}\n"
                f"**Publisher:** {book['publisher']}\n"
                f"**Subject:** {book['subject']}\n\n"
                f"## 📥 Action Required\n\n"
                f"This is a copyrighted textbook. Please add the PDF file(s) to this directory.\n"
                f"Per the Jul 21 meeting rules, only **index, TOC, content pages, subheadings,\n"
                f"and author info** will be extracted — no body text.\n\n"
                f"## Graph Concepts\n"
                f"- REQUIRES: {', '.join(book['requires'])}\n"
                f"- UNLOCKS: {', '.join(book['unlocks'])}\n"
            )
            (book_dir / "README.md").write_text(readme)
            need_user_pdfs.append(book["title"])

        ok += 1

    if need_user_pdfs:
        print(f"\n  ⚠ {len(need_user_pdfs)} books need PDFs from you:")
        for t in need_user_pdfs:
            print(f"    • {t}")

    stats = {
        "books_prepared": ok,
        "chapters_downloaded": chapters_dl,
        "need_user_pdfs": len(need_user_pdfs),
    }
    return stats


# ═══════════════════════════════════════════════════════════════════════
# Phase 3: Build categorization manifest
# ═══════════════════════════════════════════════════════════════════════


def build_manifest() -> dict:
    """Build a comprehensive CORPUS_MANIFEST.json for the pilot."""
    manifest = {
        "project": "Archipelago Pilot — Jul 21 2026",
        "hf_dataset": HF_REPO,
        "compliance": {
            "books": "Index, TOC, content pages, subheadings, author info ONLY. No body text.",
            "papers": "Full text allowed (priority content).",
            "scope": "3 subjects (DBMS, DSA, OS) + AI/ML pilot, 6 new books, 25 papers.",
        },
        "paper_clusters": {},
        "books_by_subject": {},
        "papers_total": 0,
        "books_total": 0,
    }

    # Papers
    clusters: dict[str, list] = {}
    for p in PAPERS:
        cl = p["cluster"]
        clusters.setdefault(cl, []).append(
            {
                "filename": p["filename"],
                "title": p["title"],
                "authors": p["authors"],
                "year": p["year"],
                "requires": p["requires"],
                "unlocks": p["unlocks"],
                "exists_locally": (PAPERS_DIR / p["filename"]).exists(),
            }
        )
    manifest["paper_clusters"] = clusters
    manifest["papers_total"] = len(PAPERS)

    # Books
    by_subject: dict[str, list] = {}
    for b in BOOKS:
        subj = b["subject"]
        book_dir = BOOKS_BASE / b["dirname"]
        pdf_count = len(list(book_dir.glob("*.pdf"))) if book_dir.exists() else 0
        by_subject.setdefault(subj, []).append(
            {
                "dirname": b["dirname"],
                "title": b["title"],
                "authors": b["authors"],
                "publisher": b["publisher"],
                "open_access": b["open_access"],
                "pdfs_present": pdf_count,
                "requires": b["requires"],
                "unlocks": b["unlocks"],
            }
        )
    manifest["books_by_subject"] = by_subject
    manifest["books_total"] = len(BOOKS)

    # Domain bridges
    manifest["domain_bridges"] = [
        {
            "bridge": "B+ Trees & Disk Indexing",
            "path": "Weiss (DSA) → Silberschatz (DBMS) → OSTEP (OS Storage)",
        },
        {
            "bridge": "Concurrency & Deadlocks",
            "path": "Silberschatz (OS) → Ramakrishnan (DBMS Concurrency Control)",
        },
        {
            "bridge": "Graph Traversals",
            "path": "CLRS (DSA) → KùzuDB / Network Science / AI Graph RAG",
        },
    ]

    manifest_path = BOOKS_BASE / "CORPUS_MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n  📋 Manifest saved: {manifest_path}")
    return manifest


# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    ap = argparse.ArgumentParser(description="Download pilot corpus & upload to HuggingFace")
    ap.add_argument("--upload-hf", action="store_true", help="Upload to HuggingFace after download")
    ap.add_argument(
        "--skip-download", action="store_true", help="Skip downloads, upload existing only"
    )
    args = ap.parse_args()

    print("=" * 70)
    print("  🏝️  Archipelago Pilot Corpus Builder")
    print("  Jul 21 2026 — Compliant with meeting rules")
    print("=" * 70)
    print(f"  Papers dir : {PAPERS_DIR}")
    print(f"  Books base : {BOOKS_BASE}")
    print(f"  HF repo    : {HF_REPO}")

    if not args.skip_download:
        download_papers()
        prepare_books()
    else:
        pass

    build_manifest()

    if args.upload_hf:
        upload_to_huggingface()

    # Final summary
    print("\n" + "=" * 70)
    print("  📊 Summary")
    print("=" * 70)
    existing = sum(1 for p in PAPERS if (PAPERS_DIR / p["filename"]).exists())
    print(f"  Papers ready: {existing}/{len(PAPERS)}")
    for cl_name in sorted({p["cluster"] for p in PAPERS}):
        cl_papers = [p for p in PAPERS if p["cluster"] == cl_name]
        ready = sum(1 for p in cl_papers if (PAPERS_DIR / p["filename"]).exists())
        print(f"    {cl_name}: {ready}/{len(cl_papers)}")

    books_with_pdfs = 0
    for b in BOOKS:
        d = BOOKS_BASE / b["dirname"]
        if d.exists() and list(d.glob("*.pdf")):
            books_with_pdfs += 1
    print(f"\n  Books with PDFs: {books_with_pdfs}/{len(BOOKS)}")
    for b in BOOKS:
        d = BOOKS_BASE / b["dirname"]
        n = len(list(d.glob("*.pdf"))) if d.exists() else 0
        icon = "✓" if n > 0 else "⚠"
        note = f"({n} PDFs)" if n > 0 else "(needs PDFs from you)"
        oa = " [Open Access]" if b["open_access"] else ""
        print(f"    {icon} {b['title']}{oa} {note}")

    if not args.upload_hf:
        print("\n  💡 Run with --upload-hf to push to HuggingFace")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
