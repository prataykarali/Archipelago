"""Facade for the split of tc75_cases.py."""
from __future__ import annotations

from typing import Any  # noqa: F401

from .part01_testcase import (  # noqa: F401
    TestCase,
    score_case,
)
from .part02_all_tc_cases import (  # noqa: F401
    ALL_TC_CASES,
)

__all__ = ["TestCase", "score_case", "ALL_TC_CASES"]
