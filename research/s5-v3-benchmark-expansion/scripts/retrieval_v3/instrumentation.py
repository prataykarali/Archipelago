"""Improvement #9: End-to-end latency (perf_counter_ns) and memory (tracemalloc) telemetry."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import statistics
import time
import tracemalloc
from typing import Any

from retrieval_v3.types import QueryTimingMemory

NS_PER_MS = 1_000_000.0
PERCENTILE_95 = 0.95
PERCENTILE_50 = 0.50


def measure_call[T](
    fn: Callable[[], T],
    *,
    measure_memory: bool = True,
) -> tuple[T, QueryTimingMemory]:
    """Execute fn() while measuring wall-clock latency_ns and tracemalloc peak memory."""
    already_tracing = tracemalloc.is_tracing()
    if measure_memory:
        if not already_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()

    start_ns = time.perf_counter_ns()
    output = fn()
    elapsed_ns = time.perf_counter_ns() - start_ns

    current_bytes = 0
    peak_bytes = 0
    if measure_memory:
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        if not already_tracing:
            tracemalloc.stop()

    telemetry = QueryTimingMemory(
        latency_ns=elapsed_ns,
        latency_ms=elapsed_ns / NS_PER_MS,
        peak_memory_bytes=peak_bytes,
        current_memory_bytes=current_bytes,
    )
    return output, telemetry


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * q
    low = int(pos)
    high = min(low + 1, len(sorted_vals) - 1)
    frac = pos - low
    return float(sorted_vals[low] + (sorted_vals[high] - sorted_vals[low]) * frac)


def summarize_telemetry(records: Sequence[QueryTimingMemory]) -> dict[str, Any]:
    """Compute distributional latency and peak memory summaries across queries."""
    if not records:
        return {
            "query_count": 0,
            "latency_ms": {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "max": 0.0,
                "total": 0.0,
            },
            "peak_memory_bytes": {
                "mean": 0.0,
                "max": 0,
                "min": 0,
            },
        }

    latencies = sorted(r.latency_ms for r in records)
    peaks = [r.peak_memory_bytes for r in records]
    std_val = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
    return {
        "query_count": len(records),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 4),
            "std": round(std_val, 4),
            "min": round(latencies[0], 4),
            "p50": round(_percentile(latencies, PERCENTILE_50), 4),
            "p95": round(_percentile(latencies, PERCENTILE_95), 4),
            "max": round(latencies[-1], 4),
            "total": round(sum(latencies), 4),
        },
        "peak_memory_bytes": {
            "mean": round(statistics.mean(peaks), 2),
            "max": max(peaks),
            "min": min(peaks),
        },
    }
