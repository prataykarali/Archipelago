"""Probe graph availability while the staging database is published."""

from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def subgraph_hammer(stop: threading.Event, results: list[dict[str, Any]]) -> None:
    """Hit live graph APIs and a read-only Kùzu count while the staging swap runs."""
    import urllib.request

    from archipelago.graph.engine import KuzuGraphEngine

    urls = [
        "http://127.0.0.1:5150/api/graph",
        "http://127.0.0.1:5052/api/graph/subgraph?target_id=transmission_control_protocol&max_nodes=8",
    ]
    prod = ROOT / "okf_graph.db"
    while not stop.is_set():
        t0 = time.time()
        hit = {"ok": False, "ms": 0}
        for url in urls:
            try:
                with urllib.request.urlopen(url, timeout=8) as resp:
                    hit = {
                        "ok": True,
                        "status": resp.status,
                        "url": url,
                        "ms": int((time.time() - t0) * 1000),
                    }
                    break
            except Exception as exc:
                hit = {
                    "ok": False,
                    "error": str(exc),
                    "url": url,
                    "ms": int((time.time() - t0) * 1000),
                }
        if prod.exists():
            try:
                engine = KuzuGraphEngine(db_path=prod, read_only=True)
                n = int(
                    engine.conn.execute("MATCH (c:Concept) RETURN count(c);").get_as_df().iloc[0, 0]
                )
                engine.close()
                hit["kuzu_count"] = n
                hit["kuzu_ok"] = True
            except Exception as exc:
                hit["kuzu_ok"] = False
                hit["kuzu_error"] = str(exc)
        results.append(hit)
        stop.wait(0.4)
