"""Track existing type and source-size debt while rejecting new violations.

The baseline is an interim migration aid. Run the strict tools directly to see
the full backlog; shrinking this file is the only route to a clean strict gate.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

BASELINE_PATH = Path(__file__).parent / "baselines" / "quality_debt.json"
MYPY_ERROR = re.compile(r"^(.+?):\d+(?::\d+)?: error: (.*?)\s+\[([^]]+)\]$")


def type_error_counts(output: str) -> Counter[str]:
    """Count mypy diagnostics by file, message, and error code, ignoring line shifts."""
    counts: Counter[str] = Counter()
    for line in output.splitlines():
        match = MYPY_ERROR.match(line)
        if match:
            path, message, code = match.groups()
            counts[f"{path}|{code}|{message}"] += 1
    return counts


def read_baseline() -> dict[str, dict[str, int]]:
    """Read the reviewed debt snapshot without silently creating a new one."""
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def new_type_errors(current: Counter[str], baseline: dict[str, int]) -> list[str]:
    """Return diagnostics whose count grew beyond the reviewed snapshot."""
    return [
        f"{key} (+{count - baseline.get(key, 0)})"
        for key, count in sorted(current.items())
        if count > baseline.get(key, 0)
    ]


def new_size_errors(current: list[tuple[Path, int]], baseline: dict[str, int]) -> list[str]:
    """Reject new oversized files and growth in grandfathered files."""
    return [
        f"{path}: {count} lines (baseline {baseline.get(str(path), 0)})"
        for path, count in current
        if count > baseline.get(str(path), 0)
    ]
