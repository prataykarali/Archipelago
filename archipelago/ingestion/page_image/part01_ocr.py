"""Local OCR for scanned book index (TOC) and content pages.

Uses the locally installed Tesseract engine via pytesseract. No external AI call
is made, so a librarian can pre-fill a record on an air-gapped library machine
and this costs zero inference budget (docs/03 §1, docs/02 §1B).
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any

logger = logging.getLogger("archipelago.ingestion.page_image")

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_OCR_PIXELS = 40_000_000
OCR_LANGUAGES = "eng"
OCR_PAGE_SEG_MODE = "6"  # uniform block of text
OCR_DEFAULT_DPI = 300
OCR_MIN_CONFIDENCE = 40.0
# Slack allowed when deciding whether a word starts on the current visual line.
LINE_OVERLAP_TOLERANCE_PX = 6
_TESSERACT_AVAILABLE: bool | None = None

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")

# Accepted upload content types for a page image.
IMAGE_FORMATS = ("PNG", "JPEG", "TIFF", "BMP", "WEBP")


class OCRUnavailable(RuntimeError):
    """Raised when no local OCR engine can be used."""


def is_supported_image(filename: str | None) -> bool:
    """True when the filename looks like a supported raster image."""
    if not filename:
        return False
    return str(filename).lower().endswith(_IMAGE_SUFFIXES)


def ocr_available() -> bool:
    """Report whether local OCR is usable on this machine."""
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None:
        return _TESSERACT_AVAILABLE
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        _TESSERACT_AVAILABLE = True
    except Exception as exc:
        logger.info("Local OCR unavailable (%s); page-image prefill needs text input.", exc)
        _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


def _load_image(data: bytes):
    """Decode bytes into a PIL image, downscaling very large scans."""
    from PIL import Image

    image = Image.open(io.BytesIO(data))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    width, height = image.size
    if width * height > MAX_OCR_PIXELS:
        scale = (MAX_OCR_PIXELS / float(width * height)) ** 0.5
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
    return image


def _run_ocr(image, extra_config: str = "") -> str:
    import pytesseract

    config = f"--psm {OCR_PAGE_SEG_MODE} --dpi {OCR_DEFAULT_DPI}"
    if extra_config:
        config = f"{config} {extra_config}"
    return pytesseract.image_to_string(image, lang=OCR_LANGUAGES, config=config)


def ocr_image_bytes(data: bytes) -> str:
    """OCR an uploaded page image and return plain text."""
    if not data:
        raise OCRUnavailable("No image bytes were supplied.")
    if len(data) > MAX_IMAGE_BYTES:
        raise OCRUnavailable(
            f"Image is larger than the {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit."
        )
    if not ocr_available():
        raise OCRUnavailable(
            "No local OCR engine is installed on this machine. "
            "Install Tesseract, or paste the page text instead."
        )
    image = _load_image(data)
    return _run_ocr(image)


def ocr_text_blocks(data: bytes) -> list[dict[str, Any]]:
    """OCR an image and return positioned word blocks for layout reasoning.

    Returns a list of ``{"text", "conf", "x", "y", "w", "h", "block"}`` entries,
    which the parser uses to find headings (largest/uppermost text) rather than
    guessing from raw line order.
    """
    if not data:
        raise OCRUnavailable("No image bytes were supplied.")
    if len(data) > MAX_IMAGE_BYTES:
        raise OCRUnavailable("Image exceeds the size limit.")
    if not ocr_available():
        raise OCRUnavailable("No local OCR engine is installed on this machine.")
    image = _load_image(data)
    import pytesseract
    from pytesseract import Output

    data_frame = pytesseract.image_to_data(
        image, lang=OCR_LANGUAGES, config=f"--psm {OCR_PAGE_SEG_MODE}", output_type=Output.DICT
    )
    blocks: list[dict[str, Any]] = []
    for i, text in enumerate(data_frame.get("text", [])):
        word = (text or "").strip()
        if not word:
            continue
        try:
            conf = float(data_frame["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < OCR_MIN_CONFIDENCE:
            continue
        blocks.append({
            "text": word,
            "conf": conf,
            "x": int(data_frame["left"][i]),
            "y": int(data_frame["top"][i]),
            "w": int(data_frame["width"][i]),
            "h": int(data_frame["height"][i]),
            "block": int(data_frame["block_num"][i]),
            "line": int(data_frame["line_num"][i]),
        })
    return blocks


def group_lines(blocks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group word blocks into visual lines by vertical overlap.

    Tesseract's own block/line identifiers are unreliable on sparse title pages,
    so lines are reconstructed from word geometry: words whose vertical spans
    overlap belong to the same visual line.
    """
    if not blocks:
        return []

    ordered = sorted(blocks, key=lambda b: (b["y"], b["x"]))
    lines: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_bottom: int | None = None

    for word in ordered:
        top = word["y"]
        bottom = top + max(1, word["h"])
        if current_bottom is None:
            current = [word]
            current_bottom = bottom
            continue
        # Same visual line while this word still overlaps the current line's
        # vertical span; a word starting below it begins a new line.
        if top <= current_bottom + LINE_OVERLAP_TOLERANCE_PX:
            current.append(word)
            current_bottom = max(current_bottom, bottom)
        else:
            lines.append(current)
            current = [word]
            current_bottom = bottom

    if current:
        lines.append(current)
    return [sorted(words, key=lambda w: w["x"]) for words in lines]


def line_text(words: list[dict[str, Any]]) -> str:
    """Join a grouped line into readable text."""
    return re.sub(r"\s+", " ", " ".join(w["text"] for w in words)).strip()
