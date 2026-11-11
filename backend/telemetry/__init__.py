"""Telemetry and performance metrics tracking for Archipelago."""
from __future__ import annotations

import time
from collections import deque
from typing import Any

class TelemetryTracker:
    """In-memory sliding window performance recorder."""

    def __init__(self, maxlen: int = 500):
        self._latencies: deque[float] = deque(maxlen=maxlen)

    def record_latency(self, duration_ms: float) -> None:
        self._latencies.append(duration_ms)

    def metrics(self) -> dict[str, float]:
        if not self._latencies:
            return {"p50": 0.0, "p90": 0.0, "p99": 0.0, "avg": 0.0, "samples": 0}
        sorted_vals = sorted(self._latencies)
        n = len(sorted_vals)
        return {
            "p50": sorted_vals[int(n * 0.50)],
            "p90": sorted_vals[min(int(n * 0.90), n - 1)],
            "p99": sorted_vals[min(int(n * 0.99), n - 1)],
            "avg": sum(sorted_vals) / n,
            "samples": n,
        }

telemetry_tracker = TelemetryTracker()

__all__ = ["TelemetryTracker", "telemetry_tracker"]
