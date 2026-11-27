"""host_inference/engine/intent.py — Intent-Aware Routing Categories for Hosted Inference.

Mirror of archipelago.core.intent for standalone hosted deployment compatibility.
"""

from __future__ import annotations

import enum
import re


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
    CAPABILITY_INQUIRY = "CAPABILITY_INQUIRY"
    UNSUPPORTED = "UNSUPPORTED"


# ── Pattern Definitions ────────────────────────────────────────────────────────

# 1. ACADEMIC_INFO (institutional services, library policies, wifi, portal access, hours)
# 0. UNSUPPORTED (out-of-scope topics, malicious scraping, non-academic queries)
_UNSUPPORTED_PATTERNS = [
    re.compile(
        r"\b(recipe|lasagna|cook(?:ing)?|bake|weather|horoscope|sports|movie|song|lyrics|joke)\b",
        re.I,
    ),
    re.compile(
        r"\b(scraper|scrape|download\s+all|bypass|jailbreak|exploit\b|hack\b|ddos|(?:run|execute|perform)\s+sql\s+injection)\b",
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

_CAPABILITY_INQUIRY_PATTERNS = [
    re.compile(
        r"\bwhat\s+(?:domains?|subjects?|topics?|books?)\s+(?:do\s+you\s+(?:cover|have|support|index)|can\s+i\s+ask\s+about)\b",
        re.I,
    ),
    re.compile(
        r"\bwhat\s+can\s+(?:you\s+teach|archipelago\s+do|you\s+do)\b",
        re.I,
    ),
    re.compile(
        r"\bcan\s+you\s+(?:help\s+with|teach)\b",
        re.I,
    ),
    re.compile(
        r"\bdo\s+you\s+support\s+research[- ]paper\s+discovery\b",
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

# ── Query Operation vs. Academic Concept Separation ───────────────────────────

# Follow-on imperative/question clauses after a sentence boundary (?, ., ;).
_TRAILING_SENTENCE_OP_RE = re.compile(
    r"(?<=[\?\.;])\s+(?:and\s+)?(?:"
    r"explain|describe|compare|contrast|derive|demonstrate|calculate|compute|"
    r"give|show|provide|include|illustrate|walk\s+through|list|discuss|"
    r"summarize|define|outline|state|use|also|please"
    r")\b.*$",
    re.I,
)

# Trailing pedagogical/operation modifier clauses attached to a concept query.
_TRAILING_OPERATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "with_example",
        re.compile(
            r"(?:,\s*|\s+)(?:(?:and\s+)?(?:give|show|provide|include|use|walk\s+through)\s+|with\s+)"
            r"(?:a\s+|an\s+|some\s+|one\s+)?"
            r"(?:concrete\s+|worked\s+|simple\s+|brief\s+|short\s+|clear\s+|practical\s+|real[- ]world\s+)?"
            r"examples?(?:\s+(?:for\s+each|of\s+(?:it|them|this|how\b.*)))?\s*[\?\.\!]*$",
            re.I,
        ),
    ),
    (
        "step_by_step",
        re.compile(
            r"(?:,\s*|\s+)(?:in\s+a\s+)?step[- ]by[- ]step(?:\s+(?:manner|way|walkthrough|guide|explanation))?\s*[\?\.\!]*$",
            re.I,
        ),
    ),
    (
        "in_detail",
        re.compile(
            r"(?:,\s*|\s+)(?:in\s+(?:detail|simple\s+terms|plain\s+english|brief)|briefly|clearly|concisely)\s*[\?\.\!]*$",
            re.I,
        ),
    ),
    (
        "explain_aspect",
        re.compile(
            r"(?:,\s*|\s+)(?:and\s+)?(?:explain|describe|compare|discuss|illustrate|demonstrate|calculate|derive)\s+"
            r"(?:their|its|the)\s+(?:reliability|performance|trade[- ]?offs?|differences?|complexity|use\s+cases?|pros\s+and\s+cons|advantages?|disadvantages?|behavior|behaviour|working|mechanism|mechanics)\b.*$",
            re.I,
        ),
    ),
)

_LEADING_OPERATION_RE = re.compile(
    r"^(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|would\s+you\s+)?"
    r"(?:(?:explain|compare|contrast|derive|demonstrate|calculate|compute|"
    r"describe|define|summarize|illustrate|walk\s+through|tell\s+me\s+about|"
    r"teach\s+me\s+about|show\s+me|give\s+me)\s+)+",
    re.I,
)

# Standalone fragments that represent requested operations rather than academic concepts.
_OPERATION_FRAGMENT_RE = re.compile(
    r"^(?:"
    r"(?:with\s+)?(?:a\s+|an\s+|the\s+|some\s+|concrete\s+|worked\s+|simple\s+|brief\s+|short\s+|clear\s+|practical\s+)*examples?"
    r"|step[- ]by[- ]step(?:\s+(?:explanation|walkthrough|guide|derivation|calculation))?"
    r"|(?:in\s+)?detail|simple\s+terms|plain\s+english|brief(?:ly)?"
    r"|(?:their|its)\s+(?:reliability|performance|trade[- ]?offs?|differences?|complexity|use\s+cases?|pros\s+and\s+cons|working|mechanism)"
    r"|(?:explain|compare|contrast|derive|demonstrate|calculate|compute|describe|define|illustrate|give|show|provide|include)\b.*"
    r")$",
    re.I,
)


def strip_requested_operations(query: str) -> tuple[str, list[str]]:
    """Separate academic concept text from requested operations and example clauses.

    Returns ``(concept_clause, operations)`` where ``concept_clause`` preserves
    comparative/relational frames (e.g. ``difference between TCP and UDP``) while
    removing trailing follow-on sentences and pedagogical modifiers such as
    ``with an example``, ``step by step``, or ``? Explain their reliability``.
    """
    raw = re.sub(r"\s*\([Ee]arlier user topics?:.*?\)", "", query or "").strip()
    if not raw:
        return "", []

    operations: list[str] = []
    clause = raw

    # 1. Strip follow-on imperative/question sentences after ?, ., or ;.
    trailing_match = _TRAILING_SENTENCE_OP_RE.search(clause)
    if trailing_match:
        operations.append("follow_on_instruction")
        clause = clause[: trailing_match.start()].strip()

    # 2. Iteratively strip trailing pedagogical modifier clauses (e.g. "with an example").
    changed = True
    while changed:
        changed = False
        for op_name, pattern in _TRAILING_OPERATION_PATTERNS:
            m = pattern.search(clause)
            if m and m.start() > 0:
                candidate = clause[: m.start()].strip(" ,;")
                if candidate:
                    if op_name not in operations:
                        operations.append(op_name)
                    clause = candidate
                    changed = True

    # 3. Record leading operation verb without destroying comparison/relation frames.
    lead_match = _LEADING_OPERATION_RE.match(clause)
    if lead_match:
        lead_text = lead_match.group(0).strip().lower()
        for verb in ("explain", "compare", "contrast", "derive", "demonstrate", "calculate", "compute", "define", "describe"):
            if re.search(rf"\b{verb}\b", lead_text) and verb not in operations:
                operations.append(verb)

    return clause.strip(), operations


def extract_clean_concept_clause(query: str) -> str:
    """Return the primary academic concept clause with operation modifiers stripped."""
    clause, _ops = strip_requested_operations(query)
    return clause or (query or "").strip()


def clean_concept_fragment(fragment: str) -> str:
    """Clean one extracted concept candidate by stripping trailing clauses and modifiers."""
    text = (fragment or "").strip()
    if not text:
        return ""
    # Strip any trailing sentence after ? or . or ; (e.g. "UDP? Explain their reliability").
    text = re.split(r"[\?\.;]\s+", text, maxsplit=1)[0].strip()
    # Strip trailing operation modifiers.
    text, _ops = strip_requested_operations(text)
    # Strip leading determiners and dangling punctuation (preserve balanced parens like "(3NF)").
    text = re.sub(r"^(?:the|an|a)\s+", "", text, flags=re.I).strip(" ?.,!;:")
    if text.endswith(")") and text.count(")") > text.count("("):
        text = text.rstrip(")").strip()
    if text.startswith("(") and text.count("(") > text.count(")"):
        text = text.lstrip("(").strip()
    return text


def is_operation_fragment(fragment: str) -> bool:
    """Return True when ``fragment`` is a requested operation rather than an academic concept."""
    cleaned = re.sub(r"\s+", " ", (fragment or "").strip(" ?.,!;:()[]")).strip()
    if not cleaned:
        return True
    return bool(_OPERATION_FRAGMENT_RE.match(cleaned))


def classify_query_intent(
    query: str,
    extracted_concepts: list[str] | None = None,
    is_malicious: bool = False,
    is_out_of_scope: bool = False,
    has_evidence: bool = True,
) -> IntentCategory:
    """Classify user query into one of the 9 canonical IntentCategories."""
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

    # Priority 5b: System capability & domain coverage inquiries
    for pat in _CAPABILITY_INQUIRY_PATTERNS:
        if pat.search(ql):
            return IntentCategory.CAPABILITY_INQUIRY

    # Priority 6: Multi-concept questions (3+ concepts or 2 concepts with relation/comparison cues)
    if len(concepts) >= 3:
        return IntentCategory.MULTI_CONCEPT

    if len(concepts) >= 2:
        for cue in _MULTI_CONCEPT_CUES:
            if cue.search(ql):
                return IntentCategory.MULTI_CONCEPT
        if any(token in ql for token in ("compare", "versus", "vs", "difference", "relate", "connect", "between")):
            return IntentCategory.MULTI_CONCEPT

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

    if not has_evidence and not concepts:
        return IntentCategory.UNSUPPORTED

    if len(concepts) >= 2:
        return IntentCategory.MULTI_CONCEPT

    return IntentCategory.CONCEPT_LEARNING
