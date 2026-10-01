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
from typing import Any, Dict, List, Optional, Tuple

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


class RoutingTier(str, enum.Enum):
    TIER_1_EXECUTE = "tier_1_execute"    # cos >= 0.75 or verified dual-anchor
    TIER_2_SUGGEST = "tier_2_suggest"    # 0.50 <= cos < 0.75 or ambiguous term
    TIER_3_REJECT = "tier_3_reject"      # cos < 0.50 or malicious/out-of-scope


class QueryIntent(str, enum.Enum):
    MCQ_DIAGNOSTIC = "MCQ_DIAGNOSTIC"
    CATALOG_SHELF_ROUTING = "CATALOG_SHELF_ROUTING"
    AUTH_GATEWAY = "AUTH_GATEWAY"
    INGESTION_ANALYSIS = "INGESTION_ANALYSIS"
    GRAPH_SYNTHESIS = "GRAPH_SYNTHESIS"
    TOPIC_SUGGESTION = "TOPIC_SUGGESTION"


# ── Malicious / Prompt Injection Patterns ─────────────────────────────────────
_INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bprint\s+(?:your\s+)?(?:rules|instructions|api\s*keys?|secrets?)\b", re.I),
    re.compile(r"\b(?:exfiltrate|leak|dump)\b", re.I),
    re.compile(r"\bcat\s+/etc/passwd\b", re.I),
    re.compile(r"\b(sudo|rm\s+-rf|chmod\s+\d+|bash\s+-c)\b", re.I),
    re.compile(r"\bwrite\s+(?:a\s+)?(?:python|c\+\+|javascript|code)\s+(?:script|program|function)\s+to\b", re.I),
    re.compile(r"\b(jailbreak|dan\s+mode|unrestricted\s+mode)\b", re.I),
]

# ── Conversational De-greasing Patterns ───────────────────────────────────────
_DEGREASE_PATTERNS = [
    re.compile(r"^(?:hey\s+(?:assistant|archipelago|there|bot)[\s,]+|hello[\s,]+|hi[\s,]+|greetings[\s,]+)", re.I),
    re.compile(r"^(?:(?:could|can|would)\s+you\s+)?(?:please\s+)?(?:give\s+(?:me\s+)?(?:an\s+)?overview\s+of|explain(?:\s+to\s+me)?|tell\s+me\s+about|show\s+me|help\s+me\s+with|define|describe)\s*", re.I),
    re.compile(r"^(?:what\s+(?:is|are|was|were)|how\s+does)\s*", re.I),
    re.compile(r"^(?:something\s+(?:vaguely\s+)?(?:related\s+to|about)\s+)", re.I),
]


# ── Dual-Entity Bridge Patterns (Fixing TC-04 Bug) ─────────────────────────────
_DUAL_ENTITY_PATTERNS = [
    re.compile(r"(?:how\s+does\s+)?(.+?)\s+(?:connect(?:s|ed)?\s+to|relate(?:s|d)?\s+to|bridge\s+to)\s+(.+)", re.I),
    re.compile(r"(?:path\s+between\s+|bridge\s+between\s+|relationship\s+between\s+)(.+?)\s+and\s+(.+)", re.I),
    re.compile(r"(.+?)\s+(?:vs\.?|versus)\s+(.+)", re.I),
    re.compile(r"(?:difference\s+between\s+|compare\s+)(.+?)\s+and\s+(.+)", re.I),
    re.compile(r"(?:how\s+do\s+)(.+?)\s+and\s+(.+?)\s+(?:differ|compare|interact)", re.I),
]


# ── Intent Patterns ───────────────────────────────────────────────────────────
_MCQ_PATTERNS = [
    re.compile(r"\b(quiz|diagnostic|assessment|test\s+my\s+knowledge|practice\s+questions?|mcqs?)\b", re.I),
    re.compile(r"\b(roadmap\s+quiz|prerequisite\s+test|knowledge\s+check)\b", re.I),
]

_CATALOG_SHELF_PATTERNS = [
    re.compile(r"\b(shelf|stacks?|call\s+number|floor|aisle|barcode|holdings?|physical\s+copy|borrow|checkout|copies\s+available)\b", re.I),
    re.compile(r"\b(where\s+is\s+the\s+book|find\s+on\s+shelf|library\s+shelf|catalog\s+search)\b", re.I),
]

_AUTH_GATEWAY_PATTERNS = [
    re.compile(r"\b(ndli|ieee(?:\s+explore)?|scopus|sciencedirect|springer|acm\s+digital\s+library)\b", re.I),
    re.compile(r"\b(e-?resources?|portal\s+link|passkey|credentials?|institutional\s+login|proxy\s+access)\b", re.I),
]

_INGESTION_ANALYSIS_PATTERNS = [
    re.compile(r"\b(uploaded|newly\s+ingested|uploaded\s+paper|theorem\s+\d+|formula|equation\s+\d+|deep\s*link|#page=\d+)\b", re.I),
    re.compile(r"\b(pdf\s+page|view\s+passage|cite\s+paper|paper\s+analysis)\b", re.I),
]


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

    def validate_and_normalize(self, raw_query: str) -> Tuple[bool, str, Optional[str]]:
        """Validate length bounds, intercept malicious injections, and strip conversational noise.

        Returns:
            Tuple[is_valid, normalized_query, error_message]
        """
        if not raw_query or not raw_query.strip():
            return False, "", "Query cannot be empty."

        cleaned = raw_query.strip()

        # Enforce length bound
        if len(cleaned) > self.max_query_len:
            return False, "", f"Payload overflow: {len(cleaned)} chars exceeds limit of {self.max_query_len}."

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

    def detect_dual_entities(self, query: str) -> List[str]:
        """Detect bridge queries containing two distinct entities (Fixes TC-04 bug).

        Example:
            'How does Latent Variables connect to BERT?' -> ['Latent Variables', 'BERT']
        """
        q = query.strip()
        generic_noise = {"something", "anything", "nothing", "vaguely", "somewhat", "stuff", "concept", "topic", "someone", "tell", "explain"}

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


    def classify_intent(self, query: str, dual_entities: Optional[List[str]] = None) -> QueryIntent:
        """Classify normalized query into one of the 6 core intent patterns."""
        ql = query.lower()

        # 1. MCQ_DIAGNOSTIC
        for pat in _MCQ_PATTERNS:
            if pat.search(ql):
                return QueryIntent.MCQ_DIAGNOSTIC

        # 2. CATALOG_SHELF_ROUTING
        for pat in _CATALOG_SHELF_PATTERNS:
            if pat.search(ql):
                return QueryIntent.CATALOG_SHELF_ROUTING

        # 3. AUTH_GATEWAY
        for pat in _AUTH_GATEWAY_PATTERNS:
            if pat.search(ql):
                return QueryIntent.AUTH_GATEWAY

        # 4. INGESTION_ANALYSIS
        for pat in _INGESTION_ANALYSIS_PATTERNS:
            if pat.search(ql):
                return QueryIntent.INGESTION_ANALYSIS

        # 5. Dual entity queries default to GRAPH_SYNTHESIS
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
        retriever_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Comprehensive routing entrypoint.

        Validates, normalizes, detects dual entities, classifies intent,
        evaluates semantic tiers, and returns routing directive dictionary.
        """
        is_valid, norm_q, err_msg = self.validate_and_normalize(raw_query)
        if not is_valid:
            is_malicious = err_msg == SECURITY_BOUNDARY_MESSAGE
            return {
                "route": "rejected",
                "tier": RoutingTier.TIER_3_REJECT.value,
                "intent": None,
                "normalized_query": "",
                "dual_entities": [],
                "error": err_msg,
                "is_malicious": is_malicious,
                "message": err_msg,
            }

        dual_ents = self.detect_dual_entities(norm_q)
        intent = self.classify_intent(norm_q, dual_entities=dual_ents)

        # Non-graph intents (Catalog, Auth, Diagnostic) bypass concept cosine thresholding
        if intent in (QueryIntent.CATALOG_SHELF_ROUTING, QueryIntent.AUTH_GATEWAY, QueryIntent.MCQ_DIAGNOSTIC):
            return {
                "route": "execute",
                "tier": RoutingTier.TIER_1_EXECUTE.value,
                "intent": intent.value,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
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
                    if (score1 >= self.tier2_threshold or hit1) and (score2 >= self.tier2_threshold or hit2):
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

        tier = self.evaluate_tier(sim_score, is_dual_entity_valid=is_dual_valid, has_exact_alias=exact_alias)

        if tier == RoutingTier.TIER_3_REJECT:
            return {
                "route": "out_of_scope",
                "tier": tier.value,
                "intent": None,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
                "similarity": sim_score,
                "error": "Out of scope",
                "message": OUT_OF_SCOPE_MESSAGE,
            }

        if tier == RoutingTier.TIER_2_SUGGEST:
            return {
                "route": "suggest_topics",
                "tier": tier.value,
                "intent": QueryIntent.TOPIC_SUGGESTION.value,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
                "similarity": sim_score,
                "error": None,
                "message": None,
            }

        return {
            "route": "execute",
            "tier": tier.value,
            "intent": intent.value,
            "normalized_query": norm_q,
            "dual_entities": dual_ents,
            "similarity": sim_score,
            "error": None,
            "message": None,
        }
