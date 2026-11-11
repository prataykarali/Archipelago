"""Build a paper-isolated dual-ingestion dataset from live scholarly APIs."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from training.build_dual_ingest_dataset import (
    _academic_row,
    _research_rows,
    _source_text,
    _validated_fields,
    fetch_sources,
)
from training.dual_ingest_manifest import PAPERS, PaperAnnotation
from training.dual_ingest_sources import MIN_ABSTRACT_CHARS, SOURCE_TOPICS, SourcePaper, fetch

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "datasets" / "dual_ingest_multisource_v2"
SOURCE_QUOTA = 35
MIN_PAPERS = 84
MAX_PAPERS = 165
MAX_TITLE_CONCEPT_WORDS = 6
SPLIT_HASH_HEX_CHARS = 8
HASH_RADIX = 16
SPLIT_BUCKETS = 10
TRAIN_BUCKETS = 7
VALIDATION_BUCKET = 7
FETCH_WORKERS = 4
REQUIRED_SOURCES = ("arxiv", "openalex", "crossref", "europe_pmc")
CONTRIBUTION = re.compile(
    r"\b(?:we|this (?:paper|study|work)|here,? we)\s+"
    r"(?:propose|present|introduce|develop|design|describe|report)\b",
    re.IGNORECASE,
)
DATASETS = (
    "ImageNet",
    "CIFAR-10",
    "CIFAR-100",
    "GLUE",
    "SQuAD",
    "COCO",
    "Cora",
    "PubMed",
    "MIMIC-III",
    "UK Biobank",
    "PDB",
    "Reddit",
)
DATASET_CONTEXT = re.compile(r"\b(?:dataset|benchmark|evaluat|train|experiment|test)\w*\b", re.I)
GENERIC_TITLE = re.compile(r"^(?:a|an|the)\s+(?:survey|review|study|analysis|benchmark)\b", re.I)
NON_METHOD_TITLE = re.compile(r"\b(?:survey|review|overview|benchmark|analysis|evaluation)\b", re.I)
METHOD_CONTEXT = re.compile(
    r"\b(?:we|our|this work)\b.{0,100}\b(?:use|using|apply|propose|present|introduce|develop|design|employ|evaluate|train|build)\b",
    re.I,
)


def _source_key(paper: SourcePaper) -> str:
    """Use the title to collapse duplicate DOI and preprint records."""
    return re.sub(r"[^a-z0-9]+", "", paper.title.casefold())


def _split(identifier: str) -> str:
    """Assign every prompt variant for a paper to one immutable split."""
    bucket = (
        int(hashlib.sha256(identifier.encode()).hexdigest()[:SPLIT_HASH_HEX_CHARS], HASH_RADIX)
        % SPLIT_BUCKETS
    )
    return (
        "train"
        if bucket < TRAIN_BUCKETS
        else "validation"
        if bucket == VALIDATION_BUCKET
        else "test"
    )


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _concept(paper: SourcePaper) -> str:
    """Prefer a short title subject actually repeated in the abstract."""
    prefix = paper.title.split(":", 1)[0].strip(" .")
    if (
        1 <= len(prefix.split()) <= MAX_TITLE_CONCEPT_WORDS
        and not GENERIC_TITLE.search(prefix)
        and prefix.casefold() in paper.abstract.casefold()
    ):
        return paper.abstract[
            paper.abstract.casefold().index(prefix.casefold()) : paper.abstract.casefold().index(
                prefix.casefold()
            )
            + len(prefix)
        ]
    match = re.search(re.escape(paper.topic), paper.abstract, re.I)
    return match.group(0) if match else ""


def _annotation(paper: SourcePaper) -> PaperAnnotation | None:
    """Create narrow labels only when the source contains literal support."""
    if (
        len(paper.abstract) < MIN_ABSTRACT_CHARS
        or paper.topic.casefold() not in paper.title.casefold()
        or paper.topic.casefold() not in paper.abstract.casefold()
        or NON_METHOD_TITLE.search(paper.title)
    ):
        return None
    concept = _concept(paper)
    if not concept:
        return None
    evidence = next(
        (
            sentence
            for sentence in _sentences(paper.abstract)
            if concept.casefold() in sentence.casefold()
        ),
        "",
    )
    if not evidence:
        return None
    fields: list[tuple[str, str, str]] = []
    if METHOD_CONTEXT.search(evidence):
        fields.append(("methodology", "techniques", concept))
    contribution = next(
        (sentence for sentence in _sentences(paper.abstract) if CONTRIBUTION.search(sentence)),
        "",
    )
    if contribution:
        fields.append(("methodology", "contributions", contribution))
    for dataset in DATASETS:
        sentence = next(
            (
                part
                for part in _sentences(paper.abstract)
                if re.search(rf"\b{re.escape(dataset)}\b", part, re.I)
                and DATASET_CONTEXT.search(part)
            ),
            "",
        )
        if sentence:
            match = re.search(rf"\b{re.escape(dataset)}\b", sentence, re.I)
            if match:
                fields.append(("experiments", "datasets", match.group(0)))
                break
    if not fields:
        return None
    return PaperAnnotation(
        arxiv_id=paper.identifier,
        concept=concept,
        concept_type="core" if concept.casefold() == paper.topic.casefold() else "technique",
        fields=tuple(fields),
        split=_split(_source_key(paper)),
    )


def build(output: Path) -> dict[str, Any]:
    """Fetch, validate, deduplicate, and write 500 to 1000 examples."""
    output.mkdir(parents=True, exist_ok=True)
    seed_sources = fetch_sources()
    seed: list[tuple[PaperAnnotation, SourcePaper]] = []
    seen: set[str] = set()
    seen_doi: set[str] = set()
    for annotation in PAPERS:
        item = seed_sources[annotation.arxiv_id]
        paper = SourcePaper(
            provider="arxiv",
            identifier=annotation.arxiv_id,
            url=item["url"],
            title=item["title"],
            abstract=item["abstract"],
            doi=None,
            topic=annotation.concept,
        )
        seed.append((annotation, paper))
        seen.add(_source_key(paper))
    queries = [(provider, topic) for provider, topics in SOURCE_TOPICS.items() for topic in topics]
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        fetched = list(pool.map(lambda pair: fetch(*pair), queries))
    accepted = list(seed)
    accepted_by_provider = Counter(paper.provider for _, paper in seed)
    source_responses = []
    for (provider, _), (papers, status) in zip(queries, fetched, strict=True):
        source_responses.append(status)
        for paper in papers:
            key = _source_key(paper)
            if (
                key in seen
                or (paper.doi is not None and paper.doi.casefold() in seen_doi)
                or accepted_by_provider[provider] >= SOURCE_QUOTA
                or len(accepted) >= MAX_PAPERS
            ):
                continue
            new_annotation = _annotation(paper)
            if new_annotation is None:
                continue
            seen.add(key)
            if paper.doi:
                seen_doi.add(paper.doi.casefold())
            accepted.append((new_annotation, paper))
            accepted_by_provider[provider] += 1
    if len(accepted) < MIN_PAPERS:
        raise ValueError(f"Only {len(accepted)} distinct source-backed papers; need {MIN_PAPERS}")
    missing_sources = [source for source in REQUIRED_SOURCES if not accepted_by_provider[source]]
    if missing_sources:
        raise ValueError(f"No accepted source-backed papers from: {missing_sources}")
    rows: dict[str, list[dict[str, Any]]] = {split: [] for split in ("train", "validation", "test")}
    audit = []
    for annotation, paper in accepted:
        fields = _validated_fields(annotation, paper.abstract)
        source = {"title": paper.title, "abstract": paper.abstract, "url": paper.url}
        for variant in ("complete", "evidence_sentences"):
            passage = _source_text(source, fields, variant)
            if annotation.concept.casefold() not in passage.casefold():
                concept_sentence = next(
                    sentence
                    for sentence in _sentences(paper.abstract)
                    if annotation.concept.casefold() in sentence.casefold()
                )
                passage = f"{concept_sentence} {passage}".strip()
            common = {
                "provider": paper.provider,
                "source_sha256": hashlib.sha256(paper.abstract.encode()).hexdigest(),
            }
            rows[annotation.split].append(
                {**_academic_row(annotation, source, passage, variant), **common}
            )
            rows[annotation.split].extend(
                {**row, **common}
                for row in _research_rows(annotation, source, passage, fields, variant)
            )
        audit.append(
            {
                "paper_id": annotation.arxiv_id,
                "provider": paper.provider,
                "source_url": paper.url,
                "doi": paper.doi,
                "title": paper.title,
                "abstract_sha256": hashlib.sha256(paper.abstract.encode()).hexdigest(),
                "concept": annotation.concept,
                "fields": fields,
                "split": annotation.split,
            }
        )
    ids = {split: {row["paper_id"] for row in examples} for split, examples in rows.items()}
    if any(ids[left] & ids[right] for left in ids for right in ids if left < right):
        raise ValueError("Paper identifiers overlap splits")
    for split, examples in rows.items():
        (output / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in examples),
            encoding="utf-8",
        )
    report = {
        "built_at": datetime.now(UTC).isoformat(),
        "papers": len(accepted),
        "provider_papers": dict(accepted_by_provider),
        "rows": {
            split: dict(Counter(row["task"] for row in examples))
            for split, examples in rows.items()
        },
        "paper_ids": {split: sorted(values) for split, values in ids.items()},
        "source_responses": source_responses,
        "label_policy": "Reviewed arXiv seed plus literal title/abstract concept, contribution sentence, and named dataset matches; unreviewed additions are weak labels.",
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "label_audit.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in audit), encoding="utf-8"
    )
    return report


def main() -> None:
    """Build the local training set and print its source mix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))


if __name__ == "__main__":
    main()
