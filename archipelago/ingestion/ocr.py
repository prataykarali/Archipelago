"""Local bounded OCR for scanned PDF pages; no remote document transmission."""

from __future__ import annotations

import io
import shutil

MAX_PIXELS = 12_000_000
OCR_DPI = 180
OCR_TIMEOUT_SECONDS = 20
MIN_TEXT_CHARS = 32


def page_blocks(page) -> tuple[list[dict], bool]:
    """Return native text blocks, or OCR blocks when a scanned page has no text.

    Missing OCR dependencies fail explicitly instead of silently claiming that
    an image-only PDF has been ingested successfully.
    """
    blocks = page.get_text("dict")["blocks"]
    native = "".join(
        span["text"]
        for block in blocks
        for line in block.get("lines", [])
        for span in line.get("spans", [])
    )
    if len(native.strip()) >= MIN_TEXT_CHARS or not page.get_images():
        return blocks, False
    if shutil.which("tesseract") is None:
        raise RuntimeError("Scanned PDF requires local Tesseract OCR. Install tesseract-ocr.")
    from PIL import Image
    import pytesseract

    scale = OCR_DPI / 72
    pixels = page.rect.width * page.rect.height * scale * scale
    if pixels > MAX_PIXELS:
        scale *= (MAX_PIXELS / pixels) ** 0.5
    import fitz

    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
        text = pytesseract.image_to_string(image, timeout=OCR_TIMEOUT_SECONDS).strip()
    if not text:
        raise ValueError(f"OCR extracted no readable text from PDF page {page.number + 1}.")
    rect = page.rect
    return [
        {
            "bbox": (rect.x0, rect.y0, rect.x1, rect.y1),
            "lines": [{"spans": [{"text": text, "size": 0, "font": "OCR"}]}],
        }
    ], True
