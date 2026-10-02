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
    GUARDRAIL_INTERCEPT = "GUARDRAIL_INTERCEPT"


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
    # Curriculum requests are contract type 4 in their own right. They matched
    # nothing before, so "I want to learn RAG" fell through to GRAPH_SYNTHESIS
    # and answered a definition instead of offering the learning path.
    re.compile(
        r"\b(i\s+want\s+to\s+learn|i'?d\s+like\s+to\s+learn|teach\s+me|"
        r"show\s+(?:me\s+)?(?:the\s+)?learning\s+(?:roadmap|path)|"
        r"learning\s+roadmap|what\s+should\s+i\s+study\s+first|"
        r"prepare\s+me\s+for|revision\s+plan|study\s+plan)\b",
        re.I,
    ),
]

_CATALOG_SHELF_PATTERNS = [
    re.compile(r"\b(shelf|stacks?|call\s+number|floor|aisle|barcode|holdings?|physical\s+copy|borrow|checkout|copies\s+available)\b", re.I),
    re.compile(r"\b(where\s+is\s+the\s+book|find\s+on\s+shelf|library\s+shelf|catalog\s+search)\b", re.I),
    # "How many copies of X are available" and "Where are the lab manuals" are
    # location questions. Neither matched, so both were answered as concept
    # queries and scored against the curriculum kill-switch.
    re.compile(r"\bhow\s+many\s+(?:physical\s+)?copies\b", re.I),
    re.compile(r"\b(?:lab\s+manuals?|xerox|reprography)\b", re.I),
    re.compile(r"\bwhere\s+(?:are|is|do\s+i\s+find|can\s+i\s+find)\b.*\b(?:manual|handbook|textbook|book)\b", re.I),
]

_AUTH_GATEWAY_PATTERNS = [
    re.compile(r"\b(ndli|ieee(?:\s+explore)?|scopus|sciencedirect|springer|acm\s+digital\s+library)\b", re.I),
    re.compile(r"\b(e-?resources?|portal\s+link|passkey|credentials?|institutional\s+login|proxy\s+access)\b", re.I),
    # Contract type 3 covers operating hours as well as database access. Hours
    # had no pattern at all, so "what are the library Sunday hours" was scored as
    # an out-of-corpus concept question and deflected.
    re.compile(r"\b(opac\s+link|off-?campus|remote\s+access|proxy\s+login)\b", re.I),
    re.compile(
        r"\b(?:(?:library|reading\s+room|circulation|lending|reference)\s+)?"
        r"(?:opening\s+hours|working\s+hours|timetable)\b",
        re.I,
    ),
    # Day-scoped hours: "library Sunday hours", "Monday timings", "is the library
    # open on weekends". Requiring the two words to be adjacent meant any day or
    # status qualifier broke the match.
    re.compile(
        r"\b(?:library|reading\s+room|circulation\s+desk)?\s*"
        r"(sun(?:day)?|mon(?:day)?|tues(?:day)?|wed(?:nesday)?|thur(?:sday)?|"
        r"fri(?:day)?|sat(?:urday)?|weekend|weekday|holiday)\s+"
        r"(?:hours?|timings?|schedule|open(?:ing)?)\b",
        re.I,
    ),
    re.compile(r"\b(?:is|are)\s+the\s+(?:library|reading\s+room|circulation\s+desk)\s+open\b", re.I),
    re.compile(r"\bwhat\s+time\s+(?:does|do|is)\b.*\b(?:library|desk|open|close)\b", re.I),
]

_INGESTION_ANALYSIS_PATTERNS = [
    re.compile(r"\b(uploaded|newly\s+ingested|uploaded\s+paper|theorem\s+\d+|formula|equation\s+\d+|deep\s*link|#page=\d+)\b", re.I),
    re.compile(r"\b(pdf\s+page|view\s+passage|cite\s+paper|paper\s+analysis)\b", re.I),
    # "Analyze this uploaded PDF" already matched the previous upload pattern, but
    # "extract the OKF nodes from my uploaded paper" did not, because the pattern
    # demanded the literal word "uploaded" and these phrasings say "this PDF" or
    # "my uploaded manuscript".
    re.compile(
        r"\b(?:analy[sz]e|extract|ingest|index|project)\b[^.?!]{0,40}\b"
        r"(?:this|my|the|attached|uploaded)?\s*"
        r"(?:pdf|paper|document|file|okf|manuscript)\b",
        re.I,
    ),
    re.compile(r"\b(?:okf\s+nodes?|ingestion\s+graph|new\s+nodes?\s+from)\b", re.I),
]

# Contract type 6, checked before the curriculum/concept patterns: a request to
# write code is a scope deflection even when it is dressed as coursework
# ("write a Python script to solve B+ tree insertions").
_GUARDRAIL_PATTERNS = [
    # "write a Python web scraper" names the language, then a *thing being
    # built*. Requiring the implementation noun immediately after the language
    # missed every phrasing that inserted a descriptor, which is most of them.
    re.compile(
        r"\b(?:write|create|generate|give|show)\s+(?:me\s+)?(?:a\s+|an\s+)?"
        r"(?:\w+\s+){0,3}?(?:python|java|c\+\+|c#|javascript|js|typescript|ts|sql|"
        r"bash|shell|go|rust|ruby|php|scala|kotlin|react)\b",
        re.I,
    ),
    re.compile(r"\b(?:python|java|javascript|node)\s+(?:web\s+)?(?:scraper|crawler|bot|spider)\b", re.I),
    re.compile(r"\bwrite\s+(?:me\s+)?(?:the\s+|a\s+|an\s+)?\w+\s+script\s+to\b", re.I),
    re.compile(r"\b(?:pip\s+install|npm\s+install|yarn\s+add|dockerfile|docker\s+compose|apt-get\s+install)\b", re.I),
    re.compile(r"\b(?:recipe|cook|bake|lasagna|pasta\s+recipe|what'?s\s+for\s+dinner)\b", re.I),
    re.compile(r"\b(?:tell\s+me\s+a\s+)?(?:joke|horoscope|astrological\s+sign)\b", re.I),
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

    def detect_dual_entities(self, query: str) -> list[str]:
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

        # Scope refusals are contract type 6, reported through the pipeline's
        # existing out_of_scope stage so every consumer keeps working unchanged.
        # The *reason* — code generation versus off-topic — is carried on
        # ``intent``, so the caller can say the right thing without guessing.
        if intent == QueryIntent.GUARDRAIL_INTERCEPT:
            return {
                "route": "out_of_scope",
                "tier": RoutingTier.TIER_3_REJECT.value,
                "intent": intent.value,
                "normalized_query": norm_q,
                "dual_entities": dual_ents,
                "similarity": 0.0,
                "error": "Out of scope",
                "message": OUT_OF_SCOPE_MESSAGE,
            }

        # Static-institution and scope intents never depend on the concept corpus,
        # so they bypass cosine thresholding entirely: "what are the Sunday
        # hours" has no semantic similarity to any concept node, and scoring it
        # against the corpus was the original cause of hours being deflected as
        # out-of-scope.
        if intent in (
            QueryIntent.CATALOG_SHELF_ROUTING,
            QueryIntent.AUTH_GATEWAY,
            QueryIntent.MCQ_DIAGNOSTIC,
            QueryIntent.INGESTION_ANALYSIS,
        ):
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
