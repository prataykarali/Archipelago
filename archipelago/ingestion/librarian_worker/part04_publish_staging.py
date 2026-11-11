"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

import os
from typing import Any

from archipelago.graph.engine import KuzuGraphEngine
from archipelago.storage.hf_remote import HFStorageClient

from . import _deps as _rt


def publish_staging(
    approved_edges: list[dict[str, str]] | None = None,
    rejected_edges: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Publish curated staging database to production:
    1. Applies any librarian edge rejections in staging DB.
    2. Synchronizes vector embeddings for all concepts (Pitfall 2 fix).
    3. Executes connection-safe atomic swap: KuzuGraphEngine.atomic_swap(_rt.STAGING_DB_PATH, _rt.PROD_DB_PATH).
    4. Syncs JSON export & triggers inference server reload.
    """
    if not _rt.STAGING_DB_PATH.exists():
        raise FileNotFoundError(f"Staging database {_rt.STAGING_DB_PATH} not found.")

    # 1. Apply librarian edge rejections if provided
    if rejected_edges:
        staging_engine = KuzuGraphEngine(db_path=_rt.STAGING_DB_PATH, read_only=False)
        try:
            for rej in rejected_edges:
                u = rej.get("from_id")
                v = rej.get("to_id")
                if u and v:
                    staging_engine.conn.execute(
                        f"MATCH (a:Concept {{id: '{u}'}})-[r:REQUIRES]->(b:Concept {{id: '{v}'}}) DELETE r"
                    )
        except Exception as exc:
            _rt.logger.warning("Error applying rejected edges in staging: %s", exc)
        finally:
            staging_engine.close()

    # 2. Export staging graph → JSON, then rebuild embeddings BEFORE swap
    #    so the 0.75 firewall already knows newly approved concepts.
    _rt.logger.info(
        "Exporting staging concepts and synchronizing arctic-embed cache before swap..."
    )
    try:
        _rt.sync_embeddings_from_db(_rt.STAGING_DB_PATH)
    except Exception as embed_err:
        _rt.logger.warning("Embedding synchronization notice: %s", embed_err)

    # 3. Connection-safe Atomic Swap (Pitfall 1 Fix)
    # Drop the other-process inference handle first; in-process handles are
    # closed inside KuzuGraphEngine.atomic_swap.
    _rt.notify_inference_close()
    _rt.logger.info(
        "Executing zero-downtime atomic swap %s -> %s...", _rt.STAGING_DB_PATH, _rt.PROD_DB_PATH
    )
    KuzuGraphEngine.atomic_swap(_rt.STAGING_DB_PATH, _rt.PROD_DB_PATH)

    # 4. Re-open the live inference Kùzu handle onto the swapped file
    reload_info = _rt.notify_inference_reload(embeddings_only=False)

    graph_sync: dict[str, str] = {"status": "skipped", "reason": "HF_TOKEN missing"}
    if os.getenv("HF_TOKEN"):
        try:
            client = HFStorageClient(
                repo_id=os.getenv("ARCHIPELAGO_SCHOLARLY_HF_REPO", "Prataykarali/graphier")
            )
            result = client.upload_file(_rt.DATA_FILE, "graph/okf_graph.json")
            graph_sync = {"status": "published" if result["mode"] == "hf_hub" else "skipped"}
        except Exception as exc:
            _rt.logger.exception("Graphier publication failed after local graph swap")
            graph_sync = {"status": "failed", "reason": type(exc).__name__}

    return {
        "success": True,
        "message": "Zero-downtime atomic database swap completed successfully.",
        "prod_db_path": str(_rt.PROD_DB_PATH),
        "inference_reload": reload_info,
        "graphier": graph_sync,
    }
