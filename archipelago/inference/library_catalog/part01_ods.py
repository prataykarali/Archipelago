"""ODS parsing and shelf-dedup primitives for the library catalog."""

from __future__ import annotations

import logging
from pathlib import Path
import re
from defusedxml import ElementTree as ET  # hardened: untrusted ODS XML
import zipfile

logger = logging.getLogger("archipelago.inference.library_catalog_api")

CATALOG_COLORS = (
    ("#2563eb", "#93c5fd"),
    ("#7c3aed", "#c4b5fd"),
    ("#059669", "#6ee7b7"),
    ("#d97706", "#fde68a"),
    ("#dc2626", "#fca5a5"),
    ("#0891b2", "#67e8f9"),
)

_ODS_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_ODS_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_ODS_REPEAT_ATTR = f"{{{_ODS_TABLE_NS}}}number-columns-repeated"
_MAX_CELL_REPEAT = 10


def display_title(path: str) -> str:
    """Turn a dataset path into a readable title without inventing metadata."""
    stem = Path(path).stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", stem).strip()


def _shelf_key(item: dict) -> str:
    """Collapse mirrors of one resource while preserving distinct catalog titles."""
    if item.get("isPearson"):
        return f"pearson:{item.get('id')}"
    title = str(item.get("title") or item.get("id") or "").lower()
    return re.sub(r"[^a-z0-9]", "", title)


def _deduplicate_shelf(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = _shelf_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def parse_ods_rows(file_path: Path) -> list[list[str]]:
    """Parse an ODS file into rows of string values using standard zipfile + XML."""
    if not file_path.is_file():
        return []
    try:
        with zipfile.ZipFile(file_path) as z:
            content = z.read("content.xml")
        tree = ET.fromstring(content)
        ns = {"table": _ODS_TABLE_NS, "text": _ODS_TEXT_NS}
        rows = []
        for table in tree.findall(".//table:table", ns):
            for row_elem in table.findall(".//table:table-row", ns):
                r = []
                for cell in row_elem.findall(".//table:table-cell", ns):
                    repeat = int(cell.attrib.get(_ODS_REPEAT_ATTR, 1))
                    text_nodes = cell.findall(".//text:p", ns)
                    val = " ".join([tn.text for tn in text_nodes if tn.text])
                    r.extend([val] * min(repeat, _MAX_CELL_REPEAT))
                while r and not r[-1]:
                    r.pop()
                if r:
                    rows.append(r)
        return rows
    except Exception as exc:
        logger.warning("Failed to parse ODS file %s: %s", file_path, exc)
        return []


def resolve_ods_locations(arch_dir: Path) -> list[Path]:
    """Return candidate directories for Koha ODS exports, most specific first."""
    return [arch_dir, arch_dir / "data" / "koha", arch_dir.parent]


def find_ods(ods_locations: list[Path], filename: str) -> Path | None:
    """Locate one ODS export across the candidate directories."""
    for loc in ods_locations:
        candidate = loc / filename
        if candidate.is_file():
            return candidate
    return None
