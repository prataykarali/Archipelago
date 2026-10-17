"""Scientific Information & Evidence Extractor.

Extracts structured claims, datasets, experimental metrics, baselines, ablation flags,
and reproducibility indicators linked to exact document provenance pointers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from archipelago.scholarly.contracts.okf_models import (
    ClaimRecord,
    ClaimTypeEnum,
    DatasetRecord,
    ExperimentalResult,
    ExperimentMetric,
    ExperimentRecord,
    PaperRecord,
    PolarityEnum,
    ProvenancePointer,
    StatusEnum,
)

logger = logging.getLogger("archipelago.scholarly.extractor")
EXTRACTOR_VERSION = "scientific-heuristics-v1"

COMMON_DATASETS = [
    "IAM",
    "ICDAR",
    "MNIST",
    "ImageNet",
    "COCO",
    "WMT",
    "GLUE",
    "SuperGLUE",
    "SQuAD",
    "WikiText",
    "Common Crawl",
    "TREC",
    "C4",
    "CIFAR-10",
    "CIFAR-100",
    "Synthetic",
    "SVHN",
    "IIIT-5K",
    "Street View Text",
]

METRIC_PATTERNS = [
    (
        r"(?i)\b(?:CER|character\s+error\s+rate)\b\s*(?:of|=|:)?\s*([0-9]+\.?[0-9]*)\s*(%?)",
        "CER",
        False,
        "%",
    ),
    (
        r"(?i)\b(?:WER|word\s+error\s+rate)\b\s*(?:of|=|:)?\s*([0-9]+\.?[0-9]*)\s*(%?)",
        "WER",
        False,
        "%",
    ),
    (r"(?i)\b(?:accuracy|acc)\b\s*(?:of|=|:)?\s*([0-9]+\.?[0-9]*)\s*(%?)", "Accuracy", True, "%"),
    (r"(?i)\b(?:BLEU|bleu\s+score)\b\s*(?:of|=|:)?\s*([0-9]+\.?[0-9]*)", "BLEU", True, ""),
    (r"(?i)\b(?:F1|f1-score|f-measure)\b\s*(?:of|=|:)?\s*([0-9]+\.?[0-9]*)", "F1", True, ""),
    (r"(?i)\b(?:perplexity|PPL)\b\s*(?:of|=|:)?\s*([0-9]+\.?[0-9]*)", "PPL", False, ""),
]

CODE_REPO_REGEX = r"https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"


class ScientificExtractor:
    """Extracts typed scientific entities and evidence from parsed document spans."""

    def extract_from_parsed_document(
        self, paper: PaperRecord, parsed_doc: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract claims, datasets, experiments, results, and reproducibility indicators."""
        artifact_sha256 = parsed_doc.get("artifact_sha256", "sha256_mock")

        all_claims: list[ClaimRecord] = []
        all_datasets: list[DatasetRecord] = []
        all_experiments: list[ExperimentRecord] = []
        all_results: list[ExperimentalResult] = []
        all_provenance: list[ProvenancePointer] = []

        # 1. Reproducibility & Code Repository extraction
        code_url, code_prov = self._extract_code_repo(parsed_doc, artifact_sha256)
        if code_prov:
            all_provenance.append(code_prov)

        # 2. Extract Datasets
        datasets, ds_provs = self._extract_datasets(parsed_doc, artifact_sha256)
        all_datasets.extend(datasets)
        all_provenance.extend(ds_provs)

        # 3. Detect Ablation Study & Error Analysis presence
        has_ablation, ablation_prov = self._detect_ablation(parsed_doc, artifact_sha256)
        if ablation_prov:
            all_provenance.append(ablation_prov)

        has_error_analysis, err_prov = self._detect_error_analysis(parsed_doc, artifact_sha256)
        if err_prov:
            all_provenance.append(err_prov)

        # 4. Extract Experimental Results & Metrics
        results, exp_records, res_provs = self._extract_results_and_experiments(
            paper.paper_id,
            parsed_doc,
            artifact_sha256,
            all_datasets,
            has_ablation,
            has_error_analysis,
        )
        all_results.extend(results)
        all_experiments.extend(exp_records)
        all_provenance.extend(res_provs)

        # 5. Extract Core Scientific Claims
        claims, claim_provs = self._extract_claims(parsed_doc, artifact_sha256)
        all_claims.extend(claims)
        all_provenance.extend(claim_provs)

        return {
            "extractor_version": EXTRACTOR_VERSION,
            "claims": all_claims,
            "datasets": all_datasets,
            "experiments": all_experiments,
            "results": all_results,
            "provenance": all_provenance,
            "code_url": code_url,
            "ablation_present": has_ablation,
            "error_analysis_present": has_error_analysis,
        }

    def _extract_code_repo(
        self, parsed_doc: dict[str, Any], artifact_sha256: str
    ) -> tuple[str | None, ProvenancePointer | None]:
        for sec_name, spans in parsed_doc.get("sections", {}).items():
            for sp in spans:
                text = sp["text"]
                match = re.search(CODE_REPO_REGEX, text)
                if match:
                    url = match.group(0).rstrip(".,;")
                    prov = ProvenancePointer(
                        source_type="pdf",
                        artifact_sha256=artifact_sha256,
                        page=sp["page"],
                        section_id=sec_name,
                        bbox=sp.get("bbox"),
                        source_url=url,
                    )
                    return url, prov
        return None, None

    def _extract_datasets(
        self, parsed_doc: dict[str, Any], artifact_sha256: str
    ) -> tuple[list[DatasetRecord], list[ProvenancePointer]]:
        found_datasets = {}
        provs = []
        for sec_name in ["experiments", "methods", "results", "abstract", "introduction"]:
            for sp in parsed_doc.get("sections", {}).get(sec_name, []):
                text = sp["text"]
                for ds_name in COMMON_DATASETS:
                    if (
                        re.search(rf"\b{re.escape(ds_name)}\b", text)
                        and ds_name not in found_datasets
                    ):
                        prov = ProvenancePointer(
                            source_type="pdf",
                            artifact_sha256=artifact_sha256,
                            page=sp["page"],
                            section_id=sec_name,
                            bbox=sp.get("bbox"),
                        )
                        ds_rec = DatasetRecord(
                            name=ds_name,
                            provenance_ids=[prov.provenance_id],
                        )
                        found_datasets[ds_name] = ds_rec
                        provs.append(prov)
        return list(found_datasets.values()), provs

    def _detect_ablation(
        self, parsed_doc: dict[str, Any], artifact_sha256: str
    ) -> tuple[bool | None, ProvenancePointer | None]:
        if "ablation" in parsed_doc.get("sections", {}):
            sp = parsed_doc["sections"]["ablation"][0]
            prov = ProvenancePointer(
                source_type="pdf",
                artifact_sha256=artifact_sha256,
                page=sp["page"],
                section_id="ablation",
                bbox=sp.get("bbox"),
            )
            return True, prov
        for spans in parsed_doc.get("sections", {}).values():
            for sp in spans:
                if re.search(r"(?i)\bablation\s+(?:study|experiments?)\b", sp["text"]):
                    prov = ProvenancePointer(
                        source_type="pdf",
                        artifact_sha256=artifact_sha256,
                        page=sp["page"],
                        section_id=sp["section"],
                        bbox=sp.get("bbox"),
                    )
                    return True, prov
        return False, None

    def _detect_error_analysis(
        self, parsed_doc: dict[str, Any], artifact_sha256: str
    ) -> tuple[bool | None, ProvenancePointer | None]:
        for spans in parsed_doc.get("sections", {}).values():
            for sp in spans:
                if re.search(r"(?i)\berror\s+analysis\b", sp["text"]):
                    prov = ProvenancePointer(
                        source_type="pdf",
                        artifact_sha256=artifact_sha256,
                        page=sp["page"],
                        section_id=sp["section"],
                        bbox=sp.get("bbox"),
                    )
                    return True, prov
        return False, None

    def _extract_results_and_experiments(
        self,
        paper_id: str,
        parsed_doc: dict[str, Any],
        artifact_sha256: str,
        datasets: list[DatasetRecord],
        has_ablation: bool | None,
        has_error_analysis: bool | None,
    ) -> tuple[list[ExperimentalResult], list[ExperimentRecord], list[ProvenancePointer]]:
        results: list[ExperimentalResult] = []
        provs: list[ProvenancePointer] = []
        metrics: list[ExperimentMetric] = []

        ds_name = datasets[0].name if datasets else "Standard Benchmark"
        ds_id = datasets[0].dataset_id if datasets else "ds_default"

        for sec_name in ["experiments", "results", "abstract"]:
            for sp in parsed_doc.get("sections", {}).get(sec_name, []):
                text = sp["text"]
                for pat, m_name, higher_better, unit in METRIC_PATTERNS:
                    match = re.search(pat, text)
                    if match:
                        try:
                            val = float(match.group(1))
                            prov = ProvenancePointer(
                                source_type="pdf",
                                artifact_sha256=artifact_sha256,
                                page=sp["page"],
                                section_id=sec_name,
                                bbox=sp.get("bbox"),
                            )
                            provs.append(prov)

                            res = ExperimentalResult(
                                paper_id=paper_id,
                                experiment_id=f"exp_{paper_id[:8]}",
                                method_or_configuration="Proposed Architecture",
                                baseline_or_proposed="proposed",
                                dataset_id=ds_id,
                                dataset_name=ds_name,
                                metric_name=m_name,
                                metric_value=val,
                                metric_unit=unit,
                                higher_is_better=higher_better,
                                source_page=sp["page"],
                                provenance_ids=[prov.provenance_id],
                            )
                            results.append(res)
                            metrics.append(
                                ExperimentMetric(
                                    name=m_name,
                                    value=val,
                                    unit=unit,
                                    higher_is_better=higher_better,
                                    provenance_ids=[prov.provenance_id],
                                )
                            )
                        except ValueError:
                            continue

        exp = ExperimentRecord(
            experiment_id=f"exp_{paper_id[:8]}",
            name="Main Experimental Evaluation",
            dataset_refs=[d.dataset_id for d in datasets],
            metrics=metrics,
            ablation_present=has_ablation,
            error_analysis_present=has_error_analysis,
            provenance_ids=[p.provenance_id for p in provs],
        )

        return results, [exp], provs

    def _extract_claims(
        self, parsed_doc: dict[str, Any], artifact_sha256: str
    ) -> tuple[list[ClaimRecord], list[ProvenancePointer]]:
        claims: list[ClaimRecord] = []
        provs: list[ProvenancePointer] = []

        # Extract primary claims from Abstract and Conclusion
        for sec_name in ["abstract", "conclusion", "introduction"]:
            spans = parsed_doc.get("sections", {}).get(sec_name, [])
            if not spans:
                continue
            text = " ".join([s["text"] for s in spans[:2]])
            sentences = [s.strip() for s in re.split(r"\.\s+", text) if len(s.strip()) > 30]

            for sent in sentences[:2]:
                sp = spans[0]
                prov = ProvenancePointer(
                    source_type="pdf",
                    artifact_sha256=artifact_sha256,
                    page=sp["page"],
                    section_id=sec_name,
                    bbox=sp.get("bbox"),
                )
                provs.append(prov)

                claim_type = (
                    ClaimTypeEnum.PERFORMANCE
                    if any(
                        w in sent.lower()
                        for w in [
                            "outperform",
                            "achieve",
                            "state-of-the-art",
                            "sota",
                            "improves",
                            "accuracy",
                        ]
                    )
                    else ClaimTypeEnum.METHODOLOGICAL
                )
                claims.append(
                    ClaimRecord(
                        text=sent,
                        claim_type=claim_type,
                        polarity=PolarityEnum.POSITIVE,
                        status=StatusEnum.OBSERVED,
                        confidence=0.92,
                        provenance_ids=[prov.provenance_id],
                    )
                )

        return claims, provs
