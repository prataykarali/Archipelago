"""Copy the lightweight S5 runtime into the Vercel project root."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "host_inference"
MODULES = (
    "archipelago/__init__.py",
    "archipelago/scholarly/__init__.py",
    "archipelago/scholarly/contracts/__init__.py",
    "archipelago/scholarly/contracts/okf_models.py",
    "archipelago/scholarly/discovery/arxiv_adapter.py",
    "archipelago/scholarly/discovery/canonicalizer.py",
    "archipelago/scholarly/discovery/crossref_adapter.py",
    "archipelago/scholarly/discovery/live_sources.py",
    "archipelago/scholarly/discovery/openalex_adapter.py",
    "archipelago/scholarly/discovery/orchestrator.py",
    "archipelago/scholarly/features/feature_engine.py",
    "archipelago/scholarly/pipeline/relevance.py",
    "archipelago/scholarly/intelligence/__init__.py",
    "archipelago/scholarly/intelligence/analytics.py",
    "archipelago/scholarly/intelligence/enrichment.py",
    "archipelago/scholarly/intelligence/extraction.py",
    "archipelago/scholarly/intelligence/graph.py",
    "archipelago/scholarly/intelligence/monitor.py",
    "archipelago/scholarly/intelligence/postgres_storage.py",
    "archipelago/scholarly/intelligence/search.py",
    "archipelago/scholarly/intelligence/storage.py",
    "archipelago/scholarly/intelligence/workbook.py",
)


def main() -> int:
    """Synchronize sources, or verify the checked-in deployment copy."""
    check = "--check" in sys.argv[1:]
    stale = []
    for relative in MODULES:
        source = ROOT / relative
        target = DESTINATION / relative
        if check:
            if not target.exists() or source.read_bytes() != target.read_bytes():
                stale.append(relative)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    if stale:
        print("S5 hosted runtime is stale:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
