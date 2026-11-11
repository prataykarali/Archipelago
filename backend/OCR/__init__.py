"""Local OCR ingestion for scanned book index and content pages."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("archipelago.ocr")

def perform_ocr(image_or_pdf_path: str | Path) -> str:
    """Extract text from scanned page image or document using local Tesseract OCR."""
    path = Path(image_or_pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(path)
        return pytesseract.image_to_string(img)
    except Exception as exc:
        logger.warning("Local OCR extraction failed on %s: %s", path, exc)
        return ""

__all__ = ["perform_ocr"]
