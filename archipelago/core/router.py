"""
src/core/router.py — Firewall, Guardrail, and Full-Spectrum Intent Router for Archipelago.

Features:
- Input validation (len <= 500, non-empty)
- Conversational de-greaser (stripping polite preambles and noise)
- Malicious exploit & prompt injection firewall
- Dual-entity detection to resolve the TC-04 bug (e.g., "How does Latent Variables connect to BERT?")
- 3-Tier semantic confidence gating (>=0.75 execute, 0.50-0.75 suggest, <0.50 reject)
- 6-Pattern intent classification:
  1. MCQ_DIAGNOSTIC
  2. CATALOG_SHELF_ROUTING
  3. AUTH_GATEWAY
  4. INGESTION_ANALYSIS
  5. GRAPH_SYNTHESIS
  6. TOPIC_SUGGESTION
"""

from __future__ import annotations

import enum
import logging
import re
from typing import Any

from archipelago.core.intent import IntentCategory, classify_query_intent
from archipelago.core.multi_hop import extract_concept_mentions
from archipelago.core.router_patterns import (
    _AUTH_GATEWAY_PATTERNS,
    _CATALOG_SHELF_PATTERNS,
    _DEGREASE_PATTERNS,
    _DUAL_ENTITY_PATTERNS,
    _GUARDRAIL_PATTERNS,
    _INGESTION_ANALYSIS_PATTERNS,
    _INJECTION_PATTERNS,
    _MCQ_PATTERNS,
)

logger = logging.getLogger(__name__)

# ── Security Boundary Constants ───────────────────────────────────────────────
SECURITY_BOUNDARY_MESSAGE = (
    "[Security Boundary] Archipelago is a theoretical CS/AI academic library engine. "
    "Code execution, system prompt exfiltration, and administrative modifications are strictly denied."
)

OUT_OF_SCOPE_MESSAGE = (
    "This topic is outside the library's active catalog. "
    "Archipelago is scoped to Computer Science, AI/ML, and institutional library collections."
)

MAX_QUERY_LENGTH = 500


class RoutingTier(enum.StrEnum):
    TIER_1_EXECUTE = "tier_1_execute"  # cos >= 0.75 or verified dual-anchor
    TIER_2_SUGGEST = "tier_2_suggest"  # 0.50 <= cos < 0.75 or ambiguous term
    TIER_3_REJECT = "tier_3_reject"  # cos < 0.50 or malicious/out-of-scope


class QueryIntent(enum.StrEnum):
    MCQ_DIAGNOSTIC = "MCQ_DIAGNOSTIC"
    CATALOG_SHELF_ROUTING = "CATALOG_SHELF_ROUTING"
    AUTH_GATEWAY = "AUTH_GATEWAY"
    INGESTION_ANALYSIS = "INGESTION_ANALYSIS"
    GRAPH_SYNTHESIS = "GRAPH_SYNTHESIS"
    TOPIC_SUGGESTION = "TOPIC_SUGGESTION"
    GUARDRAIL_INTERCEPT = "GUARDRAIL_INTERCEPT"


class QueryRouter:
    """Production Query Router, Guardrail, and Intent Classifier for Archipelago."""

    def __init__(
        self,
        tier1_threshold: float = 0.75,
        tier2_threshold: float = 0.50,
        max_query_len: int = MAX_QUERY_LENGTH,
    ) -> None:
        self.tier1_threshold = tier1_threshold
        self.tier2_threshold = tier2_threshold
        self.max_query_len = max_query_len

    def validate_and_normalize(self, raw_query: str) -> tuple[bool, str, str | None]:
        """Validate length bounds, intercept malicious injections, and strip conversational noise.

        Returns:
            Tuple[is_valid, normalized_query, error_message]
        """
        if not raw_query or not raw_query.strip():
            return False, "", "Query cannot be empty."

        cleaned = raw_query.strip()

        # Enforce length bound
        if len(cleaned) > self.max_query_len:
            return (
                False,
                "",
                f"Payload overflow: {len(cleaned)} chars exceeds limit of {self.max_query_len}.",
            )

        # Check for malicious / injection patterns
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(cleaned):
                logger.warning("Intercepted malicious pattern in query: %s", cleaned[:80])
                return False, "", SECURITY_BOUNDARY_MESSAGE

        # De-grease conversational preamble iteratively
        norm = cleaned
        while True:
            changed = False
            for pat in _DEGREASE_PATTERNS:
                stripped = pat.sub("", norm).strip()
                if stripped != norm:
                    norm = stripped
                    changed = True
            if not changed:
                break

        # Clean trailing punctuation
        norm = re.sub(r"[\?\.!\s]+$", "", norm).strip()

        # If de-greasing stripped everything, fallback to cleaned original
        final_query = norm if norm else cleaned
        return True, final_query, None

    def extract_concepts(self, query: str) -> list[str]:
        """Extract 1, 2, 3, 4+ concepts from the query."""
        concepts = extract_concept_mentions(query)
        if not concepts:
            # Fallback to dual entities if extractor found nothing
            return self.detect_dual_entities(query)
        return concepts

    def detect_dual_entities(self, query: str) -> list[str]:
        """Detect bridge queries containing two distinct entities (Fixes TC-04 bug).

        Example:
            'How does Latent Variables connect to BERT?' -> ['Latent Variables', 'BERT']
        """
        q = query.strip()
        generic_noise = {
            "something",
            "anything",
            "nothing",
            "vaguely",
            "somewhat",
            "stuff",
            "concept",
            "topic",
            "someone",
            "tell",
            "explain",
        }

        for pat in _DUAL_ENTITY_PATTERNS:
            m = pat.search(q)
            if m:
                ent1 = m.group(1).strip()
                ent2 = m.group(2).strip()
                # Clean extra punctuation / conjunctions
                ent1 = re.sub(r"^(?:the|an|a)\s+", "", ent1, flags=re.I).strip(" ?.,!")
                ent2 = re.sub(r"^(?:the|an|a)\s+", "", ent2, flags=re.I).strip(" ?.,!")

                # Check that neither entity is just generic noise like "something vaguely"
                w1 = [w for w in re.findall(r"\w+", ent1.lower()) if w not in generic_noise]
                w2 = [w for w in re.findall(r"\w+", ent2.lower()) if w not in generic_noise]

                if w1 and w2 and ent1.lower() != ent2.lower():
                    return [ent1, ent2]
        return []

    def classify_intent(self, query: str, dual_entities: list[str] | None = None) -> QueryIntent:
        """Classify normalized query into one of the contract types.

        Order is load-bearing. Scope refusals are tested first so that a request
        framed as coursework ("write a Python script for my B+ tree assignment")
        is a guardrail intercept rather than a curriculum question, and the three
        static-institution intents are tested before the concept default so an
        hours query is never scored against the curriculum corpus.
        """
        ql = query.lower()

        # 6. GUARDRAIL_INTERCEPT — checked first, see docstring.
        for pat in _GUARDRAIL_PATTERNS:
            if pat.search(ql):
                return QueryIntent.GUARDRAIL_INTERCEPT

        # 1. MCQ_DIAGNOSTIC (includes plain curriculum learning requests).
        for pat in _MCQ_PATTERNS:
            if pat.search(ql):
                return QueryIntent.MCQ_DIAGNOSTIC

        # 2. CATALOG_SHELF_ROUTING
        for pat in _CATALOG_SHELF_PATTERNS:
            if pat.search(ql):
                return QueryIntent.CATALOG_SHELF_ROUTING

        # 3. AUTH_GATEWAY (operating hours and e-resource access both land here)
        for pat in _AUTH_GATEWAY_PATTERNS:
            if pat.search(ql):
                return QueryIntent.AUTH_GATEWAY

        # 5. INGESTION_ANALYSIS
        for pat in _INGESTION_ANALYSIS_PATTERNS:
            if pat.search(ql):
                return QueryIntent.INGESTION_ANALYSIS

        # 4. Dual entity queries default to GRAPH_SYNTHESIS
        if dual_entities and len(dual_entities) >= 2:
            return QueryIntent.GRAPH_SYNTHESIS

        # Default pedagogical path
        return QueryIntent.GRAPH_SYNTHESIS

    def evaluate_tier(
        self,
        max_similarity: float,
        is_dual_entity_valid: bool = False,
        has_exact_alias: bool = False,
    ) -> RoutingTier:
        """Enforce 3-tier thresholding logic.

        - TIER_1_EXECUTE: Cosine >= 0.75, or valid dual-entity pair, or exact alias match
        - TIER_2_SUGGEST: 0.50 <= Cosine < 0.75 (Fuzzy Concept Discovery & Suggestions)
        - TIER_3_REJECT: Cosine < 0.50 (Strict Out-of-Domain or Malicious)
        """
        if is_dual_entity_valid or has_exact_alias or max_similarity >= self.tier1_threshold:
            return RoutingTier.TIER_1_EXECUTE
        if max_similarity >= self.tier2_threshold:
            return RoutingTier.TIER_2_SUGGEST
        return RoutingTier.TIER_3_REJECT

    def route_query(
        self,
        raw_query: str,
        retriever_fn: Any | None = None,
    ) -> dict[str, Any]:
        """Comprehensive routing entrypoint.

        Validates, normalizes, detects dual entities, classifies intent,
        evaluates semantic tiers, and returns routing directive dictionary.
        """
        is_valid, norm_q, err_msg = self.validate_and_normalize(raw_query)
        is_malicious = err_msg == SECURITY_BOUNDARY_MESSAGE
        if not is_valid:
            return {
                "route": "rejected",
                "tier": RoutingTier.TIER_3_REJECT.value,
                "intent": None,
                "intent_category": IntentCategory.UNSUPPORTED.value,
                "normalized_query": "",
                "dual_entities": [],
                "concepts": [],
                "error": err_msg,
                "is_malicious": is_malicious,
                "message": err_msg,
            }

        concepts = self.extract_concepts(norm_q)
        dual_ents = self.detect_dual_entities(norm_q) or concepts[:2]
        intent = self.classify_intent(norm_q, dual_entities=dual_ents)
        intent_category = classify_query_intent(norm_q, extracted_concepts=concepts)

        # Scope refusals are contract type 6, reported through the pipeline's
        # existing out_of_scope stage so every consumer keeps working unchanged.
        # The *reason* — code generation versus off-topic — is carried on
        # ``intent``, so the caller can say the right thing without guessing.
        if intent == QueryIntent.GUARDRAIL_INTERCEPT:
            return {
                "route": "out_of_scope",
                "tier": RoutingTier.TIER_3_REJECT.value,
                "intent": intent.value,
                "intent_category": IntentCategory.UNSUPPORTED.value,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
                "concepts": concepts,
                "similarity": 0.0,
                "error": "Out of scope",
                "message": OUT_OF_SCOPE_MESSAGE,
            }

        # Static-institution and scope intents never depend on the concept corpus,
        # so they bypass cosine thresholding entirely: "what are the Sunday
        # hours" has no semantic similarity to any concept node, and scoring it
        # against the corpus was the original cause of hours being deflected as
        # out-of-scope.
        if (
            intent in (
                QueryIntent.CATALOG_SHELF_ROUTING,
                QueryIntent.AUTH_GATEWAY,
                QueryIntent.MCQ_DIAGNOSTIC,
                QueryIntent.INGESTION_ANALYSIS,
            )
            or intent_category in (
                IntentCategory.PAPER_LOOKUP,
                IntentCategory.LIBRARY_LOOKUP,
                IntentCategory.ACADEMIC_INFO,
                IntentCategory.MULTI_CONCEPT,
            )
        ):
            return {
                "route": "execute",
                "tier": RoutingTier.TIER_1_EXECUTE.value,
                "intent": intent.value if intent else "METADATA_LOOKUP",
                "intent_category": intent_category.value,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
                "concepts": concepts,
                "similarity": 1.0,
                "error": None,
                "message": None,
            }

        sim_score = 0.0
        exact_alias = False
        is_dual_valid = False

        if retriever_fn is not None:
            try:
                # If dual entities detected, check both anchors to solve TC-04 bug
                if dual_ents and len(dual_ents) >= 2:
                    score1, hit1 = retriever_fn(dual_ents[0])
                    score2, hit2 = retriever_fn(dual_ents[1])
                    # If both entities exist or have decent individual similarity, promote to Tier 1
                    if (score1 >= self.tier2_threshold or hit1) and (
                        score2 >= self.tier2_threshold or hit2
                    ):
                        is_dual_valid = True
                        sim_score = max(score1, score2)
                    else:
                        sim_score = max(score1, score2)
                else:
                    sim_score, hit_info = retriever_fn(norm_q)
                    if hit_info and isinstance(hit_info, dict) and hit_info.get("exact_alias"):
                        exact_alias = True
            except Exception as exc:
                logger.error("Error during similarity calculation in router: %s", exc)
                sim_score = 0.0

        tier = self.evaluate_tier(
            sim_score, is_dual_entity_valid=is_dual_valid, has_exact_alias=exact_alias
        )

        if tier == RoutingTier.TIER_3_REJECT:
            return {
                "route": "out_of_scope",
                "tier": tier.value,
                "intent": None,
                "intent_category": IntentCategory.UNSUPPORTED.value,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
                "concepts": concepts,
                "similarity": sim_score,
                "error": "Out of scope",
                "message": OUT_OF_SCOPE_MESSAGE,
            }

        if tier == RoutingTier.TIER_2_SUGGEST:
            return {
                "route": "suggest_topics",
                "tier": tier.value,
                "intent": QueryIntent.TOPIC_SUGGESTION.value,
                "intent_category": intent_category.value,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
                "concepts": concepts,
                "similarity": sim_score,
                "error": None,
                "message": None,
            }

        return {
            "route": "execute",
            "tier": tier.value,
            "intent": intent.value,
            "intent_category": intent_category.value,
            "normalized_query": norm_q,
            "dual_entities": dual_ents,
            "concepts": concepts,
            "similarity": sim_score,
            "error": None,
            "message": None,
        }
