"""Scientific PDF Structure Parser.

Extracts text, page numbers, bounding boxes, and section headings from scientific PDFs using PyMuPDF.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

logger = logging.getLogger("archipelago.scholarly.parser")

SECTION_PATTERNS = [
    (r"(?i)^(?:1\.?\s*)?abstract\b", "abstract"),
    (r"(?i)^(?:1\.?\s*)?introduction\b", "introduction"),
    (r"(?i)^(?:2\.?\s*)?related\s+work\b", "related_work"),
    (r"(?i)^(?:[2-4]\.?\s*)?(?:methodology|method|model|approach|architecture)\b", "methods"),
    (r"(?i)^(?:[3-5]\.?\s*)?(?:experiments|experimental\s+setup|evaluation)\b", "experiments"),
    (r"(?i)^(?:[4-6]\.?\s*)?(?:results|analysis|discussion)\b", "results"),
    (r"(?i)^(?:[5-7]\.?\s*)?(?:ablation\s+study|ablations)\b", "ablation"),
    (r"(?i)^(?:[6-8]\.?\s*)?(?:limitations|failure\s+modes)\b", "limitations"),
    (r"(?i)^(?:[7-9]\.?\s*)?(?:conclusion|concluding\s+remarks)\b", "conclusion"),
]


class PDFParser:
    """Parses scientific PDFs into structured sections and page spans."""

    def parse_pdf(self, pdf_path: str | Path, artifact_sha256: str) -> dict[str, Any]:
        """Parse PDF file into sections, page texts, and provenance spans."""
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is not installed.")

        doc = fitz.open(str(pdf_path))
        num_pages = len(doc)
        pages_data = []
        sections: dict[str, list[dict[str, Any]]] = {}
        current_section = "preamble"

        for page_idx in range(num_pages):
            page = doc[page_idx]
            page_num = page_idx + 1
            blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

            for b in blocks:
                if len(b) < 5:
                    continue
                x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4].strip()
                if not text:
                    continue

                # Check if block is a section header
                matched_sec = self._detect_section(text)
                if matched_sec:
                    current_section = matched_sec

                span_record = {
                    "page": page_num,
                    "section": current_section,
                    "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                    "text": text,
                    "char_start": 0,
                    "char_end": len(text),
                }

                if current_section not in sections:
                    sections[current_section] = []
                sections[current_section].append(span_record)

            pages_data.append(
                {
                    "page": page_num,
                    "text": page.get_text(),
                }
            )

        doc.close()

        return {
            "num_pages": num_pages,
            "artifact_sha256": artifact_sha256,
            "pages": pages_data,
            "sections": sections,
        }

    def _detect_section(self, text: str) -> str | None:
        """Check if text is a section header."""
        first_line = text.split("\n")[0].strip()
        if len(first_line) > 60:
            return None
        for pattern, sec_name in SECTION_PATTERNS:
            if re.match(pattern, first_line):
                return sec_name
        return None
