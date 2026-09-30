"""Unit tests for Resource Sync and Reconciliation command."""
from __future__ import annotations

import pytest
from archipelago.resolver.sync import sync_all_resources
from archipelago.resolver.resource_registry import get_registry

pytestmark = pytest.mark.unit


def test_sync_all_resources_reconciliation_numbers():
    """Verify sync_all_resources reconciles the complete 46-resource corpus."""
    stats, details = sync_all_resources(verbose=False)

    assert stats["total"] == 46
    assert stats["pearson"] == 40
    assert stats["huggingface"] == 2
    assert stats["local"] == 2
    assert stats["metadata_only"] == 2

    # At least 45 resources resolve cleanly
    assert stats["resolved"] >= 44
    assert stats["missing"] <= 2
    assert stats["duplicates"] == 0

    assert len(details) == 46


def test_sync_details_contain_required_fields():
    """Verify each sync detail entry contains id, source, symbol, title, and status."""
    stats, details = sync_all_resources(verbose=False)

    for entry in details:
        assert "id" in entry
        assert "source" in entry
        assert "symbol" in entry
        assert "title" in entry
        assert "status" in entry
        assert entry["symbol"] in ("✓", "✗", "⚠", "ⓘ")
