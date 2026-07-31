#!/usr/bin/env python3
"""
ingest_real_lib.py — Safe & Resumable Batch Ingestion for Archipelago Real Library.

Features:
  1. Resumable: Skips previously completed PDFs automatically.
  2. Thermally Throttled: Pauses between files (3s rest) to prevent GPU/RAM overheat.
  3. Isolated Subprocess: Each PDF runs in a fresh Python process so memory is 100% freed on exit.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL_LIB_DIR = ROOT / "pdfs" / "real-lib"
LOG_DIR = ROOT / "ingest_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

PY = ROOT / ".venv" / "bin" / "python"


def find_all_pdfs() -> list[Path]:
    """Find all unique PDF files under pdfs/real-lib/."""
    pdfs = []
    for p in sorted(REAL_LIB_DIR.glob("**/*.pdf")):
        if p.is_file() and p.stat().st_size > 1000:
            pdfs.append(p)
    return pdfs


def is_already_completed(log_file: Path) -> bool:
    """Check if the log file indicates successful past ingestion."""
    if not log_file.exists():
        return False
    try:
        content = log_file.read_text(encoding="utf-8", errors="ignore")
        return "[OK] Pipeline complete!" in content or "Pipeline complete!" in content
    except Exception:
        return False


def main():
    pdfs = find_all_pdfs()
    print("=" * 65)
    print(f" Archipelago Safe & Resumable Batch Ingestion ({len(pdfs)} PDFs)")
    print("=" * 65)
    print(f"Root dir   : {ROOT}")
    print(f"Target dir : {REAL_LIB_DIR}")
    print(f"Python env : {PY}")
    print("=" * 65)

    completed = 0
    failed = 0
    skipped = 0

    start_total = time.time()

    for idx, pdf_path in enumerate(pdfs, 1):
        rel_path = pdf_path.relative_to(ROOT)
        log_name = f"ingest_{idx:03d}_{pdf_path.stem[:30]}.log"
        log_file = LOG_DIR / log_name

        # Skip already completed PDFs
        if is_already_completed(log_file):
            skipped += 1
            print(f"[{idx}/{len(pdfs)}] SKIP (Already Completed): {pdf_path.name}")
            continue

        print(f"\n[{idx}/{len(pdfs)}] Ingesting: {rel_path}")
        print(f"  Size: {pdf_path.stat().st_size / (1024*1024):.2f} MB | Log: {log_file.name}")

        cmd = [str(PY), "okf_pipeline.py", "--add", str(rel_path), "--ollama"]
        
        t0 = time.time()
        try:
            with open(log_file, "w", encoding="utf-8") as lf:
                res = subprocess.run(cmd, cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT, timeout=1800)
            elapsed = time.time() - t0

            if res.returncode == 0:
                completed += 1
                print(f"  ✓ DONE in {elapsed:.1f}s")
            else:
                failed += 1
                print(f"  ✗ FAILED (rc={res.returncode}) in {elapsed:.1f}s — see {log_file}")
        except subprocess.TimeoutExpired:
            failed += 1
            print(f"  TIMEOUT (>600s) — see {log_file}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {e}")

        # Thermal rest pause between files to prevent GPU/RAM overheat
        time.sleep(3)

    total_time = time.time() - start_total
    print("\n" + "=" * 65)
    print(f" Batch Ingestion Finished in {total_time/60:.1f} minutes")
    print(f" Newly Ingested: {completed} | Skipped (Done): {skipped} | Failed: {failed}")
    print("=" * 65)


if __name__ == "__main__":
    main()
