"""Regression: topic-specific ranking must not fall back to global AIML top."""
from catalog_ranking import rank_documents, format_ranking_response


def test_sql_topic_does_not_return_attention_paper():
    results = rank_documents(topic="SQL", parameter="composite", top_k=5)
    titles = " ".join((r.get("title") or "") for r in results).lower()
    # Either empty (hard miss) or SQL/DBMS-related — never the global ML leaderboard alone
    if results:
        assert "attention is all you need" not in titles or any(
            t in titles for t in ("sql", "database", "dbms", "relational")
        )
    # Hard miss is acceptable when catalog has no SQL tags
    assert isinstance(results, list)


def test_specific_topic_hard_miss_returns_empty():
    results = rank_documents(topic="zzzxxyy_not_a_real_topic", parameter="composite", top_k=5)
    assert results == []


def test_format_ranking_miss_does_not_dump_global_top():
    text = format_ranking_response(topic="zzzxxyy_not_a_real_topic", parameter="composite", top_k=5)
    assert "Attention Is All You Need" not in text
    assert "No catalog documents matched" in text


def test_global_rank_still_works_without_topic():
    results = rank_documents(topic=None, parameter="composite", top_k=3)
    assert len(results) >= 1
