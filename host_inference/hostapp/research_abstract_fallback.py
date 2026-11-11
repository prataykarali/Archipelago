"""Conservative quote-matched abstract fallback fields."""

from __future__ import annotations

import re
from typing import Any


def extract_fallback_abstract_fields(abstract: str) -> list[dict[str, Any]]:
    if not abstract or len(abstract.strip()) < 20:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", abstract.strip())
    results: list[dict[str, Any]] = []

    for sentence in sentences:
        s_clean = sentence.strip()
        s_lower = s_clean.casefold()

        # 1. Methodology techniques
        if any(
            w in s_lower
            for w in (
                "propose",
                "present",
                "introduce",
                "develop",
                "employ",
                "utilize",
                "method",
                "algorithm",
                "architecture",
                "framework",
                "approach",
                "technique",
                "pipeline",
                "model",
            )
        ):
            m = re.search(
                r"(?:propose|present|introduce|develop|employ|utilize|use|based on)\s+([a-zA-Z0-9\s,-]+?)(?:for|to|with|in|that|\.|\,)",
                s_clean,
                re.I,
            )
            val = m.group(1).strip() if m else None
            if val and 3 <= len(val) <= 120 and val in s_clean:
                results.append(
                    {
                        "group": "methodology",
                        "field": "techniques",
                        "value": val,
                        "evidence_text": s_clean,
                        "verification_status": "abstract_quote_matched",
                        "source_api": "abstract_span_extractor",
                    }
                )

        # 2. Contributions
        if any(
            w in s_lower
            for w in (
                "contribution",
                "novel",
                "key finding",
                "this paper",
                "this study",
                "we demonstrate",
                "we show",
            )
        ):
            m = re.search(
                r"(?:this paper|this study|we demonstrate|we show|key finding|contribution[s]?)\s+([a-zA-Z0-9\s,-]+?)(?:\.|\;|\n)",
                s_clean,
                re.I,
            )
            val = m.group(1).strip() if m else (s_clean[:120] if s_clean in abstract else None)
            if val and 5 <= len(val) <= 150 and val in abstract:
                results.append(
                    {
                        "group": "methodology",
                        "field": "contributions",
                        "value": val,
                        "evidence_text": s_clean,
                        "verification_status": "abstract_quote_matched",
                        "source_api": "abstract_span_extractor",
                    }
                )

        # 3. Experiments datasets
        if any(
            w in s_lower
            for w in ("dataset", "benchmark", "corpus", "evaluat", "experiment", "test on")
        ):
            m = re.search(
                r"(?:on the|using the|on)\s+([A-Z][a-zA-Z0-9\s-]+?\s+(?:dataset|benchmark|corpus|data))",
                s_clean,
            )
            val = m.group(1).strip() if m else None
            if not val:
                m2 = re.search(r"([A-Za-z0-9-]+\s+(?:dataset|benchmark|corpus))\b", s_clean, re.I)
                val = m2.group(1).strip() if m2 else None
            if val and 3 <= len(val) <= 80 and val in s_clean:
                results.append(
                    {
                        "group": "experiments",
                        "field": "datasets",
                        "value": val,
                        "evidence_text": s_clean,
                        "verification_status": "abstract_quote_matched",
                        "source_api": "abstract_span_extractor",
                    }
                )

    return results
