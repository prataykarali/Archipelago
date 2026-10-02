"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from typing import Any
from . import _deps as _rt  # noqa: F401


class TestCase:
    """A structured test case representation for Archipelago verification."""

    def __init__(
        self,
        tc_id: str,
        query: str,
        category: int,
        expect_length_error: bool = False,
        expect_multi_topic: bool = False,
        expect_curriculum: bool = False,
        expect_lineage: bool = False,
        expect_lib_intent: str | None = None,
        expect_body_any: list[str] | None = None,
        expect_body_all: list[str] | None = None,
    ) -> None:
        """Initialize TestCase with validation fields."""
        self.tc_id = tc_id
        self.query = query
        self.category = category
        self.expect_length_error = expect_length_error
        self.expect_multi_topic = expect_multi_topic
        self.expect_curriculum = expect_curriculum
        self.expect_lineage = expect_lineage
        self.expect_lib_intent = expect_lib_intent
        self.expect_body_any = expect_body_any
        self.expect_body_all = expect_body_all


def score_case(case: TestCase, ctx: dict[str, Any]) -> tuple[bool, str]:
    """Score a pipeline context against test case expectations.

    Args:
        case: The test case containing the expectations.
        ctx: The runtime context dict returned by the pipeline.

    Returns:
        A tuple of (success_boolean, detail_string).
    """
    if case.expect_length_error and not ctx.get("length_error"):
        return False, "Expected length error but none detected"
    if case.expect_length_error:
        return True, ""

    if case.expect_multi_topic and not ctx.get("topics_ok"):
        return False, "Expected multi-topic parsing to succeed"

    if case.expect_curriculum and not ctx.get("curriculum_ok"):
        return False, "Expected curriculum paths to be traversed"

    if case.expect_lineage and not ctx.get("lineage_ok"):
        return False, "Expected citation lineage mapping to succeed"

    if case.expect_lib_intent and ctx.get("lib_intent") != case.expect_lib_intent:
        return (
            False,
            f"Expected library intent {case.expect_lib_intent} but got {ctx.get('lib_intent')}",
        )

    if case.expect_body_any:
        body = ctx.get("body", "")
        if not any(val.lower() in body.lower() for val in case.expect_body_any):
            return (
                False,
                f"Expected body to contain any of {case.expect_body_any} but got: {body[:120]}",
            )

    if case.expect_body_all:
        body = ctx.get("body", "")
        if not all(val.lower() in body.lower() for val in case.expect_body_all):
            return (
                False,
                f"Expected body to contain all of {case.expect_body_all} but got: {body[:120]}",
            )

    return True, ""
