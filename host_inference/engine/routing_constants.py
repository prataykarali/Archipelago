"""Named thresholds and query cues for hosted chat routing."""

from __future__ import annotations

import re

# Routing thresholds and caps.
MIN_QUERY_LEN = 2
RANK_TOP_K = 6
ANCHOR_LIMIT = 3
NEIGHBOUR_NODE_LIMIT = 6
SHORTEST_PATH_LIMIT = 6
# Book-title token match: at least this many distinctive tokens must overlap.
BOOK_TITLE_MIN_OVERLAP = 2
BOOK_TITLE_TOKEN_MIN_LEN = 5
# Grounded routes whose draft is worth sending to the LLM for phrasing.
POLISHABLE_ROUTES = frozenset(
    {"GRAPH_SYNTHESIS", "GENERAL_EXPLANATION", "RELATION", "CROSS_DOMAIN", "BOOK_PAGE", "DEMO"}
)
# Comparison cue words that flip a relation reply into a comparative matrix.
COMPARE_CUES = ("compare", "versus", "vs", "difference", "differ", "different", "distinguish", "contrast")
COMPARE_CUES_DBMS = ("compare", "versus", "vs", "difference", "dbms", "b+")
SOURCE_LOOKUP_RE = re.compile(
    r"\b(?:open|download|page|pages|chapter|book|textbook|paper|pdf|"
    r"dataset|pearson|hugging\s*face|source|citation)\b",
    re.I,
)
WHERE_IS_RE = re.compile(r"^where\s+(?:is|are)\s+", re.I)
SHORT_DEFINITION_RE = re.compile(r"^(?:what\s+is|define|what\s+does)\b", re.I)
