"""Build source-checked academic and research SLM examples from arXiv abstracts."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import xml.etree.ElementTree as ET

import requests

from archipelago.scholarly.contracts.okf_v2_fields import PARAMETER_FIELDS
from archipelago.scholarly.extraction.abstract_fields import ALLOWED_FIELDS, PROMPT_PATH
from archipelago.scholarly.extraction.slm_paper_fields import EXTRACTABLE_GROUPS
from archipelago.scholarly.extraction.slm_paper_fields import PROMPT_PATH as PDF_PROMPT
from okf.academic_prompt import academic_messages
from training.dual_ingest_manifest import PAPERS, PaperAnnotation

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "datasets" / "dual_ingest_v1"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}
REQUEST_TIMEOUT_SECONDS = 45
MAX_SOURCE_CHARS = 1800
MAX_QUOTE_FIELDS = 4
PDF_SPAN_PAGE = 0  # Abstract API content has no PDF page.
ABSTRACT_SECTION = "abstract"
VARIANTS = ("complete", "evidence_sentences")


def _normalize(value: str) -> str:
    """Collapse arXiv XML line wrapping without changing the cited words."""
    return " ".join(value.replace("\\%", "%").replace("\\&", "&").split())


def fetch_sources() -> dict[str, dict[str, str]]:
    """Read the exact reviewed identifiers from arXiv's official API."""
    response = requests.get(
        ARXIV_ENDPOINT,
        params={
            "id_list": ",".join(paper.arxiv_id for paper in PAPERS),
            "max_results": len(PAPERS),
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    sources: dict[str, dict[str, str]] = {}
    for entry in ET.fromstring(response.content).findall("atom:entry", ATOM):
        source_url = entry.findtext("atom:id", "", ATOM)
        identifier = re.sub(r"v\d+$", "", source_url.rsplit("/", 1)[-1])
        sources[identifier] = {
            "url": source_url,
            "title": _normalize(entry.findtext("atom:title", "", ATOM)),
            "abstract": _normalize(entry.findtext("atom:summary", "", ATOM)),
        }
    missing = {paper.arxiv_id for paper in PAPERS} - sources.keys()
    if missing:
        raise ValueError(f"arXiv returned no record for: {sorted(missing)}")
    return sources


def _sentences(abstract: str) -> list[str]:
    """Keep complete citation spans for literal substring checks."""
    return [
        sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", abstract) if sentence.strip()
    ]


def _evidence(abstract: str, value: str) -> str:
    """Find an exact source sentence containing the annotation."""
    matched = next(
        (sentence for sentence in _sentences(abstract) if value.casefold() in sentence.casefold()),
        None,
    )
    if matched is None:
        raise ValueError(f"Annotation {value!r} is absent from its source abstract")
    return matched


def _validated_fields(paper: PaperAnnotation, abstract: str) -> list[dict[str, str]]:
    """Reject unsupported field names and labels without literal evidence."""
    fields = []
    for group, field, value in paper.fields:
        if group not in PARAMETER_FIELDS or field not in PARAMETER_FIELDS[group]:
            raise ValueError(f"Unknown OKF field: {group}.{field}")
        fields.append(
            {
                "group": group,
                "field": field,
                "value": value,
                "evidence_text": _evidence(abstract, value),
            }
        )
    if paper.concept.casefold() not in abstract.casefold():
        raise ValueError(f"Central concept missing from {paper.arxiv_id}: {paper.concept}")
    if not fields:
        raise ValueError(f"No research fields for {paper.arxiv_id}")
    return fields


def _source_text(source: dict[str, str], fields: list[dict[str, str]], variant: str) -> str:
    """Build a full abstract or a shorter evidence-only passage."""
    if variant == "complete":
        return source["abstract"][:MAX_SOURCE_CHARS]
    selected = list(dict.fromkeys(field["evidence_text"] for field in fields))
    return " ".join(selected)[:MAX_SOURCE_CHARS]


def _academic_row(
    paper: PaperAnnotation, source: dict[str, str], text: str, variant: str
) -> dict[str, Any]:
    """Label the central teachable concept in the production eight-key contract."""
    evidence = _evidence(text, paper.concept)
    concept = {
        "concept_name": paper.concept,
        "concept_type": paper.concept_type,
        "difficulty": "intermediate",
        "summary": evidence,
        "prerequisites": [],
        "unlocks": [],
        "related_to": [],
        "tags": [],
    }
    return {
        "task": "academic_okf",
        "paper_id": paper.arxiv_id,
        "variant": variant,
        "source_url": source["url"],
        "gold_concepts": [paper.concept],
        "messages": [
            *academic_messages(text, source["title"]),
            {"role": "assistant", "content": json.dumps([concept], ensure_ascii=False)},
        ],
    }


def _research_rows(
    paper: PaperAnnotation,
    source: dict[str, str],
    text: str,
    fields: list[dict[str, str]],
    variant: str,
) -> list[dict[str, Any]]:
    """Create abstract and quote-span tasks with independently checkable targets."""
    selected = [field for field in fields if field["value"].casefold() in text.casefold()]
    abstract_fields = [
        {key: field[key] for key in ("group", "field", "value")}
        for field in selected
        if (field["group"], field["field"]) in ALLOWED_FIELDS
    ][:MAX_QUOTE_FIELDS]
    common = {"paper_id": paper.arxiv_id, "variant": variant, "source_url": source["url"]}
    abstract_row = {
        **common,
        "task": "research_abstract",
        "gold_fields": abstract_fields,
        "messages": [
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": text},
            {
                "role": "assistant",
                "content": json.dumps({"fields": abstract_fields}, ensure_ascii=False),
            },
        ],
    }
    registry = {group: PARAMETER_FIELDS[group] for group in sorted(EXTRACTABLE_GROUPS)}
    spans = [
        {"pdf_page": PDF_SPAN_PAGE, "section": ABSTRACT_SECTION, "text": sentence}
        for sentence in dict.fromkeys(field["evidence_text"] for field in selected)
    ]
    quote_fields = [
        {**field, "pdf_page": PDF_SPAN_PAGE, "section": ABSTRACT_SECTION} for field in selected
    ]
    quote_row = {
        **common,
        "task": "research_quote_spans",
        "gold_fields": quote_fields,
        "messages": [
            {"role": "system", "content": PDF_PROMPT.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps({"registry": registry, "spans": spans})},
            {
                "role": "assistant",
                "content": json.dumps({"fields": quote_fields}, ensure_ascii=False),
            },
        ],
    }
    return [abstract_row, quote_row]


def build(output: Path, sources: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Write immutable paper-level splits and a source/label audit report."""
    output.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    source_checksums: dict[str, str] = {}
    for paper in PAPERS:
        source = sources[paper.arxiv_id]
        source_checksums[paper.arxiv_id] = hashlib.sha256(source["abstract"].encode()).hexdigest()
        fields = _validated_fields(paper, source["abstract"])
        for variant in VARIANTS:
            text = _source_text(source, fields, variant)
            rows[paper.split].append(_academic_row(paper, source, text, variant))
            rows[paper.split].extend(_research_rows(paper, source, text, fields, variant))
    for split, split_rows in rows.items():
        path = output / f"{split}.jsonl"
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in split_rows),
            encoding="utf-8",
        )
    split_ids = {
        split: {row["paper_id"] for row in split_rows} for split, split_rows in rows.items()
    }
    if any(
        split_ids[first] & split_ids[second] for first in rows for second in rows if first < second
    ):
        raise ValueError("Paper-level split leakage")
    report = {
        "source": ARXIV_ENDPOINT,
        "papers": {split: sorted(identifiers) for split, identifiers in split_ids.items()},
        "rows": {
            split: dict(Counter(row["task"] for row in split_rows))
            for split, split_rows in rows.items()
        },
        "source_sha256": source_checksums,
        "annotation_policy": "literal source substring plus reviewed semantic field type",
        "test_is_never_used_by_trainer": True,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    """Fetch reviewed source records, validate labels, and write splits."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.output, fetch_sources()), indent=2))


if __name__ == "__main__":
    main()
