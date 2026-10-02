"""Guard: ``finalize_and_build`` must honour a patched ``BASE_DIR``.

Regression for the modularization bug where ``okf.pipeline`` used a *direct*
``BASE_DIR`` import, so ``patch("okf.pipeline.BASE_DIR", tmp_path)`` was
silently ignored — ``finalize_and_build`` then read/wrote near the repository
root instead of the patched directory (its first act is to dump
``okf_results.json``, which is how the local concept corpus got clobbered).

Contract under test: every path in ``finalize_and_build`` is anchored to
``okf.pipeline.BASE_DIR`` as resolved dynamically through the package
namespace (``_rt.BASE_DIR``), not a snapshot taken at import time.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]

SAMPLE_RESULTS = [
    {
        "concept_name": "Concept A",
        "concept_type": "definition",
        "difficulty": "foundational",
        "summary": "Summary A",
        "prerequisites": [],
        "unlocks": [],
        "related_to": [],
        "tags": [],
    }
]


class _StopPipeline(Exception):
    """Sentinel raised to halt the pipeline right after its first write."""


def _fingerprint(name: str) -> str | None:
    """Hash a repo-root artifact, or ``None`` when it does not exist."""
    path = REPO_ROOT / name
    if not path.is_file():
        return None
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_finalize_and_build_anchors_writes_to_patched_base_dir(tmp_path: Path) -> None:
    """The first write lands under the patched dir — never in the repo root."""
    repo_results_before = _fingerprint("okf_results.json")

    with patch("okf.pipeline.BASE_DIR", tmp_path), \
         patch("okf.pipeline.cleanup_and_canonicalize", side_effect=lambda x: x), \
         patch("okf.pipeline.ingest_to_kuzu",
               side_effect=_StopPipeline("stop before graph build")):
        from okf.pipeline import finalize_and_build

        with pytest.raises(_StopPipeline):
            finalize_and_build(SAMPLE_RESULTS, 1, 1, chunks=[])

    assert (tmp_path / "okf_results.json").is_file(), (
        "finalize_and_build ignored the patched okf.pipeline.BASE_DIR"
    )
    assert _fingerprint("okf_results.json") == repo_results_before, (
        "finalize_and_build wrote okf_results.json into the repository root"
    )


def test_finalize_and_build_threads_base_dir_into_artifact_writer(tmp_path: Path) -> None:
    """The shared artifact writer receives the patched dir explicitly.

    ``write_all_artifacts`` defaults to ``okf.config.BASE_DIR``, independent of
    ``okf.pipeline.BASE_DIR``; finalize_and_build must pass its own anchored
    value so a patched run cannot leak artifacts outside ``tmp_path``.
    """
    graph_export = {
        "concepts": {},
        "edges": [],
        "stats": {"total_concepts": 1, "total_edges": 0},
    }

    with patch("okf.pipeline.BASE_DIR", tmp_path), \
         patch("okf.pipeline.cleanup_and_canonicalize", side_effect=lambda x: x), \
         patch("okf.pipeline.ingest_to_kuzu",
               return_value=(MagicMock(), MagicMock(), graph_export)), \
         patch("okf.evaluate.structural_audit",
               return_value={"self_edges": [], "cycles": []}), \
         patch("okf.exports.write_all_artifacts",
               return_value=(MagicMock(), MagicMock())) as writer:
        from okf.pipeline import finalize_and_build

        try:
            finalize_and_build(SAMPLE_RESULTS, 1, 1, chunks=[])
        except Exception:
            # Later evaluation stages may need real data/LLM access; the
            # contract we assert is established before they run.
            pass

    assert writer.called, "write_all_artifacts was never reached"
    assert writer.call_args.kwargs.get("base_dir") == tmp_path
