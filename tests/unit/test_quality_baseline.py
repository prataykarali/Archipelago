"""Regression checks for the interim strict-gate debt baseline."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from scripts.quality_baseline import new_size_errors, new_type_errors, type_error_counts

pytestmark = pytest.mark.unit


def test_type_baseline_ignores_line_shifts_but_rejects_new_diagnostics() -> None:
    """Moving code must not invalidate debt; adding a diagnostic must."""
    baseline = {"okf/example.py|type-arg|Missing type arguments": 1}
    output = "okf/example.py:99: error: Missing type arguments  [type-arg]\n"
    current = type_error_counts(output)
    assert new_type_errors(current, baseline) == []

    added = current + Counter({"okf/example.py|no-untyped-def|Missing annotation": 1})
    assert new_type_errors(added, baseline) == [
        "okf/example.py|no-untyped-def|Missing annotation (+1)"
    ]


def test_size_baseline_rejects_new_file_and_growth() -> None:
    """Existing large files may shrink, while new or grown files fail."""
    baseline = {"existing.py": 600}
    assert new_size_errors([(Path("existing.py"), 580)], baseline) == []
    assert new_size_errors([(Path("existing.py"), 601)], baseline)
    assert new_size_errors([(Path("new.py"), 401)], baseline)
