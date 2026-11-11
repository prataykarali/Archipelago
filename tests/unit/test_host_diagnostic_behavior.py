"""Hosted diagnostic length and curriculum path regressions."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from engine import Engine  # noqa: E402
from engine.pathfinder import learning_path  # noqa: E402

pytestmark = pytest.mark.unit
TARGET = "transformer"
LONG_PATH_LENGTH = 12


@pytest.fixture(scope="module")
def hosted_engine():
    return Engine()


def test_diagnostic_stops_at_three_correct_or_six_total(hosted_engine):
    payload = hosted_engine.diagnostic_payload(TARGET)
    for choices, expected_count in ((["A", "A", "A"], 3), (["B"] * 6, 6)):
        question = payload["initial_question"]
        history = []
        for index, choice in enumerate(choices, 1):
            result = hosted_engine.adaptive_step(
                {
                    "target_concept": TARGET,
                    "current_mcq": question,
                    "user_choice": choice,
                    "history": history,
                }
            )
            history = result["history"]
            if index < expected_count:
                assert result["completed"] is False
                question = result["next_question"]
        assert result["completed"] is True
        assert result["total_asked"] == expected_count
        assert result["next_question"] is None


def test_personalized_path_is_not_capped_at_eight():
    class _Graph:
        def __init__(self) -> None:
            self.nodes = {str(index): {} for index in range(LONG_PATH_LENGTH)}
            self.out = {
                str(index): [("REQUIRES", str(index - 1))] for index in range(1, LONG_PATH_LENGTH)
            }
            self.inn = {}

    path = learning_path(_Graph(), str(LONG_PATH_LENGTH - 1), frozenset())
    assert len(path) == LONG_PATH_LENGTH
    assert path[0] == "0"
    assert path[-1] == str(LONG_PATH_LENGTH - 1)
