"""Offline preflight and real OCR probe; does not download, retrain or publish a model."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shutil
import time

PROBE_TEXT = (
    "Linear algebra studies vectors and matrices. "
    "Dot product similarity compares vector directions. "
    "Matrix multiplication combines rows and columns."
)


def run_ocr_probe() -> dict:
    """Measure word overlap on a generated scanned PDF using actual local OCR."""
    if shutil.which("tesseract") is None:
        return {
            "status": "blocked",
            "reason": "Tesseract binary is unavailable.",
            "word_recall": None,
        }
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    from archipelago.ingestion.ocr import page_blocks

    image = Image.new("RGB", (1600, 600), "white")
    font_path = "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf"
    font = ImageFont.truetype(font_path, 30)
    draw = ImageDraw.Draw(image)
    sentences = PROBE_TEXT.split(". ")
    for i, line in enumerate(sentences):
        draw.text((50, 60 + i * 90), line, font=font, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    doc = fitz.open()
    try:
        page = doc.new_page(width=800, height=300)
        page.insert_image(page.rect, stream=buffer.getvalue())
        blocks, used = page_blocks(page)
        result = " ".join(
            span["text"] for b in blocks for line in b["lines"] for span in line["spans"]
        )
        import re

        expected = set(re.findall(r"[a-z]+", PROBE_TEXT.lower()))
        observed = set(re.findall(r"[a-z]+", result.lower()))
        recall = len(expected & observed) / len(expected)
        return {
            "status": "tested",
            "synthetic": True,
            "ocr_used": used,
            "word_recall": round(recall, 4),
            "recognized_text": result,
            "scope": "One generated clean English scan, not institutional OCR quality.",
        }
    finally:
        doc.close()


def model_preflight(path: Path) -> dict:
    """Distinguish absent config/weights/LFS pointers from an actually loadable model."""
    if not path.is_dir():
        return {"status": "blocked", "reason": "Model directory is missing.", "path": str(path)}
    config = path / "config.json"
    weights = list(path.glob("*.safetensors")) + list(path.glob("pytorch_model*.bin"))
    if not config.is_file() or not weights:
        return {
            "status": "blocked",
            "reason": "Model configuration or weights are missing.",
            "path": str(path),
        }
    for file in weights:
        with file.open("rb") as stream:
            if stream.read(128).startswith(b"version https://git-lfs.github.com/spec/v1"):
                return {"status": "blocked", "reason": "Model weights are unhydrated LFS pointers."}
    return {"status": "available_not_loaded", "path": str(path), "weight_files": len(weights)}


def main() -> None:
    """Produce an honest preflight report without substituting mocks for model metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "timestamp_epoch": time.time(),
        "model": model_preflight(args.model),
        "node_extraction": None,
        "edge_extraction": None,
        "json_validity": None,
        "hallucination_rate": None,
        "overall_score": None,
        "model_evaluation": "not_run",
        "model_note": "Run eval_lib_qwen_ingestion.py with approved weights and labelled evaluation data. No retraining.",
        "ocr": run_ocr_probe(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
