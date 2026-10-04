"""Publication never copies unreviewed source material or another dataset."""
from __future__ import annotations

import copy
import json

import pytest

from scripts.export_graphier import DESTINATION, export_graph

pytestmark = pytest.mark.unit


def graph() -> dict:
    """Synthetic fixture with no third-party rights dependency."""
    return {
        "nodes": [{
            "id": "one", "label": "One", "summary": "Safe reviewed definition",
            "sources": [{"doc_id": "owned.pdf", "page_number": 2, "text_passage": "NEVER COPY RAW"}],
            "student_history": "NEVER COPY STUDENT",
        }],
        "edges": [{"from_id": "one", "to_id": "unknown", "edge_type": "REQUIRES"}],
    }


def test_export_requires_explicit_rights() -> None:
    assert not export_graph(graph(), set())["nodes"]
    assert DESTINATION == "Prataykarali/graphier"


def test_metadata_only_and_dangling_edges_removed() -> None:
    result = export_graph(graph(), {"owned.pdf"})
    assert len(result["nodes"]) == 1
    assert result["edges"] == []
    encoded = json.dumps(result)
    assert "NEVER COPY" not in encoded and "text_passage" not in encoded
    assert result["nodes"][0]["sources"][0]["page_number"] == 2


def test_private_and_mixed_source_nodes_excluded() -> None:
    data = graph()
    data["nodes"][0]["sources"].append({"doc_id": "private.pdf", "page_number": 1})
    assert not export_graph(data, {"owned.pdf"})["nodes"]
    data = graph()
    data["nodes"][0]["private"] = True
    assert not export_graph(data, {"owned.pdf"})["nodes"]


def test_idempotent_without_mutating_input() -> None:
    data = graph()
    original = copy.deepcopy(data)
    result = export_graph(data, {"owned.pdf"})
    assert result == export_graph(data, {"owned.pdf"})
    assert result == export_graph(result, {"owned.pdf"})
    assert data == original


def test_credential_like_summaries_excluded() -> None:
    data = graph()
    data["nodes"][0]["summary"] = "api_key=DO_NOT_UPLOAD"
    assert not export_graph(data, {"owned.pdf"})["nodes"]
