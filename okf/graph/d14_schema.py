"""Schema, typed edge ontology, and version selection for Archipelago D14 OKF graph."""

from __future__ import annotations

import os
from pathlib import Path

#: Frozen SHA-256 of the immutable historical v1 baseline (610 concepts, 1,988 edges).
GRAPH_V1_SHA256 = "9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76"
GRAPH_V1_ID = "graph_v1_okf610"
GRAPH_V2_ID = "graph_v2_d14"
GRAPH_V2_SCHEMA_VERSION = "2.0.0-d14"

GRAPH_V1_FILENAME = "okf_graph.json"
GRAPH_V2_FILENAME = "okf_graph_v2_d14.json"

ENV_GRAPH_PATH = "ARCHIPELAGO_GRAPH_PATH"
ENV_GRAPH_VERSION = "ARCHIPELAGO_GRAPH_VERSION"

#: Six canonical typed relationship semantics in graph_v2_d14.
REL_REQUIRES = "REQUIRES"
REL_ENABLES = "ENABLES"
REL_USES = "USES"
REL_PART_OF = "PART_OF"
REL_RELATED_TO = "RELATED_TO"
REL_CONTRASTS_WITH = "CONTRASTS_WITH"

VALID_TYPED_RELATIONS: frozenset[str] = frozenset(
    {
        REL_REQUIRES,
        REL_ENABLES,
        REL_USES,
        REL_PART_OF,
        REL_RELATED_TO,
        REL_CONTRASTS_WITH,
    }
)

#: Relations that represent hard prerequisite/unlock pedagogical order (must be a DAG).
PREREQUISITE_RELATIONS: frozenset[str] = frozenset({REL_REQUIRES, REL_ENABLES})

#: Relations that are non-prerequisite semantic links (never presented as prerequisites).
ASSOCIATIVE_RELATIONS: frozenset[str] = frozenset(
    {REL_USES, REL_PART_OF, REL_RELATED_TO, REL_CONTRASTS_WITH}
)

#: Explicit provenance review statuses. Machine-generated edges are NEVER auto-promoted.
REVIEW_HUMAN_VERIFIED = "HUMAN_VERIFIED"
REVIEW_PENDING = "PENDING_REVIEW"
REVIEW_QUARANTINED = "QUARANTINED"

VALID_REVIEW_STATUSES: frozenset[str] = frozenset(
    {REVIEW_HUMAN_VERIFIED, REVIEW_PENDING, REVIEW_QUARANTINED}
)

#: Twelve canonical academic domains aligned with the Archipelago D10-D14 curriculum.
ACADEMIC_DOMAINS: tuple[str, ...] = (
    "Mathematics for Computing",
    "Probability & Statistics",
    "AI & Machine Learning",
    "Operating Systems",
    "Data Structures & Algorithms",
    "Database Systems",
    "Computer Networks",
    "Compilers & Languages",
    "Automata & Computation",
    "Information Security",
    "Software Engineering",
    "Computer Architecture",
)

FALLBACK_DOMAIN_CS = "General Computer Science"
FALLBACK_DOMAIN_SCI = "Natural Sciences"

#: Approved interdisciplinary bridges exempt from cross-domain noise quarantine.
INTERDISCIPLINARY_BRIDGES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"paging", "paged_attention"}),
        frozenset({"virtual_memory", "paged_attention"}),
        frozenset({"paging", "vllm"}),
        frozenset({"priority_queue_mechanics", "heuristic_search"}),
        frozenset({"priority_queue_mechanics", "dijkstras_algorithm"}),
        frozenset({"modular_arithmetic", "rsa_cryptosystem"}),
        frozenset({"linear_algebra", "singular_value_decomposition"}),
        frozenset({"linear_algebra", "principal_component_analysis"}),
        frozenset({"probability_distribution", "maximum_likelihood_estimation"}),
        frozenset({"probability_distribution", "kl_divergence"}),
        frozenset({"kl_divergence", "variational_inference"}),
        frozenset({"kl_divergence", "direct_preference_optimization"}),
        frozenset({"variational_inference", "denoising_diffusion_probabilistic_models"}),
        frozenset({"variational_inference", "variational_autoencoder"}),
        frozenset({"bayes_theorem", "variational_inference"}),
        frozenset({"tcp", "tls_protocol"}),
        frozenset({"finite_automata", "lexical_analysis"}),
        frozenset({"deterministic_finite_automaton", "lexical_analysis"}),
        frozenset({"context_free_grammar", "syntax_analysis"}),
        frozenset({"context_free_grammar", "lalr"}),
    }
)


def normalize_edge_relation(raw_edge_type: str | None, raw_relation: str | None) -> str:
    """Map legacy v1 ``edge_type`` + ``relation`` pairs to the 6 canonical v2 types."""
    rel = (raw_relation or "").strip().lower()
    etype = (raw_edge_type or "").strip().upper()

    if rel in {"requires", "prerequisite"}:
        return REL_REQUIRES
    if rel in {"enables", "unlocks"}:
        return REL_ENABLES
    if rel == "uses":
        return REL_USES
    if rel in {"part_of", "variant_of"}:
        return REL_PART_OF
    if rel == "contrasts_with":
        return REL_CONTRASTS_WITH
    if rel in {"co_mention", "evaluated_by", "related", "related_to"}:
        return REL_RELATED_TO

    if etype == "REQUIRES":
        return REL_REQUIRES
    if etype in {"UNLOCKS", "ENABLES"}:
        return REL_ENABLES
    if etype in VALID_TYPED_RELATIONS:
        return etype
    return REL_RELATED_TO


def resolve_graph_path(
    fixtures_dir: Path,
    explicit_path: Path | None = None,
    *,
    allow_env_override: bool = True,
) -> Path:
    """Resolve graph JSON path without breaking ``graph_v1_okf610`` reproducibility.

    Precedence:
    1. Explicit non-default path (e.g. a caller directly passing a custom file or v2 path).
    2. ``ARCHIPELAGO_GRAPH_PATH`` env var when ``allow_env_override`` is True.
    3. ``ARCHIPELAGO_GRAPH_VERSION`` env var (``graph_v2_d14`` / ``v2_d14`` vs ``graph_v1_okf610``).
    4. Default ``okf_graph.json`` (``graph_v1_okf610``) for full backward compatibility.
    """
    is_default_target = explicit_path is None or explicit_path.name == GRAPH_V1_FILENAME
    if allow_env_override and is_default_target:
        env_path = os.environ.get(ENV_GRAPH_PATH, "").strip()
        if env_path:
            return Path(env_path)
        env_version = os.environ.get(ENV_GRAPH_VERSION, "").strip().lower()
        if env_version in {GRAPH_V2_ID, "v2_d14", "v2"}:
            return fixtures_dir / GRAPH_V2_FILENAME
        if env_version in {GRAPH_V1_ID, "v1_okf610", "v1"}:
            return fixtures_dir / GRAPH_V1_FILENAME
    if explicit_path is not None:
        return explicit_path
    return fixtures_dir / GRAPH_V1_FILENAME
