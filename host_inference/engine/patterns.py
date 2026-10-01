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
    r"reading room|lending desk|when does the library)\b",
    re.I,
)
SHELF_RE = re.compile(
    r"\b(physical (book|copy|copies)|where can i find|call number|"
    r"on the shelf|which shelf|barcode|stacks?|rack)\b",
    re.I,
)
AUTH_RE = re.compile(
    r"\b(ieee|xplore|scopus|sciencedirect|ndli|springer|e-?resource|"
    r"subscription portal|institutional login|proxy login|pearson)\b",
    re.I,
)
DIAG_RE = re.compile(
    r"\b(roadmap|where (should|do) i (start|begin)|diagnostic|quiz me|"
    r"assess my|what should i study first|learning path|begin studying)\b",
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
