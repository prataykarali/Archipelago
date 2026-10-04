"""Routing constants: suggested anchors, small-talk patterns, vocab lists."""
from __future__ import annotations

import re

_SUGGESTED_QUERY_ANCHORS = {
    "lora": "low_rank_adaptation",
    "lora_vs_bert": "low_rank_adaptation",
    "rag": "rag",
    "bert": "bert",
    "attention": "attention_mechanism",
    "dbms_buffer": "retrieval",
    "ostep_paging": "paging",
    "graphrag": "graph_rag",
    "peft_rank": "rag",
    "multi_rag_dbms": "rag",
}

# Patterns for pure conversational small talk — no technical/computational content
_PURE_SMALL_TALK_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|yo|sup|howdy|greetings|good\s+(?:morning|afternoon|evening)|"
    r"how\s+(?:are|r)\s+you\b|how\s+can\s+i\s+help|what'?s\s+(?:up|your\s+name)|"
    r"what\s+(?:is|are)\s+your\s+name|tell\s+me\s+your\s+name|what\s+(?:can|do)\s+you\s+do|"
    r"what\s+can\s+you\s+(?:help\s+with|do)|"
    r"tell\s+me\s+your\s+age|how\s+old\s+are\s+you|"
    r"nice\s+to\s+meet\s+you|good\s+to\s+(?:see|meet)\s+you|"
    r"who\s+are\s+you\b|are\s+you\s+(?:real|alive|human|a\s+bot|an\s+ai)|"
    r"good\s+(?:morning|afternoon|evening)\s+to\s+you|"
    r"what'?s\s+going\s+on|how'?s\s+it\s+going|how\s+have\s+you\s+been|"
    r"how\s+do\s+you\s+do|pleased\s+to\s+meet\s+you|"
    r"long\s+time\s+no\s+see|it'?s\s+(?:good|great|nice)\s+to\s+(?:see|meet)\s+you|"
    r"good\s+to\s+talk\s+to\s+you|"
    r"[?!.\s]*$"
    r")",
    re.I | re.UNICODE,
)

# Conversational lead-ins that appear before the real query
_SMALL_TALK_PREFIXES = re.compile(
    r"^\s*(?:"
    r"(?:hi|hello|hey|yo|sup|howdy)\s*,?\s*|"
    r"(?:good\s+(?:morning|afternoon|evening))\s*,?\s*|"
    r"(?:well|anyway|so|btw|by\s+the\s+way)\s*,?\s*|"
    r"(?:hey|hi)\s+how'?s\s+it\s+going\s*,?\s*|"
    r"(?:anyway|anyhow)\s*,?\s*|"
    r"(?:how\s+are\s+you\??|how'?s\s+it\s+going\??)\s*,?\s*"
    r")+",
    re.I | re.UNICODE,
)

# Technical/ML markers for small-talk stripping heuristic.
# NOTE: every alternative must consume ≥1 char — optional groups that can
# match the empty string make re.search("hi") succeed and break chitchat.
_TECHNICAL_MARKERS = re.compile(
    r"\b(?:"
    r"ai|a\.i\.?|ml|aiml|ai/?ml|machine\s+learning|deep\s+learning|"
    r"data\s+science|neural|network|llm|transformer|attention|backprop|"
    r"gradient|optimizer|lora|rag|bert|gpt|encoder|decoder|embedding|"
    r"token|logit|latent|convex|nonconvex|regression|classification|"
    r"supervised|unsupervised|reinforcement|q-?learning|policy|"
    r"reward|agent|environment|state|action|observation|"
    r"forward\s+pass|backward\s+pass|loss|cost|function|"
    r"activation|relu|sigmoid|tanh|softmax|cross-?entropy|"
    r"batch|epoch|learning\s+rate|momentum|weight|bias|"
    r"layer|hidden\s+layer|output\s+layer|input\s+layer|"
    r"convolution|pooling|filter|kernel|feature\s+map|"
    r"attention\s+mechanism|self-?attention|"
    r"multi-?head\s+attention|positional\s+encoding|"
    r"matrix|matrices|jacobian|covariance|probability|likelihood|estimation|bayesian|entropy|"
    r"backpropagation|fine-?tun\w*|"
    r"premium\s+llm|openai|anthropic|google\s+ai|microsoft\s+ai|"
    r"hugging\s*face|huggingface"
    r")\b",
    re.I | re.UNICODE,
)

# Soft tone/style requests — strip so theory ranking still works (persona lock
# in the system prompt enforces dry academic tone). Not a banlist of topics.
_PERSONA_STYLE_NOISE = re.compile(
    r"(?:"
    r"using\s+gen\s*z\s+slang|gen\s*z\s+slang|using\s+slang|in\s+slang|"
    r"(?:a\s+)?bunch\s+of\s+emojis|lots\s+of\s+emojis|use\s+emojis|with\s+emojis|"
    r"explain\s+like\s+i'?m\s+5|\beli5\b|"
    r"in\s+the\s+style\s+of\s+\w+|as\s+a\s+pirate|talk\s+like\s+a\s+\w+"
    r")",
    re.I | re.UNICODE,
)

# Non-domain filler/academic vocabulary — tokens here are never "foreign"
_SANITY_FILLER = frozenset({
    "the", "and", "for", "with", "this", "that", "these", "those", "does",
    "can", "could", "would", "should", "will", "shall", "may", "might", "must",
    "what", "whats", "which", "where", "when", "how", "why", "who", "are",
    "was", "were", "has", "have", "had", "you", "your", "our", "their", "its",
    "please", "tell", "give", "need", "know", "want", "wanna", "help", "just",
    "gist", "explain", "define", "describe", "compare", "contrast", "between",
    "difference", "different", "differences", "versus", "learn", "learning",
    "study", "student", "understand", "curriculum", "path", "paths", "course",
    "prerequisite", "prerequisites", "upstream", "downstream", "node", "nodes",
    "graph", "bridge", "trace", "map", "identify", "lens", "concept",
    "concepts", "library", "book", "books", "paper", "papers", "connect",
    "connects", "connection", "relationship", "relationships", "diverge",
    "mechanism", "process", "better", "best", "perform", "performs", "handle",
    "handles", "directly", "observe", "observed", "fit", "fits", "into",
    "through", "about", "vanilla", "skip", "become", "share", "common",
    "highest", "most", "many", "much", "use", "used", "using", "way", "other",
    "around", "depend", "depends", "not", "one", "two", "long", "short",
    "sequence", "sequences", "man", "hey", "buddy", "cool", "now", "good",
    "evening", "morning", "tired", "math", "hard", "also", "really", "maximum", "minimum",
    "from", "they", "them", "any", "some", "all", "but", "than", "then",
    "there", "here", "each", "both", "very", "more", "less", "only", "even",
    # graph-navigation vocabulary (curriculum questions, not foreign content)
    "inaccessible", "accessible", "unlock", "unlocks", "unlocked", "reach",
    "reachable", "unreachable", "skipping", "hop", "hops", "multi", "degree",
    # student curriculum & pedagogical progression terms
    "before", "after", "start", "starting", "started", "master", "mastering",
    "mastered", "train", "training", "trained", "once", "model", "models",
    "build", "building", "built", "test", "testing", "solve", "solving",
})

# Question framing stripped before graph-coverage checks ("what is rag" → "rag")
_QUESTION_FRAMING_RE = re.compile(
    r"^(what\s+is|what's|whats|what\s+are|explain|tell\s+me\s+about|tell\s+me|"
    r"how\s+does|how\s+do|define|describe|teach\s+me|about)\s+",
    re.I,
)
_COVERAGE_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "of", "for", "and", "or",
    "in", "on", "at", "to", "from", "by", "with", "it", "its", "this", "that",
    "what", "whats", "how", "do", "does", "did", "me", "my", "i", "we", "you",
    "please", "can", "could", "would", "should", "about", "tell", "explain",
})
