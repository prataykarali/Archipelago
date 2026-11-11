"""Upload the prepared pilot corpus to Hugging Face."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

from scripts.pilot_corpus_books import BOOKS
from scripts.pilot_corpus_papers import PAPERS

BASE = Path(__file__).resolve().parent.parent
PAPERS_DIR = BASE / "pdfs" / "papers"
BOOKS_BASE = BASE / "pdfs" / "archipelago-books-cs"
HF_TOKEN = os.environ.get("HF_TOKEN")
HF_REPO = "Prataykarali/archipelago-books-cs"


def upload_to_huggingface():
    """Upload new papers, book directories, and manifest to HF dataset."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("  ✗ huggingface_hub not installed. Install: pip install huggingface_hub")
        return

    print("\n" + "=" * 70)
    print("  ☁️  Uploading to HuggingFace")
    print(f"  Repo: {HF_REPO}")
    print("=" * 70)

    api = HfApi(token=HF_TOKEN)
    uploaded, failed = 0, 0

    # Upload papers
    for paper in PAPERS:
        local = PAPERS_DIR / paper["filename"]
        if not local.exists():
            continue
        hf_path = f"papers/{paper['filename']}"
        try:
            api.upload_file(
                path_or_fileobj=str(local),
                path_in_repo=hf_path,
                repo_id=HF_REPO,
                repo_type="dataset",
            )
            print(f"  ✓ Uploaded paper: {paper['filename']}")
            uploaded += 1
        except Exception as e:
            print(f"  ✗ Failed paper {paper['filename']}: {e}")
            failed += 1

    # Upload book directories (metadata + any PDFs)
    for book in BOOKS:
        book_dir = BOOKS_BASE / book["dirname"]
        if not book_dir.exists():
            continue
        for f in book_dir.iterdir():
            if f.is_file():
                hf_path = f"{book['dirname']}/{f.name}"
                try:
                    api.upload_file(
                        path_or_fileobj=str(f),
                        path_in_repo=hf_path,
                        repo_id=HF_REPO,
                        repo_type="dataset",
                    )
                    uploaded += 1
                except Exception as e:
                    print(f"  ✗ Failed {f.name}: {e}")
                    failed += 1

    # Upload manifest
    manifest_path = BOOKS_BASE / "CORPUS_MANIFEST.json"
    if manifest_path.exists():
        try:
            api.upload_file(
                path_or_fileobj=str(manifest_path),
                path_in_repo="CORPUS_MANIFEST.json",
                repo_id=HF_REPO,
                repo_type="dataset",
            )
            print("  ✓ Uploaded CORPUS_MANIFEST.json")
            uploaded += 1
        except Exception as e:
            print(f"  ✗ Manifest upload failed: {e}")
            failed += 1

    # Update INVENTORY.json
    inv = {
        "hf_dataset": HF_REPO,
        "books_count": 5 + len(BOOKS),  # 5 existing + 6 new
        "paper_count": len(PAPERS),
        "books_existing": [
            "artificial_intelligence_a_new_synthesis_1998 (36)",
            "data_science_2019 (25)",
            "knowledge_representation_and_reasoning_2004 (21)",
            "pattern_recognition_2009 (23)",
            "predictive_analytics_and_data_mining_2015 (22)",
        ],
        "books_new": [b["dirname"] for b in BOOKS],
        "paper_clusters": {
            "01_foundations": 4,
            "02_transformers_llms": 6,
            "03_peft_systems": 4,
            "04_rag_graph": 5,
            "05_generative_alignment": 6,
        },
        "subjects": [
            "Database Management Systems",
            "Data Structures and Algorithms",
            "Operating Systems",
            "AI/ML (pilot corpus)",
        ],
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    inv_path = BOOKS_BASE / "INVENTORY.json"
    with open(inv_path, "w") as f:
        json.dump(inv, f, indent=2)
    try:
        api.upload_file(
            path_or_fileobj=str(inv_path),
            path_in_repo="INVENTORY.json",
            repo_id=HF_REPO,
            repo_type="dataset",
        )
        uploaded += 1
    except Exception:
        pass

    print(f"\n  Upload complete: {uploaded} uploaded, {failed} failed")
    print(f"  👉 https://huggingface.co/datasets/{HF_REPO}")
