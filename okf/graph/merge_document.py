"""Merge uploaded-document OKF results into the live corpus artifacts."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from okf.config import BASE_DIR

logger = logging.getLogger(__name__)


def load_okf_results(path: Path | str) -> list[dict[str, Any]]:
    """Load okf_results.json; return [] if missing or invalid."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        rows = data.get("results") or data.get("concepts") or []
        return [row for row in rows if isinstance(row, dict)]
    return []


def doc_ids_in_results(results: list[dict[str, Any]]) -> set[str]:
    """Unique document ids present in OKF result rows."""
    ids: set[str] = set()
    for row in results:
        doc_id = row.get("doc_id") or row.get("document_id") or ""
        if doc_id:
            ids.add(str(doc_id))
    return ids


def merge_okf_results(
    prior: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append incoming rows, dropping exact (doc_id, chunk_id, concept_name) dupes."""
    seen: set[tuple[str, str, str]] = set()
    merged: list[dict[str, Any]] = []
    for row in list(prior) + list(incoming):
        key = (
            str(row.get("doc_id") or ""),
            str(row.get("chunk_id") or ""),
            str(row.get("concept_name") or row.get("name") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def write_okf_results_atomic(path: Path | str, results: list[dict[str, Any]]) -> None:
    """Write results JSON via a temp file then replace."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, dest)


def assert_merge_safe(
    prior_doc_ids: set[str],
    merged_ids: set[str],
    uploading_doc_id: str,
) -> None:
    """Refuse a merge that would drop previously ingested documents."""
    if not uploading_doc_id:
        raise ValueError("upload doc_id is empty")
    lost = prior_doc_ids - merged_ids
    if lost:
        raise ValueError(
            f"merge would drop {len(lost)} existing document(s): {sorted(lost)[:8]}"
        )


def upsert_upload_inventory_meta(
    meta: dict[str, Any],
    dest_rel: str,
    graph_ready: bool = False,
    base_dir: Path | str | None = None,
) -> Path:
    """Record one librarian upload in ``pdfs/upload_inventory.json``.

    Args:
        meta: Upload metadata (title, kind, doc_id, …). Must not be empty.
        dest_rel: Path of the stored file relative to ``pdfs/``, e.g.
            ``"papers/attention.pdf"``.
        graph_ready: True only once the upload has been merged into the live
            graph. Rows with ``graph_ready=False`` are listed in the librarian
            inventory but must not be treated as searchable sources.
        base_dir: Repository root; defaults to :data:`okf.config.BASE_DIR`.

    Returns:
        Path to the written inventory file.

    The row is keyed on the destination path, so re-uploading the same file
    updates the existing row instead of appending a duplicate — that is what
    makes a repeated ingestion idempotent.
    """
    if not isinstance(meta, dict) or not meta:
        raise ValueError("upload metadata must be a non-empty dict")
    if not dest_rel:
        raise ValueError("dest_rel is required")

    folder = Path(base_dir if base_dir is not None else BASE_DIR) / "pdfs"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "upload_inventory.json"

    existing: list[dict[str, Any]] = []
    if out.is_file():
        try:
            loaded = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = [row for row in loaded if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError):
            logger.warning("Discarding unreadable upload inventory at %s", out)
            existing = []

    kept = [row for row in existing if row.get("path") != dest_rel]
    record = dict(meta)
    record["path"] = dest_rel
    record["graph_ready"] = bool(graph_ready)
    kept.append(record)

    out.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
