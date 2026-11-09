"""archipelago/core/intent.py — Intent-Aware Routing Categories and Classification.

Implements the 9 explicit intent categories for the Intelligent Reply Engine:
- CONCEPT_LEARNING: Definitions, mechanisms, learning prerequisites and examples.
- MULTI_CONCEPT: Relationships between X, Y, Z or more concepts.
- RESEARCH_TOPIC: Scientific findings, relevant existing literature and comparisons.
- PAPER_LOOKUP: Finding or identifying a paper, authors, publication, DOI and references.
- LIBRARY_LOOKUP: Books, availability, journal holdings, call numbers and locations.
- ACADEMIC_INFO: Institutional services, academic documents and library policies.
- PERSONALIZED_LEARNING: Explicit roadmaps, diagnostic quizzes, prerequisite maps.
- RESEARCH_INTELLIGENCE: Authorized bibliometric analysis, delegated to the research pipeline.
- UNSUPPORTED: Honest fallback when evidence is missing or query is out of scope / malicious.
"""

from __future__ import annotations

import enum
import re
from typing import Any


class IntentCategory(enum.StrEnum):
    """The 9 canonical intent categories for Archipelago S1."""

    CONCEPT_LEARNING = "CONCEPT_LEARNING"
    MULTI_CONCEPT = "MULTI_CONCEPT"
    RESEARCH_TOPIC = "RESEARCH_TOPIC"
    PAPER_LOOKUP = "PAPER_LOOKUP"
    LIBRARY_LOOKUP = "LIBRARY_LOOKUP"
    ACADEMIC_INFO = "ACADEMIC_INFO"
    PERSONALIZED_LEARNING = "PERSONALIZED_LEARNING"
    RESEARCH_INTELLIGENCE = "RESEARCH_INTELLIGENCE"
    UNSUPPORTED = "UNSUPPORTED"


# ── Pattern Definitions ────────────────────────────────────────────────────────

# 0. UNSUPPORTED (out-of-scope topics, malicious scraping, non-academic queries)
_UNSUPPORTED_PATTERNS = [
    re.compile(
        r"\b(recipe|lasagna|cook(?:ing)?|bake|weather|horoscope|sports|movie|song|lyrics|joke)\b",
        re.I,
    ),
    re.compile(
        r"\b(scraper|scrape|download\s+all|bypass|jailbreak|exploit|hack|ddos|sql\s+injection)\b",
        re.I,
    ),
]

# 1. ACADEMIC_INFO (institutional services, library policies, wifi, portal access, hours)
_ACADEMIC_INFO_PATTERNS = [
    re.compile(
        r"\b(opening\s+hours|library\s+hours|closing\s+time|schedule|holiday\s+hours|sunday\s+hours)\b",
        re.I,
    ),
    re.compile(
        r"\b(wifi|remote\s+access|off-campus\s+access|ezproxy|vpn|portal\s+login|library\s+card|borrowing\s+policy|fines|overdue|circulation\s+desk)\b",
        re.I,
    ),
    re.compile(
        r"\b(how\s+do\s+i\s+(?:log\s*in(?:\s+to)?|access|connect(?:\s+to)?)\s+(?:scopus|ieee|web\s+of\s+science|springer|science\s*direct))\b",
        re.I,
    ),
]

# 2. LIBRARY_LOOKUP (physical/digital book availability, call number, shelf, copies)
_LIBRARY_LOOKUP_PATTERNS = [
    re.compile(
        r"\b(call\s+number|shelf\s+location|physical\s+copy|copies\s+available|where\s+(?:is|can\s+i\s+find)\s+(?:the\s+book|a\s+physical\s+copy)|on\s+campus\s+shelf)\b",
        re.I,
    ),
    re.compile(
        r"\b(where\s+(?:is|can\s+i\s+find)\b.+?\b(?:in\s+the\s+library|on\s+shelf|shelf))\b",
        re.I,
    ),
    re.compile(
        r"\b(how\s+many\s+copies|is\s+the\s+book\s+available|check\s+shelf|borrow\s+book|book\s+inventory)\b",
        re.I,
    ),
    re.compile(
        r"\b(journal\s+holdings|journal\s+inventory|show\s+journal\s+inventory|(?:what|which)\s+books\s+(?:are\s+)?in\s+the\s+library|books\s+in\s+the\s+library)\b",
        re.I,
    ),
]

# 3. PAPER_LOOKUP (identifying papers, authors, citations, DOIs, publication venues)
_PAPER_LOOKUP_PATTERNS = [
    re.compile(
        r"\b(who\s+(?:wrote|authored)|which\s+paper\s+introduced|author\s+of|doi\s+for|citation\s+for\s+paper)\b",
        re.I,
    ),
    re.compile(
        r"\b(find\s+(?:the\s+)?paper|paper\s+title|identify\s+(?:the\s+)?paper|published\s+in\s+(?:neurips|icml|iclr|cvpr|acl|aaai|kdd))\b",
        re.I,
    ),
    re.compile(
        r"\b(give\s+me\s+(?:the\s+)?citations\s+of|citation\s+count\s+of|references\s+of\s+this\s+paper)\b",
        re.I,
    ),
]

# 4. PERSONALIZED_LEARNING (explicit quizzes, diagnostic tests, learning roadmaps)
_PERSONALIZED_LEARNING_PATTERNS = [
    re.compile(
        r"\b(quiz\s+me|test\s+my\s+knowledge|diagnostic\s+quiz|learning\s+roadmap|personalized\s+(?:path|graph)|assessment)\b",
        re.I,
    ),
    re.compile(
        r"\b(generate\s+(?:a\s+)?quiz|start\s+(?:a\s+)?diagnostic|evaluate\s+my\s+understanding|study\s+plan\s+for\s+me)\b",
        re.I,
    ),
]

# 5. RESEARCH_INTELLIGENCE (bibliometric analysis, topic inventories, research pipeline)
_RESEARCH_INTELLIGENCE_PATTERNS = [
    re.compile(
        r"\b(bibliometric|h-index\s+analysis|citation\s+network\s+analysis|topic\s+inventory|ingested\s+topics|research\s+atlas)\b",
        re.I,
    ),
    re.compile(
        r"\b(harvest\s+papers|research\s+worker|research\s+queue|topic-to-paper\s+records)\b",
        re.I,
    ),
]

# 6. MULTI_CONCEPT (relationship, connection, or comparison between 2+ entities)
_MULTI_CONCEPT_CUES = [
    re.compile(
        r"\b(how\s+(?:are|is|do)\s+.+?\s+(?:and|,|with)\s+.+?\s+(?:related|connected|interact|differ))\b",
        re.I,
    ),
    re.compile(
        r"\b(relationship|connection|relation)\s+between\s+.+?\s+(?:and|,)\s+.+\b",
        re.I,
    ),
    re.compile(
        r"\b(compare|comparison|versus|vs\.?|difference\s+between)\s+.+?\s+(?:and|,|with|to)\s+.+\b",
        re.I,
    ),
]

# 7. RESEARCH_TOPIC (scientific findings, literature synthesis, state of the art)
_RESEARCH_TOPIC_PATTERNS = [
    re.compile(
        r"\b(recent\s+(?:studies|research|papers|advances)|latest\s+(?:findings|literature|works)|current\s+state\s+of\s+the\s+art|sota)\b",
        re.I,
    ),
    re.compile(
        r"\b(literature\s+review|empirical\s+evidence|research\s+gaps?|open\s+problems?|ablation\s+studies)\b",
        re.I,
    ),
]

# 8. CONCEPT_LEARNING (definitions, mechanisms, explanations, prerequisites)
_CONCEPT_LEARNING_PATTERNS = [
    re.compile(
        r"^(what\s+is|define|explain|how\s+does|how\s+do|teach\s+me\s+about|i\s+want\s+to\s+learn|tell\s+me\s+about)\b",
        re.I,
    ),
    re.compile(
        r"\b(prerequisites?\s+(?:for|to)|what\s+should\s+i\s+learn\s+before|how\s+does\s+it\s+work|formula\s+for|derivation\s+of)\b",
        re.I,
    ),
]


def classify_query_intent(
    query: str,
    extracted_concepts: list[str] | None = None,
    is_malicious: bool = False,
    is_out_of_scope: bool = False,
    has_evidence: bool = True,
) -> IntentCategory:
    """Classify user query into one of the 9 canonical IntentCategories.

    Args:
        query: Raw or normalized query string.
        extracted_concepts: Optional list of identified concepts in the query.
        is_malicious: True if firewall intercepted malicious attack or injection.
        is_out_of_scope: True if topic is completely outside CS/AI domain.
        has_evidence: True if corpus has relevant evidence/nodes.

    Returns:
        IntentCategory enum member.
    """
    if is_malicious or is_out_of_scope:
        return IntentCategory.UNSUPPORTED

    q = (query or "").strip()
    if not q:
        return IntentCategory.UNSUPPORTED

    ql = q.lower()
    concepts = extracted_concepts or []

    # Priority 0: Explicit out-of-scope or malicious queries
    for pat in _UNSUPPORTED_PATTERNS:
        if pat.search(ql):
            return IntentCategory.UNSUPPORTED

    # Priority 1: Deterministic check for institutional administrative / access questions
    for pat in _ACADEMIC_INFO_PATTERNS:
        if pat.search(ql):
            return IntentCategory.ACADEMIC_INFO

    # Priority 2: Library physical / holding queries
    for pat in _LIBRARY_LOOKUP_PATTERNS:
        if pat.search(ql):
            return IntentCategory.LIBRARY_LOOKUP

    # Priority 3: Paper metadata / bibliographic lookup
    for pat in _PAPER_LOOKUP_PATTERNS:
        if pat.search(ql):
            return IntentCategory.PAPER_LOOKUP

    # Priority 4: Personalized learning / diagnostic assessment
    for pat in _PERSONALIZED_LEARNING_PATTERNS:
        if pat.search(ql):
            return IntentCategory.PERSONALIZED_LEARNING

    # Priority 5: Research intelligence / bibliometrics
    for pat in _RESEARCH_INTELLIGENCE_PATTERNS:
        if pat.search(ql):
            return IntentCategory.RESEARCH_INTELLIGENCE

    # Priority 6: Multi-concept questions (3+ concepts or 2 concepts with relation/comparison cues)
    if len(concepts) >= 3:
        return IntentCategory.MULTI_CONCEPT

    if len(concepts) >= 2:
        for cue in _MULTI_CONCEPT_CUES:
            if cue.search(ql):
                return IntentCategory.MULTI_CONCEPT
        if any(token in ql for token in ("compare", "versus", "vs", "difference", "relate", "connect", "between")):
            return IntentCategory.MULTI_CONCEPT

    # Also check multi-concept regexes even if entity extractor hasn't populated concepts yet
    for cue in _MULTI_CONCEPT_CUES:
        if cue.search(ql):
            return IntentCategory.MULTI_CONCEPT

    # Priority 7: Research topic literature questions
    for pat in _RESEARCH_TOPIC_PATTERNS:
        if pat.search(ql):
            return IntentCategory.RESEARCH_TOPIC

    # Priority 8: Concept learning
    for pat in _CONCEPT_LEARNING_PATTERNS:
        if pat.search(ql):
            return IntentCategory.CONCEPT_LEARNING

    # Check evidence presence: if evidence is explicitly false and no concepts found
    if not has_evidence and not concepts:
        return IntentCategory.UNSUPPORTED

    # Default pedagogical path
    if len(concepts) >= 2:
        return IntentCategory.MULTI_CONCEPT

    return IntentCategory.CONCEPT_LEARNING
