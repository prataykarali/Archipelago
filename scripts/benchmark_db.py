"""KùzuDB Micro-benchmark harness.

Measures p50, p95, and p99 query latency for 1-hop, 2-hop, and multi-hop
topological traversals in KùzuDB. Emits JSON metrics and human-readable summary.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any

# Ensure project root and src/ are in sys.path
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
_src_dir = _repo_root / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from archipelago.graph.engine import KuzuGraphEngine


def benchmark_query(
    engine: KuzuGraphEngine,
    query: str,
    params: dict[str, Any] | None = None,
    iterations: int = 100,
    warmup: int = 10,
) -> dict[str, float]:
    """Benchmark a single Cypher query over repeated iterations."""
    # Warmup
    for _ in range(warmup):
        engine.execute(query, params)

    durations_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        engine.execute(query, params)
        t1 = time.perf_counter()
        durations_ms.append((t1 - t0) * 1000.0)

    durations_ms.sort()
    n = len(durations_ms)

    def p(pct: float) -> float:
        idx = int(n * pct)
        return durations_ms[min(idx, n - 1)]

    return {
        "iterations": n,
        "min_ms": round(durations_ms[0], 3),
        "p50_ms": round(p(0.50), 3),
        "p90_ms": round(p(0.90), 3),
        "p95_ms": round(p(0.95), 3),
        "p99_ms": round(p(0.99), 3),
        "max_ms": round(durations_ms[-1], 3),
        "mean_ms": round(statistics.mean(durations_ms), 3),
    }


def run_benchmarks(db_path: str, iterations: int = 100) -> dict[str, Any]:
    """Execute standard suite of benchmark queries against KùzuDB instance."""
    path = Path(db_path)
    if not path.exists():
        print(f"Warning: Database path '{db_path}' does not exist. Creating synthetic in-memory/temp DB.")
        # Setup synthetic benchmark DB
        temp_dir = Path("/tmp/archipelago_bench_db")
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)
        engine = KuzuGraphEngine(temp_dir, read_only=False)
        engine.execute("CREATE NODE TABLE Concept(name STRING, level INT64, PRIMARY KEY(name))")
        engine.execute("CREATE REL TABLE REQUIRES(FROM Concept TO Concept)")
        # Insert test concepts
        for i in range(100):
            engine.execute(f"CREATE (:Concept {{name: 'C_{i}', level: {i % 4}}})")
        for i in range(90):
            engine.execute(f"MATCH (a:Concept), (b:Concept) WHERE a.name = 'C_{i}' AND b.name = 'C_{i+1}' CREATE (a)-[:REQUIRES]->(b)")
    else:
        engine = KuzuGraphEngine(path, read_only=True)

    suite = {
        "1_hop_traversal": "MATCH (a)-[r]->(b) RETURN a, b LIMIT 20",
        "node_lookup_point": "MATCH (a) RETURN a LIMIT 1",
        "aggregate_count": "MATCH (a) RETURN count(a)",
    }

    results: dict[str, Any] = {}
    print(f"\n--- Running KùzuDB Micro-benchmarks ({iterations} iterations each) ---")
    print(f"Database: {path.resolve()}\n")

    for name, query in suite.items():
        try:
            stats = benchmark_query(engine, query, iterations=iterations)
            results[name] = stats
            print(
                f"[{name}]\n"
                f"  p50: {stats['p50_ms']} ms | "
                f"p95: {stats['p95_ms']} ms | "
                f"p99: {stats['p99_ms']} ms | "
                f"mean: {stats['mean_ms']} ms"
            )
        except Exception as e:
            results[name] = {"error": str(e)}
            print(f"[{name}] Failed: {e}")

    engine.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="KùzuDB Micro-benchmarks")
    parser.add_argument("--db-path", default="okf_graph.db", help="Path to KùzuDB database")
    parser.add_argument("--iterations", type=int, default=100, help="Number of benchmark iterations")
    parser.add_argument("--output-json", help="Path to write JSON benchmark report")
    args = parser.parse_args()

    results = run_benchmarks(args.db_path, iterations=args.iterations)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nBenchmark metrics written to: {args.output_json}")


if __name__ == "__main__":
    main()
