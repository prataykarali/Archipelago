"""
CLI command for resource synchronization and reconciliation across all 46 resources.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import logging
from pathlib import Path
import sys

from archipelago.resolver.huggingface import resolve_huggingface_url, verify_hf_repo_file
from archipelago.resolver.resource_registry import get_registry, ResourceRecord
from archipelago.resolver.resolver import LinkResolver

logger = logging.getLogger("archipelago.resolver.sync")


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


def sync_all_resources(verbose: bool = False) -> tuple[dict, list[dict]]:
    """Synchronize, resolve, and audit all 46 registered resources."""
    registry = get_registry()
    resources = registry.all_resources()
    resolver = LinkResolver()

    base_dir = Path(__file__).resolve().parents[2]
    pdf_dir = base_dir / "pdfs"

    stats = Counter({
        "total": len(resources),
        "huggingface": 0,
        "pearson": 0,
        "local": 0,
        "metadata_only": 0,
        "resolved": 0,
        "missing": 0,
        "auth_required": 0,
        "stale": 0,
        "duplicates": 0,
    })

    duplicates = registry.detect_duplicates()
    stats["duplicates"] = len(duplicates)

    results = []

    for res in resources:
        res_source = res.source or "metadata_only"
        res_id = res.resource_id
        res_title = res.title or "Unknown Title"

        status_symbol = "ⓘ"
        status_text = "metadata only"
        is_missing = False
        auth_required = False
        is_stale = False

        if res_source == "huggingface":
            stats["huggingface"] += 1
            hf_res = resolver.resolve(resource_id=res_id, title=res_title, isbn=res.isbn, source="huggingface")
            if hf_res.get("working"):
                status_symbol = "✓"
                status_text = hf_res.get("filename") or hf_res.get("url", "")
                stats["resolved"] += 1
            else:
                status_symbol = "✗"
                status_text = "NOT FOUND"
                is_missing = True

        elif res_source == "pearson":
            stats["pearson"] += 1
            p_res = resolver.resolve(resource_id=res_id, title=res_title, isbn=res.isbn, source="pearson")
            if p_res.get("working"):
                status_symbol = "✓"
                status_text = res.pearson_book_id or res_id
                stats["resolved"] += 1
            elif p_res.get("status") == "authentication_required":
                status_symbol = "⚠"
                status_text = "AUTH REQUIRED"
                auth_required = True
            elif p_res.get("status") == "stale":
                status_symbol = "⚠"
                status_text = "STALE URL"
                is_stale = True
            else:
                status_symbol = "✗"
                status_text = "NOT FOUND"
                is_missing = True

        elif res_source == "local":
            stats["local"] += 1
            # Check local file
            reader_url = res.reader_url.lstrip("/")
            # Check if file exists under pdfs or base_dir
            candidate1 = base_dir / reader_url
            candidate2 = pdf_dir / reader_url.replace("pdfs/", "")
            exists = candidate1.is_file() or candidate2.is_file()
            if exists:
                status_symbol = "✓"
                status_text = res.reader_url
                stats["resolved"] += 1
            else:
                status_symbol = "✗"
                status_text = "FILE MISSING"
                is_missing = True

        else:
            # metadata_only
            stats["metadata_only"] += 1
            status_symbol = "ⓘ"
            status_text = "metadata only"
            stats["resolved"] += 1

        if is_missing:
            stats["missing"] += 1
        if auth_required:
            stats["auth_required"] += 1
        if is_stale:
            stats["stale"] += 1

        results.append({
            "id": res_id,
            "source": res_source.upper(),
            "symbol": status_symbol,
            "title": res_title,
            "status": status_text,
            "reader_url": res.reader_url,
        })

    return dict(stats), results


def main() -> None:
    parser = argparse.ArgumentParser(description="Resource Synchronization Command for Archipelago (All 46 Resources)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    setup_logging(args.verbose)

    stats, results = sync_all_resources(verbose=args.verbose)

    if args.json:
        print(json.dumps({
            "stats": stats,
            "details": results
        }, indent=2))
        return

    # Print Text Report
    print("\nRESOURCE SYNC")
    print("=============\n")
    print(f"Total:        {stats['total']}")
    print(f"Hugging Face:  {stats['huggingface']}")
    print(f"Pearson:      {stats['pearson']}")
    print(f"Local PDF:     {stats['local']}")
    print(f"Metadata-only: {stats['metadata_only']}\n")
    print(f"Resolved:     {stats['resolved']}")
    print(f"Missing:       {stats['missing']}")
    print(f"Auth Required: {stats['auth_required']}")
    print(f"Stale:         {stats['stale']}")
    print(f"Duplicates:    {stats['duplicates']}\n")
    
    if stats['total'] > 0:
        percent = (stats['resolved'] / stats['total']) * 100
    else:
        percent = 100.0
    print(f"Completed: {percent:.2f}%\n")

    print("--- DETAILS ---")
    for r in results:
        source_tag = f"[{r['source']}]"
        print(f"{source_tag:<12} {r['symbol']} {r['title'][:44]:<45} {r['status']}")


if __name__ == "__main__":
    main()

