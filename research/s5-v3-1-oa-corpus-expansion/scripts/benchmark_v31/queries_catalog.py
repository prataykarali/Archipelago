"""Combined 72-query S5-v3.1 multi-domain proposed benchmark catalog."""

from __future__ import annotations

from .builder import QueryDraft
from .catalog_v3_retained import get_retained_v3_drafts
from .catalog_v31_cs_dev import get_new_cs_dev_drafts
from .catalog_v31_cs_test_core import get_new_cs_test_core_drafts
from .catalog_v31_cs_test_cross_nc import get_new_cs_test_cross_nc_drafts


def get_proposed_v31_query_drafts() -> list[QueryDraft]:
    """Return all 72 proposed S5-v3.1 query drafts (24 dev, 48 test)."""
    return [
        *get_retained_v3_drafts(),
        *get_new_cs_dev_drafts(),
        *get_new_cs_test_core_drafts(),
        *get_new_cs_test_cross_nc_drafts(),
    ]
