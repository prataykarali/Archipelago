"""Regression tests for D4-B Scientific Integrity Audit and Routing Repairs.

Verifies:
1. "What is deadlock?" and "what isdeadlock" resolve consistently to the Deadlock concept.
2. "AVL Tree" does not resolve to the ML Decision Tree node.
3. "Context-free languages" does not resolve to the NLP/ReAct context node.
4. "LLVM SSA", "Post Correspondence Problem", and "zk-SNARKs" are recognized as in-domain Computer Science.
5. "Artificial Intelligence: A Modern Approach" resolves to the verified library/Pearson catalog record.
6. Synthetic textbooks/*.pdf citations are never given broken reader URLs or marked as verified passages.
7. Combined query "Find papers and UEM library books about deadlocks." attributes both books and research literature.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host_inference"))

from engine import Engine  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def engine() -> Engine:
    return Engine()


class TestD4BRoutingAndIntegrity:
    """Validate D4-B domain routing, homonym protection, and evidence grounding."""

    def test_deadlock_query_normalization(self, engine: Engine) -> None:
        """Verify 'what isdeadlock' and 'what is deadlock' both route to deadlock concept."""
        res_normal = engine._route("What is deadlock?")
        res_fused = engine._route("what isdeadlock")

        assert res_normal[0] == "GRAPH_SYNTHESIS"
        assert res_normal[2] == "deadlock"

        assert res_fused[0] == "GRAPH_SYNTHESIS"
        assert res_fused[2] == "deadlock"

    def test_avl_tree_does_not_resolve_to_decision_tree(self, engine: Engine) -> None:
        """Verify AVL Tree (DSA) does not falsely resolve to ML Decision Tree ('tree')."""
        res = engine._route("AVL Tree")
        assert res[2] != "tree", "AVL Tree must not resolve to ML Decision Tree node"
        assert res[0] in {"GENERAL_EXPLANATION", "CURRICULUM_UNINDEXED"}
        assert res[3].get("hide_graph") is True
        assert "AVL Tree" in res[1]

    def test_context_free_languages_does_not_resolve_to_react_context(self, engine: Engine) -> None:
        """Verify CFL does not falsely resolve to ReAct prompt context ('context')."""
        res = engine._route("Context-free languages")
        assert res[2] != "context", "Context-free languages must not resolve to prompt context node"
        assert res[0] in {"GENERAL_EXPLANATION", "CURRICULUM_UNINDEXED"}
        assert res[3].get("hide_graph") is True

    def test_core_cs_topics_are_not_out_of_domain(self, engine: Engine) -> None:
        """Verify LLVM SSA, Post Correspondence Problem, and zk-SNARKs are recognized as in-domain."""
        for query in ["LLVM SSA", "Post Correspondence Problem", "zk-SNARKs"]:
            res = engine._route(query)
            assert res[0] != "GUARDRAIL_INTERCEPT" or res[3].get("reason") != "cosine_below_0.75", (
                f"{query} was falsely classified as outside Computer Science"
            )
            assert res[0] in {"GENERAL_EXPLANATION", "CURRICULUM_UNINDEXED", "GRAPH_SYNTHESIS"}

    def test_artificial_intelligence_catalog_lookup(self, engine: Engine) -> None:
        """Verify Artificial Intelligence: A Modern Approach resolves to catalog record."""
        res = engine._route("Artificial Intelligence: A Modern Approach")
        assert res[0] in {"BOOK_PAGE", "CATALOG_SHELF_ROUTING", "LIBRARY_LOOKUP"}
        assert "Russell" in res[1] or "Artificial Intelligence" in res[1]

    def test_synthetic_textbook_citations_have_no_broken_links(self, engine: Engine) -> None:
        """Verify citations from textbooks/*.pdf do not emit 404 reader URLs."""
        ans = engine.answer("What is deadlock?")
        citations = ans["payload"].get("citations", [])
        for c in citations:
            doc_id = str(c.get("doc_id") or "")
            if doc_id.startswith("textbooks/"):
                assert not c.get("url"), f"Synthetic citation {c} must not have a reader URL"
                assert c.get("verification_status") == "Source linked — not independently audited"

    def test_combined_books_and_papers_query(self, engine: Engine) -> None:
        """Verify combined query attributes both library books and research literature."""
        res = engine._route("Find papers and UEM library books about deadlocks.")
        assert res[0] == "LIBRARY_LOOKUP"
        text = res[1]
        assert "catalog" in text.lower() or "books" in text.lower()
        assert "research" in text.lower() or "literature" in text.lower()
