"""Map Kùzu evidence rows to the shared citation contract."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _row_to_evidence(row: list[Any]) -> dict[str, Any]:
    """Map an _EVIDENCE_RETURN result row to the shared evidence contract."""
    block_vals = row[7:11]
    block_bbox = [float(v) for v in block_vals] if all(v is not None for v in block_vals) else None
    page_label_map = None
    if row[12]:
        try:
            parsed = json.loads(row[12])
            if isinstance(parsed, dict) and parsed:
                page_label_map = parsed
        except (ValueError, TypeError):
            logger.debug("Ignoring malformed page label map", exc_info=True)
    return {
        "chunk_id": row[0],
        "doc_id": row[1],
        "page_number": int(row[2]) if row[2] is not None else 0,
        "section_title": row[3],
        "text": row[4],
        "text_offset_start": int(row[5]) if row[5] is not None else None,
        "text_offset_end": int(row[6]) if row[6] is not None else None,
        "block_bbox": block_bbox,
        "doc_title": row[11],
        "page_label_map": page_label_map,
    }
