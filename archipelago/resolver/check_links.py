"""CLI Admin Utility for parallel link resolution and catalog validation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys

from archipelago.resolver.resolver import LinkResolver


def main() -> None:
    args = sys.argv[1:]
    resolver = LinkResolver()

    # If a specific resource_id argument is passed
    if args:
        resource_id = args[0]
        print(f"Checking resource: {resource_id} ...")
        res = resolver.resolve(resource_id=resource_id)
        print(json.dumps(res, indent=2))
        return

    # Batch check all 46 registered catalog resources via ResourceRegistry
    from archipelago.resolver.resource_registry import get_registry

    registry = get_registry()
    resources = registry.all_resources()
    total = len(resources)
    print(f"\nChecking all {total} resources concurrently...\n")


    verified = 0
    redirected = 0
    repaired = 0
    unresolved = 0

    def check_one(item: Any) -> dict:
        rid = getattr(item, "resource_id", None) or (item.get("id") if isinstance(item, dict) else "unknown")
        title = getattr(item, "title", None) or (item.get("title") if isinstance(item, dict) else "")
        isbn = getattr(item, "isbn", None) or (item.get("isbn") if isinstance(item, dict) else "")
        source = getattr(item, "source", None) or (item.get("source") if isinstance(item, dict) else "")
        return resolver.resolve(resource_id=rid, title=title, isbn=isbn, source=source)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_one, item) for item in resources]

        for fut in as_completed(futures):
            try:
                res = fut.result()
                if res.get("working"):
                    verified += 1
                    if res.get("redirected"):
                        redirected += 1
                    if res.get("source") != "direct":
                        repaired += 1
                else:
                    unresolved += 1
            except Exception:
                unresolved += 1

    print("---------------------------------------")
    print(f"✓ {verified} verified")
    print(f"↪ {redirected} redirected")
    print(f"⚠ {repaired} repaired")
    print(f"✗ {unresolved} unresolved")
    print("---------------------------------------\n")


if __name__ == "__main__":
    main()
