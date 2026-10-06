"""The library HTTP receiver must share its graph export with the appliance."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_library_receiver_links_export_before_loading_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from archipelago.apps import inference_app
    import ingestion_worker
    from scripts import run_ingestion_worker

    calls: list[str] = []
    monkeypatch.setenv("ARCHIPELAGO_ENV", "library")
    monkeypatch.setenv("ARCHIPELAGO_LOAD_EMBEDDINGS", "0")
    monkeypatch.setenv("ARCHIPELAGO_LOAD_AURA", "0")
    monkeypatch.setattr(inference_app, "_runtime_started", False)
    monkeypatch.setattr(
        run_ingestion_worker,
        "ensure_shared_graph_export",
        lambda: calls.append("link"),
    )
    monkeypatch.setattr(
        inference_app,
        "init_concepts_data",
        lambda: calls.append("load"),
    )
    monkeypatch.setattr(
        ingestion_worker,
        "get_worker",
        lambda: calls.append("worker"),
    )

    app = inference_app.create_app()
    assert app is inference_app.app
    assert calls == ["link", "load", "worker"]
    inference_app.create_app()
    assert calls == ["link", "load", "worker"]
