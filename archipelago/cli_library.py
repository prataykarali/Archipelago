"""Library catalog and source lifecycle CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


# ─── Library: catalog population + source lifecycle ────────────

DEFAULT_GRAPH_DB = "okf_graph.db"
DEFAULT_KOHA_DIR = "data/koha"
DEFAULT_BOOKSHELF = "data/catalogs/pearson_bookshelf.json"


def _graph_db_path(args: argparse.Namespace) -> Path:
    """Resolve the graph database path from the CLI args or the repo default."""
    return Path(getattr(args, "db", None) or ROOT / DEFAULT_GRAPH_DB)


def cmd_library_populate(args: argparse.Namespace) -> int:
    """Merge the institutional catalog (Koha + eLibrary) into the graph."""
    from catalog_populate import ingest_catalog, ingest_pearson_bookshelf

    db_path = str(_graph_db_path(args))
    if not Path(db_path).exists():
        print(f"ERROR: graph database not found: {db_path}", file=sys.stderr)
        return 1

    total_resources = 0
    koha_dir = getattr(args, "koha_dir", None) or str(ROOT / DEFAULT_KOHA_DIR)
    if Path(koha_dir).is_dir():
        counts = ingest_catalog(db_path, koha_dir)
        print(f"Koha catalog: {counts['resources']} resources, {counts['subjects']} subjects")
        total_resources += counts["resources"]

    bookshelf = getattr(args, "bookshelf", None) or str(ROOT / DEFAULT_BOOKSHELF)
    if Path(bookshelf).is_file():
        counts = ingest_pearson_bookshelf(db_path, bookshelf)
        print(f"Pearson eLibrary: {counts['resources']} resources, {counts['subjects']} subjects")
        total_resources += counts["resources"]

    if not total_resources:
        print("No catalog sources found; pass --koha-dir and/or --bookshelf.", file=sys.stderr)
        return 1
    print(f"\nCatalog now holds {total_resources} searchable resources.")
    return 0


def cmd_library_propose(args: argparse.Namespace) -> int:
    """Propose entitled-but-unheld books for the librarian to approve."""
    from archipelago.resolver.ingest_proposals import (
        discover_from_provider_bookshelf,
        load_queue,
    )

    bookshelf = getattr(args, "bookshelf", None) or str(ROOT / DEFAULT_BOOKSHELF)
    if not Path(bookshelf).is_file():
        print(f"ERROR: bookshelf export not found: {bookshelf}", file=sys.stderr)
        return 1

    graph_file = ROOT / "okf_graph.json"
    held: set[str] = set()
    if graph_file.is_file():
        try:
            raw = json.loads(graph_file.read_text(encoding="utf-8"))
            for node in raw.get("nodes") or []:
                held.add(str(node.get("name") or "").strip().lower())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: unreadable {graph_file.name}: {exc}", file=sys.stderr)

    result = discover_from_provider_bookshelf(bookshelf, held)
    print(f"New proposals: {len(result['proposed'])}")
    print(f"Already held:  {result['already_held']}")
    for proposal in result["proposed"]:
        print(f"  + {proposal['title']}  [{proposal['license_mode']}]")

    pending = sum(1 for p in load_queue().values() if p.actionable)
    print(f"\nAwaiting librarian review: {pending}")
    return 0


def cmd_library_sources(args: argparse.Namespace) -> int:
    """Print source availability from the lifecycle ledger."""
    from archipelago.resolver.source_lifecycle import load_ledger

    states = load_ledger()
    if not states:
        print("No source lifecycle records yet. Run a provider check first.")
        return 0

    withdrawn_only = getattr(args, "withdrawn_only", False)
    for source_id, state in sorted(states.items()):
        if withdrawn_only and state.status != "withdrawn":
            continue
        label = state.tombstone.get("title") or source_id
        print(f"[{state.status:9}] {label}  ({state.provider or 'unknown'}) {source_id}")
        if state.message:
            print(f"            {state.message}")

    counts: dict[str, int] = {}
    for state in states.values():
        counts[state.status] = counts.get(state.status, 0) + 1
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    return 0


# ─── Main parser ──────────────────────────────────────────────
