#!/usr/bin/env python3
"""
Headless Kaggle GPU ingest orchestrator for LibraryAI / Archipelago.

Architecture (no local book downloads on the library machine):

  Librarian uploads PDFs
        ↓
  HF Dataset  (e.g. Prataykarali/archipelago-books-cs)
        ↓
  Kaggle GPU notebook  (fine-tuned lib-qwen GGUF extraction)
        ↓
  HF Dataset graph/  (okf_results.json, okf_graph.json, status.json)
        ↓
  HF Spaces chat  (loads model + graph from HF)

This script only:
  1. Pushes the Kaggle worker notebook via Kaggle API
  2. Polls kernel status until complete
  3. Polls HF for graph/status.json == ready

Usage:
  export HF_TOKEN=hf_...
  # Kaggle auth: ~/.kaggle/kaggle.json or access_token
  python scripts/kaggle_ingest.py
  python scripts/kaggle_ingest.py --books-repo Prataykarali/archipelago-books-cs
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER_DIR = Path(__file__).resolve().parent / "kaggle_worker"

DEFAULT_BOOKS_REPO = "Prataykarali/archipelago-books-cs"
DEFAULT_KERNEL_SLUG = "kopi456/libraryai-libqwen-ingest"
DEFAULT_GRAPH_PREFIX = "graph"


def _hf_headers(token: str | None) -> dict:
    h = {"User-Agent": "libraryai-kaggle-ingest/1.0"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def hf_get_json(repo: str, path: str, token: str | None, repo_type: str = "dataset") -> dict | None:
    """Fetch a JSON file from HF with cache-bust. Returns None if missing."""
    base = "datasets" if repo_type == "dataset" else ""
    # resolve/main with download=true follows CDN redirects when using urlopen
    url = (
        f"https://huggingface.co/{'datasets/' if repo_type == 'dataset' else ''}"
        f"{repo}/resolve/main/{path}?download=true&t={int(time.time())}"
    )
    req = urllib.request.Request(url, headers=_hf_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (404, 401):
            return None
        raise
    except Exception:
        return None


def push_kaggle_notebook(kernel_slug: str) -> str:
    meta_file = WORKER_DIR / "kernel-metadata.json"
    meta = json.loads(meta_file.read_text())
    meta["id"] = kernel_slug
    meta["enable_gpu"] = True
    meta["enable_internet"] = True
    meta_file.write_text(json.dumps(meta, indent=2) + "\n")

    print(f"  📤 Pushing headless GPU ingest notebook → {kernel_slug}")
    result = subprocess.run(
        ["kaggle", "kernels", "push", "-p", str(WORKER_DIR),
         "--accelerator", "NvidiaTeslaT4"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Kaggle push failed: {result.stderr or result.stdout}")
    print(f"  ✓ {result.stdout.strip()}")
    return kernel_slug


def wait_for_kernel(kernel_slug: str, max_wait_secs: int = 14400) -> str:
    """Poll until COMPLETE or ERROR. Long timeout: full corpus GPU extract."""
    print(f"  ⏳ Waiting for Kaggle kernel ({kernel_slug})...")
    t0 = time.time()
    last = ""
    while time.time() - t0 < max_wait_secs:
        result = subprocess.run(
            ["kaggle", "kernels", "status", kernel_slug],
            capture_output=True,
            text=True,
        )
        status = (result.stdout or result.stderr or "").strip()
        if status != last:
            print(f"    [{int(time.time() - t0):5d}s] {status}")
            last = status
        low = status.lower()
        if "complete" in low:
            return "COMPLETE"
        if "error" in low or "cancel" in low:
            # pull logs for debugging
            out = Path("/tmp/kaggle_ingest_logs")
            out.mkdir(exist_ok=True)
            subprocess.run(
                ["kaggle", "kernels", "output", kernel_slug, "-p", str(out)],
                capture_output=True,
                text=True,
            )
            print(f"  ❌ Kernel failed — logs in {out}")
            return "ERROR"
        time.sleep(20)
    return "TIMEOUT"


def wait_for_graph_on_hf(
    books_repo: str,
    graph_prefix: str,
    token: str | None,
    max_wait_secs: int = 600,
    min_started_after: float | None = None,
) -> dict:
    """Poll HF dataset graph/status.json until status=ready."""
    status_path = f"{graph_prefix.strip('/')}/status.json"
    print(f"  🔍 Polling HF dataset {books_repo}/{status_path} ...")
    deadline = time.time() + max_wait_secs
    while time.time() < deadline:
        data = hf_get_json(books_repo, status_path, token, repo_type="dataset")
        if data and data.get("status") == "ready":
            print(f"  ✓ Graph ready on HF: {data}")
            return data
        if data:
            print(f"    status present but not ready: {data}")
        else:
            print("    graph/status.json not published yet...")
        time.sleep(15)
    raise RuntimeError(
        f"Timed out waiting for {books_repo}/{status_path}. "
        "Check Kaggle kernel logs."
    )


def print_spaces_hints(books_repo: str, graph_prefix: str) -> None:
    p = graph_prefix.strip("/")
    print(
        f"""
{'=' * 70}
🎉 HEADLESS INGEST COMPLETE

HF dataset (books + ready graph for Spaces):
  https://huggingface.co/datasets/{books_repo}

Graph artifacts Spaces should load:
  {books_repo}/{p}/okf_graph.json     # nodes + edges + meta
  {books_repo}/{p}/okf_results.json   # raw concept records
  {books_repo}/{p}/status.json        # pipeline status

Inference model (GGUF / transformers):
  Prataykarali/lib-qwen-v5-gguf   or   Prataykarali/lib-qwen-v5

Librarian flow next time:
  1. Upload new PDFs into the HF dataset (folder per book / papers/)
  2. Re-run:  python scripts/kaggle_ingest.py
  3. Spaces reloads graph/ from the same dataset
{'=' * 70}
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless Kaggle GPU ingest: HF books → lib-qwen → HF graph"
    )
    parser.add_argument("--books-repo", default=DEFAULT_BOOKS_REPO,
                        help="HF dataset where librarian uploads books")
    parser.add_argument("--graph-prefix", default=DEFAULT_GRAPH_PREFIX,
                        help="Path prefix inside the dataset for graph outputs")
    parser.add_argument("--kernel-slug", default=DEFAULT_KERNEL_SLUG)
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--skip-push", action="store_true",
                        help="Only poll HF for an already-running/finished job")
    parser.add_argument("--max-wait", type=int, default=14400,
                        help="Max seconds to wait for Kaggle kernel")
    args = parser.parse_args()

    if not args.hf_token:
        print("⚠️  HF_TOKEN not set — graph poll/upload may fail for private datasets")

    print("=" * 60)
    print("LibraryAI headless Kaggle GPU ingest")
    print(f"  books/graph dataset: {args.books_repo}")
    print(f"  kernel:              {args.kernel_slug}")
    print("=" * 60)

    push_ts = time.time()
    if not args.skip_push:
        if not WORKER_DIR.exists():
            raise SystemExit(f"Missing worker dir: {WORKER_DIR}")
        push_kaggle_notebook(args.kernel_slug)
        state = wait_for_kernel(args.kernel_slug, max_wait_secs=args.max_wait)
        if state != "COMPLETE":
            # Still try HF — notebook uploads graph before COMPLETE finishes packing
            print(f"  ⚠️ Kernel ended as {state}; checking HF graph anyway...")
    else:
        print("  (skip-push: not launching a new Kaggle run)")

    try:
        meta = wait_for_graph_on_hf(
            args.books_repo,
            args.graph_prefix,
            args.hf_token or None,
            max_wait_secs=300 if not args.skip_push else args.max_wait,
        )
    except Exception as e:
        print(f"  ❌ {e}")
        sys.exit(1)

    print_spaces_hints(args.books_repo, args.graph_prefix)
    # Optional: write meta locally for ops visibility (not the books)
    out = REPO_ROOT / "data" / "artifacts" / "last_kaggle_ingest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta, indent=2))
    print(f"  💾 Local ops note: {out}")


if __name__ == "__main__":
    main()
