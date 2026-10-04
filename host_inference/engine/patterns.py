"""Intent-detection regular expressions for the hosted librarian engine.

Each pattern names the concrete user intent it recognises so routing reads as a
sequence of intent checks rather than a list of raw regex bodies.
"""
from __future__ import annotations

import re

INJECTION = re.compile(
    r"(ignore\s+(all\s+)?previous|system\s+prompt|<\s*system\s*>|\[INST\]|"
    r"os\.system|rm\s+-rf|act\s+as\b|jailbreak|developer\s+mode|"
    r"print\s+your\s+instructions|you\s+are\s+now\b)",
    re.I,
)
CODE_TRAP = re.compile(
    r"(\bwrite\s+(me\s+)?(a\s+)?(python|code|script|essay|docker)|"
    r"\bpytorch\b|\bbash\b|\bcurl\b|\bdockerfile\b|\bpip\s+install\b|"
    r"\btraining\s+loop\b|\bhomework\b|\b500-word\b|\bgenerate\s+code\b|"
    r"\bimplement\s+.{0,40}\bin\s+python\b)",
    re.I,
)
SCHEDULE_RE = re.compile(
    r"\b(opening hours|library hours|what time|timetable|circulation desk|"
    r"reading room|lending desk|when does the library|"
    # Day-scoped hours ("library Sunday hours", "Monday timings") previously fell
    # through to the OOD kill-switch: "library hours" only matched when the two
    # words were adjacent, so any day qualifier broke it.
    r"(sun(day|day)?|mon(day|day)?|tues(day|day)?|wed(nesday)?|thur(sday)?|"
    r"fri(day)?|sat(urday)?|holiday)\s+(hours|timings?|schedule|open(ing)?)|"
    r"hours\s+(on|for)\s+(sun|mon|tues|wed|thur|fri|sat)|"
    r"is the (library|reading room) open)\b",
    re.I,
)
SHELF_RE = re.compile(
    r"\b(physical (book|copy|copies)|where can i find|where do i find|"
    r"where is .*(?:book|concepts|textbook)|call number|on the shelf|which shelf|barcode|stacks?|rack|"
    # "a physical copy on campus" / "copies available" are shelf intents that the
    # original pattern missed because it required "copy" to follow "physical".
    r"copies? (available|available\?|in stock)|availability|"
    r"(available|availability)\s+(copies|books?|titles?)|"
    # "How many copies of X are available" splits the noun from the adjective,
    # so neither adjacency rule fires and the query was answered as a book page.
    r"how many (physical )?(copies|books?|titles?)\b|"
    r"(copies|books?|titles?)\b[^?!]{0,60}\b(are|is)\s+available\b|"
    r"\b(issue\s+status|due\s+date)\b|"
    r"in the library|borrow|issue)\b",
    re.I,
)
AUTH_RE = re.compile(
    r"\b(ieee|xplore|scopus|sciencedirect|ndli|springer|e-?resource|"
    r"subscription portal|institutional login|proxy login|pearson|"
    # "Scopus login" matched before; "access IEEE off-campus" did not, because
    # "access" alone carried no signal. Access + portal/proxy/off-campus does.
    r"off-?campus|remote access|proxy|credentials?|"
    r"how (do|can) i (access|log ?in)|access (the )?\w+ (database|portal|journal)|"
    r"login to|log in to|sign in to)\b",
    re.I,
)
DIAG_RE = re.compile(
    r"\b(roadmap|where (should|do) i (start|begin)|diagnostic|quiz me|"
    r"assess my|what should i study first|learning path|begin studying|"
    # Curriculum requests are the contract's own examples. "I want to learn X"
    # and "Teach me Y" were routed to BOOK_PAGE because no pattern matched.
    r"i want to learn|i'?d like to learn|teach me|teach me about|"
    r"show learning (roadmap|path)|explain step by step|study plan|"
    r"curriculum for|prepare me for|revision plan)\b",
    re.I,
)
# Contract type 5: live analysis of an uploaded paper. Distinguished from a
# request to analyse a *specific known* paper, which stays a concept question.
INGEST_RE = re.compile(
    r"\b(analy[sz]e|extract|ingest|index|scan|process)\b[^.?!]{0,40}\b"
    r"(this |the |my |attached |uploaded )?(pdf|paper|document|file|"
    r"okf|manuscript)\b|"
    r"\b(upload|uploaded|ingest(ing)?|okf nodes?|extract)\b[^.?!]{0,30}\b"
    r"(paper|pdf|document|file)\b",
    re.I,
)
RELATE_RE = re.compile(
    r"\b(how (are|is)|relation|related|connect|difference|compare|versus|vs\.?)\b",
    re.I,
)
PARAM_RE = re.compile(
    r"\b(memory consumption|vram|parameter count|qiskit\s*v?\d|exact latency|"
    r"hyperparameter|bytes of memory|implementation formula)\b",
    re.I,
)
