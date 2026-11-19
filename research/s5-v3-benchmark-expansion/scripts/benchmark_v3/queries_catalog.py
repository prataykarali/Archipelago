"""Combined 48-query proposed S5-v3 benchmark catalog."""

from __future__ import annotations

from .builder import QueryDraft
from .catalog_dev import get_dev_query_drafts
from .catalog_test_cross import get_test_cross_doc_drafts
from .catalog_test_para_neg import get_test_paraphrase_and_neg_drafts
from .catalog_test_single_same import get_test_single_and_same_doc_drafts


def get_proposed_query_drafts() -> list[QueryDraft]:
    """Return all 48 proposed S5-v3 query drafts (16 dev, 32 test)."""
    return [
        *get_dev_query_drafts(),
        *get_test_single_and_same_doc_drafts(),
        *get_test_cross_doc_drafts(),
        *get_test_paraphrase_and_neg_drafts(),
    ]
