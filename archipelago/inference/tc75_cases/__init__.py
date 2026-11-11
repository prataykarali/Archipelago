"""Facade for the split of tc75_cases.py."""

from __future__ import annotations

from typing import Any  # noqa: F401

from .part01_testcase import (
    TestCase,
    score_case,
)
from .part02_all_tc_cases import (
    ALL_TC_CASES,
)

__all__ = ["ALL_TC_CASES", "TestCase", "score_case"]
