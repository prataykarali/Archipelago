"""Compiled query routing and guardrail patterns."""

from __future__ import annotations

import re

# ── Malicious / Prompt Injection Patterns ─────────────────────────────────────
_INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bprint\s+(?:your\s+)?(?:rules|instructions|api\s*keys?|secrets?)\b", re.I),
    re.compile(r"\b(?:exfiltrate|leak|dump)\b", re.I),
    re.compile(r"\bcat\s+/etc/passwd\b", re.I),
    re.compile(r"\b(sudo|rm\s+-rf|chmod\s+\d+|bash\s+-c)\b", re.I),
    re.compile(
        r"\bwrite\s+(?:a\s+)?(?:python|c\+\+|javascript|code)\s+(?:script|program|function)\s+to\b",
        re.I,
    ),
    re.compile(r"\b(jailbreak|dan\s+mode|unrestricted\s+mode)\b", re.I),
]

# ── Conversational De-greasing Patterns ───────────────────────────────────────
_DEGREASE_PATTERNS = [
    re.compile(
        r"^(?:hey\s+(?:assistant|archipelago|there|bot)[\s,]+|hello[\s,]+|hi[\s,]+|greetings[\s,]+)",
        re.I,
    ),
    re.compile(
        r"^(?:(?:could|can|would)\s+you\s+)?(?:please\s+)?(?:give\s+(?:me\s+)?(?:an\s+)?overview\s+of|explain(?:\s+to\s+me)?|tell\s+me\s+about|show\s+me|help\s+me\s+with|define|describe)\s*",
        re.I,
    ),
    re.compile(r"^(?:what\s+(?:is|are|was|were)|how\s+does)\s*", re.I),
    re.compile(r"^(?:something\s+(?:vaguely\s+)?(?:related\s+to|about)\s+)", re.I),
]


# ── Dual-Entity Bridge Patterns (Fixing TC-04 Bug) ─────────────────────────────
_DUAL_ENTITY_PATTERNS = [
    re.compile(
        r"(?:how\s+does\s+)?(.+?)\s+(?:connect(?:s|ed)?\s+to|relate(?:s|d)?\s+to|bridge\s+to)\s+(.+)",
        re.I,
    ),
    re.compile(
        r"(?:path\s+between\s+|bridge\s+between\s+|relationship\s+between\s+)(.+?)\s+and\s+(.+)",
        re.I,
    ),
    re.compile(r"(.+?)\s+(?:vs\.?|versus)\s+(.+)", re.I),
    re.compile(r"(?:difference\s+between\s+|compare\s+)(.+?)\s+and\s+(.+)", re.I),
    re.compile(r"(?:how\s+do\s+)(.+?)\s+and\s+(.+?)\s+(?:differ|compare|interact)", re.I),
]


# ── Intent Patterns ───────────────────────────────────────────────────────────
_MCQ_PATTERNS = [
    re.compile(
        r"\b(quiz|diagnostic|assessment|test\s+my\s+knowledge|practice\s+questions?|mcqs?)\b", re.I
    ),
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
    re.compile(
        r"\b(shelf|stacks?|call\s+number|floor|aisle|barcode|holdings?|physical\s+copy|borrow|checkout|copies\s+available)\b",
        re.I,
    ),
    re.compile(
        r"\b(where\s+is\s+the\s+book|find\s+on\s+shelf|library\s+shelf|catalog\s+search)\b", re.I
    ),
    # "How many copies of X are available" and "Where are the lab manuals" are
    # location questions. Neither matched, so both were answered as concept
    # queries and scored against the curriculum kill-switch.
    re.compile(r"\bhow\s+many\s+(?:physical\s+)?copies\b", re.I),
    re.compile(r"\b(?:lab\s+manuals?|xerox|reprography)\b", re.I),
    re.compile(
        r"\bwhere\s+(?:are|is|do\s+i\s+find|can\s+i\s+find)\b.*\b(?:manual|handbook|textbook|book)\b",
        re.I,
    ),
]

_AUTH_GATEWAY_PATTERNS = [
    re.compile(
        r"\b(ndli|ieee(?:\s+explore)?|scopus|sciencedirect|springer|acm\s+digital\s+library)\b",
        re.I,
    ),
    re.compile(
        r"\b(e-?resources?|portal\s+link|passkey|credentials?|institutional\s+login|proxy\s+access)\b",
        re.I,
    ),
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
    re.compile(
        r"\b(?:is|are)\s+the\s+(?:library|reading\s+room|circulation\s+desk)\s+open\b", re.I
    ),
    re.compile(r"\bwhat\s+time\s+(?:does|do|is)\b.*\b(?:library|desk|open|close)\b", re.I),
]

_INGESTION_ANALYSIS_PATTERNS = [
    re.compile(
        r"\b(uploaded|newly\s+ingested|uploaded\s+paper|theorem\s+\d+|formula|equation\s+\d+|deep\s*link|#page=\d+)\b",
        re.I,
    ),
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
    re.compile(
        r"\b(?:python|java|javascript|node)\s+(?:web\s+)?(?:scraper|crawler|bot|spider)\b", re.I
    ),
    re.compile(r"\bwrite\s+(?:me\s+)?(?:the\s+|a\s+|an\s+)?\w+\s+script\s+to\b", re.I),
    re.compile(
        r"\b(?:pip\s+install|npm\s+install|yarn\s+add|dockerfile|docker\s+compose|apt-get\s+install)\b",
        re.I,
    ),
    re.compile(r"\b(?:recipe|cook|bake|lasagna|pasta\s+recipe|what'?s\s+for\s+dinner)\b", re.I),
    re.compile(r"\b(?:tell\s+me\s+a\s+)?(?:joke|horoscope|astrological\s+sign)\b", re.I),
]
