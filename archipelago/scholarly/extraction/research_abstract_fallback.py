"""Conservative quote-matched abstract fallback fields."""

from __future__ import annotations

import re
from typing import Any

MIN_TECHNIQUE_CHARS = 20
MAX_PROBLEM_CHARS = 180


def extract_fallback_abstract_fields(abstract: str) -> list[dict[str, Any]]:
    if not abstract or len(abstract.strip()) < 20:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", abstract.strip())
    results: list[dict[str, Any]] = []

    for sentence in sentences:
        s_clean = sentence.strip()
        s_lower = s_clean.casefold()

        purpose = re.search(
            r"\b(?:the )?(?:purpose|aim|objective) of this (?:paper|study|work) is to\s+([^.;]+)",
            s_clean,
            re.I,
        )
        if purpose:
            value = purpose.group(1).strip()
            if 8 <= len(value) <= MAX_PROBLEM_CHARS:
                results.append(
                    {
                        "group": "methodology",
                        "field": "research_problem",
                        "value": value,
                        "evidence_text": s_clean,
                        "verification_status": "abstract_quote_matched",
                        "source_api": "abstract_span_extractor",
                    }
                )

        # Preserve an explicitly stated aim or contribution as a literal
        # abstract span. An aim is not treated as an achieved result.
        statement = re.search(
            r"\b(?:this (?:paper|study|work|research)|we)\s+"
            r"(aims?\s+(?:to|at)|propos(?:e|es|ed)|present(?:s|ed)?|"
            r"introduc(?:e|es|ed)|develop(?:s|ed)?|investigat(?:e|es|ed)|"
            r"evaluat(?:e|es|ed))\s+([^.;]+)",
            s_clean,
            re.I,
        )
        if statement:
            value = statement.group(2).strip()
            if 8 <= len(value) <= 150 and value in s_clean:
                is_aim = statement.group(1).casefold().startswith(("aim", "investigat"))
                results.append(
                    {
                        "group": "methodology",
                        "field": "research_problem" if is_aim else "contributions",
                        "value": value,
                        "evidence_text": s_clean,
                        "verification_status": "abstract_quote_matched",
                        "source_api": "abstract_span_extractor",
                    }
                )

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
                r"(?:propose|present|introduce|develop|employ|utilize|use|based on)\s+"
                r"([a-zA-Z0-9\s,-]+?)(?:\b(?:for|to|with|in|that)\b|[.,])",
                s_clean,
                re.I,
            )
            val = m.group(1).strip() if m else None
            if val and MIN_TECHNIQUE_CHARS <= len(val) <= 120 and val in s_clean:
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
        if not statement and any(
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
                r"(?:we demonstrate|we show|key findings?\s+(?:are|include)|"
                r"contributions?\s+(?:include|are))\s+([^.;]+)",
                s_clean,
                re.I,
            )
            val = m.group(1).strip() if m else None
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
                created = re.search(
                    r"\b(?:creat\w*|releas\w*|introduc\w*|present\w*|crowdsourc\w*)\s+"
                    r"(?:a|the)\s+([A-Z][A-Za-z0-9\s-]+?\s+(?:dataset|benchmark|corpus))\b",
                    s_clean,
                )
                val = created.group(1).strip() if created else None
            if not val:
                m2 = re.search(r"([A-Z][A-Za-z0-9-]+\s+(?:dataset|benchmark|corpus))\b", s_clean)
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
