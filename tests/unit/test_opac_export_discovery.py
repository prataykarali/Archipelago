"""OPAC discovery reads the local Koha export without network access."""

from __future__ import annotations

from archipelago.scholarly.discovery.opac_adapter import OPACAdapter


def test_opac_discovery_uses_export_without_network(monkeypatch) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("OPAC network request attempted")

    monkeypatch.setattr("urllib.request.urlopen", reject_network)
    rows = OPACAdapter().search("computer", limit=2)
    assert rows
    assert len(rows) <= 2
    assert all(row["retrieval_mode"] == "export_snapshot" for row in rows)
    assert all("biblionumber=" in str(row["catalog_url"]) for row in rows)
