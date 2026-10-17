"""
Scholarly Evidence Intelligence Platform — OKF v1.0.0 Data Contracts.
Authoritative Pydantic models for papers, claims, experiments, results, datasets,
provenance pointers, and typed feature observations.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Union
import uuid

from pydantic import BaseModel, Field


class StatusEnum(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    DERIVED = "derived"
    UNKNOWN = "unknown"
    NOT_REPORTED = "not_reported"
    NOT_APPLICABLE = "not_applicable"


class ClaimTypeEnum(StrEnum):
    PERFORMANCE = "performance"
    METHODOLOGICAL = "methodological"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    DATASET = "dataset"
    LIMITATION = "limitation"
    GENERALIZATION = "generalization"
    OTHER = "other"


class PolarityEnum(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class RelationTypeEnum(StrEnum):
    CITES = "CITES"
    ASSERTS = "ASSERTS"
    SUPPORTED_BY = "SUPPORTED_BY"
    REFUTED_BY = "REFUTED_BY"
    USES = "USES"
    USES_DATASET = "USES_DATASET"
    EVALUATED_ON = "EVALUATED_ON"
    COMPARES_AGAINST = "COMPARES_AGAINST"
    EXTENDS = "EXTENDS"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    REPLICATES = "REPLICATES"
    INTRODUCES = "INTRODUCES"


class ProvenancePointer(BaseModel):
    provenance_id: str = Field(default_factory=lambda: f"prov_{uuid.uuid4().hex[:8]}")
    source_type: str  # pdf, tei, table, ocr, openalex, crossref, arxiv, semantic_scholar, derived
    artifact_sha256: str
    page: int | None = None
    section_id: str | None = None
    tei_xpath: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: list[float] | None = None  # [x0, y0, x1, y1]
    table_id: str | None = None
    row: int | None = None
    column: int | None = None
    source_record_id: str | None = None
    json_pointer: str | None = None
    source_url: str | None = None
    fetched_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class PaperAuthor(BaseModel):
    name: str
    orcid: str | None = None
    institutions: list[str] = Field(default_factory=list)


class PaperIdentifiers(BaseModel):
    doi: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None


class PaperRecord(BaseModel):
    paper_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    identifiers: PaperIdentifiers = Field(default_factory=PaperIdentifiers)
    abstract: str | None = None
    authors: list[PaperAuthor] = Field(default_factory=list)
    venue: str | None = None
    publication_date: str | None = None
    publication_type: str | None = None
    language: str | None = "en"
    is_open_access: bool | None = None
    oa_url: str | None = None
    pdf_object_key: str | None = None
    license: str | None = None
    publication_status: str | None = None
    retraction_status: str = "unknown"
    correction_status: str = "unknown"
    canonical_version: int = 1


class ClaimRecord(BaseModel):
    claim_id: str = Field(default_factory=lambda: f"claim_{uuid.uuid4().hex[:8]}")
    text: str
    claim_type: ClaimTypeEnum = ClaimTypeEnum.OTHER
    polarity: PolarityEnum = PolarityEnum.POSITIVE
    status: StatusEnum = StatusEnum.OBSERVED
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    extractor_name: str = "scientific-extractor-v1.0"
    extractor_version: str = "1.0.0"
    provenance_ids: list[str] = Field(default_factory=list)


class ExperimentMetric(BaseModel):
    name: str
    value: Union[float, str] | None = None
    unit: str | None = None
    split: str | None = None
    higher_is_better: bool | None = None
    provenance_ids: list[str] = Field(default_factory=list)


class ExperimentRecord(BaseModel):
    experiment_id: str = Field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:8]}")
    name: str
    dataset_refs: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    metrics: list[ExperimentMetric] = Field(default_factory=list)
    ablation_present: bool | None = None
    error_analysis_present: bool | None = None
    sample_size: int | None = None
    external_validation: bool | None = None
    cross_dataset_evaluation: bool | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.95)
    extractor_version: str = "1.0.0"
    provenance_ids: list[str] = Field(default_factory=list)


class ExperimentalResult(BaseModel):
    """Section 5: Contextual experimental result record."""

    result_id: str = Field(default_factory=lambda: f"res_{uuid.uuid4().hex[:8]}")
    paper_id: str
    experiment_id: str
    method_or_configuration: str
    baseline_or_proposed: str = "proposed"  # proposed | baseline
    dataset_id: str
    dataset_name: str
    dataset_version: str | None = None
    split: str | None = "test"  # train | val | test
    language: list[str] = Field(default_factory=lambda: ["en"])
    metric_name: str
    metric_value: float | None = None
    metric_unit: str | None = None
    higher_is_better: bool = True
    preprocessing: str | None = None
    evaluation_protocol: str | None = None
    source_table: str | None = None
    source_page: int | None = None
    provenance_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.95


class DatasetRecord(BaseModel):
    dataset_id: str = Field(default_factory=lambda: f"ds_{uuid.uuid4().hex[:8]}")
    name: str
    version: str | None = None
    sample_count: int | None = None
    language_scope: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)


class RelationRecord(BaseModel):
    relation_id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:8]}")
    source_type: str
    source_id: str
    relation_type: RelationTypeEnum
    target_type: str
    target_id: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    extractor_version: str = "1.0.0"
    provenance_ids: list[str] = Field(default_factory=list)


class FeatureObservation(BaseModel):
    """Section 7: Typed quantitative and qualitative feature observation."""

    feature_name: str
    value: Any = None
    status: StatusEnum = StatusEnum.OBSERVED
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    extractor: str = "feature-engine-v1.1"
    extractor_version: str = "1.1.0"
    observed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    provenance_ids: list[str] = Field(default_factory=list)
    derivation_json: dict[str, Any] | None = None
    comparability_status: str | None = "comparable"
    comparability_reasons: list[str] | None = None


class OKFPaperRecord(BaseModel):
    """Master OKF v1.0.0 Paper Record Contract."""

    okf_version: str = "1.0.0"
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    pipeline_version: str = "2026.10.1"
    paper: PaperRecord
    claims: list[ClaimRecord] = Field(default_factory=list)
    experiments: list[ExperimentRecord] = Field(default_factory=list)
    results: list[ExperimentalResult] = Field(default_factory=list)
    datasets: list[DatasetRecord] = Field(default_factory=list)
    relations: list[RelationRecord] = Field(default_factory=list)
    features: list[FeatureObservation] = Field(default_factory=list)
    provenance: list[ProvenancePointer] = Field(default_factory=list)
    quality: dict[str, Any] = Field(
        default_factory=lambda: {
            "validation_status": "validated",
            "schema_valid": True,
            "evidence_coverage": 1.0,
        }
    )
