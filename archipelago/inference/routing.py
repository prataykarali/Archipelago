"""Query routing: graph | library | out_of_scope | general_chat | small_talk.

Defenses scale via embedding/LLM intent prototypes (intent_gate) + embedder
kill-switch — not keyword banlists of forbidden entities.
"""
from __future__ import annotations

import re

from archipelago.inference.ranking import (
    rank_concepts, find_anchor_concept, _select_soft_anchor,
    _is_chitchat, _is_offtopic, _is_learning_or_domain_query,
    _has_domain_terms, _is_learning_intent, _is_identity, _is_onboarding,
    normalize_user_query, _has_surface_concept_hit, _has_strong_graph_evidence,
)
from archipelago.inference.scope_gate import is_aiml_in_scope
from archipelago.inference.intent_gate import (
    classify_intent,
    intent_to_block_reason,
    INTENT_THEORY,
    INTENT_SOCIAL,
    INTENT_IMPLEMENTATION,
    INTENT_OUT_OF_DOMAIN,
    INTENT_ENTITY_TRIVIA,
    INTENT_META,
    REASON_IMPLEMENTATION,
    REASON_OUT_OF_SCOPE,
    REASON_NOT_IN_CORPUS,
    REASON_META,
)
from archipelago.inference import state as st
from archipelago.inference.aliases import generate_aliases, _clean_query_words

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
    r"matrix|matrices|jacobian|covariance|probability|"
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


def _strip_small_talk(query: str) -> tuple:
    """Return (is_small_talk, remaining_query)."""
    q = (query or "").strip()
    if not q:
        return True, ""

    stripped = _SMALL_TALK_PREFIXES.sub("", q).strip()

    if _PURE_SMALL_TALK_PATTERNS.fullmatch(stripped):
        return True, stripped

    if not _TECHNICAL_MARKERS.search(stripped):
        return True, stripped

    if len(stripped.split()) <= 4 and not _TECHNICAL_MARKERS.search(stripped):
        return True, stripped

    return False, stripped


def _strip_persona_style(query: str) -> tuple[str, bool]:
    """Remove tone/style instructions; keep the technical ask."""
    q = (query or "").strip()
    if not q or not _PERSONA_STYLE_NOISE.search(q):
        return q, False
    cleaned = _PERSONA_STYLE_NOISE.sub(" ", q)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.?!")
    return (cleaned or q), True


def _merge_slots(base_slots: dict, extra: dict) -> dict:
    out = dict(base_slots or {})
    out.update(extra or {})
    return out


def _run_dual_pass_guard(query: str) -> bool:
    import os
    import sys
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        from archipelago.inference.llm_gateway import gateway_chat

        ans = gateway_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a security guard. Is the user asking to write, draft, or generate code, programming scripts, configuration files, emails, or personal advice? "
                        "Answer YES only if they want you to write or generate these software/administrative artifacts. "
                        "Answer NO if they are asking a theoretical, mathematical, conceptual, or syllabus-related question about machine learning, even if they ask to explain it in a creative style, format, or creative script (e.g. songs, poems, or audio play scripts)."
                    ),
                },
                {"role": "user", "content": query},
            ],
            purpose="routing",
            temperature=0.0,
            max_tokens=8,
            timeout=8,
        ) or ""
        return "YES" in ans.strip().upper()
    except Exception:
        return False

def _get_active_concept_from_history(history: list) -> str | None:
    """Scan conversational history (newest to oldest) to find the active concept.

    Assistant turns are mined too — they name the anchor concept of the previous
    answer, which is exactly what a follow-up pronoun ("it", "that") refers to.
    """
    if not history:
        return None
    for h in reversed(history):
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            # Try to find a strong concept anchor first
            anchor_id, score = find_anchor_concept(content)
            if anchor_id:
                return anchor_id
            # Fallback to top ranked concept with a reasonable score threshold
            ranked = rank_concepts(content, top_k=1)
            if ranked and ranked[0].get("cos", 0.0) >= 0.50:
                return ranked[0]["id"]
        elif role == "assistant":
            # Assistant prose mentions concept labels — lexical scan only
            # (no embedding of long answers). Longest label wins to avoid
            # generic single-word labels shadowing the real anchor.
            cl = content.lower()
            best_id, best_len = None, 0
            for cid, concept in st.CONCEPTS_DATA.items():
                label = (concept.get("label") or concept.get("name") or "").lower()
                if len(label) >= 4 and label in cl and len(label) > best_len:
                    best_id, best_len = cid, len(label)
            if best_id:
                return best_id
    return None


def _extract_quiz_answers(text: str) -> dict[str, str]:
    """Extract student quiz responses like {'1': 'A', '2': 'B', ...} from natural text."""
    answers = {}
    if not text:
        return answers
    # Pattern 1: Numbered answers e.g. "1-A, 2-B, 3-C, 4-D, 5-A", "1. A 2. B", "Q1: C", "1A 2B"
    for m in re.finditer(r"(?:q(?:uestion)?\s*)?([1-9])\s*[-:.)]?\s*([A-Da-d])\b", text):
        answers[str(m.group(1))] = m.group(2).upper()
    if answers:
        return answers
    # Pattern 2: Comma or space separated letters e.g. "A, B, C, D, A" or "A B C D A"
    letters = re.findall(r"\b([A-Da-d])\b", text)
    if len(letters) >= 3:
        for idx, letter in enumerate(letters[:6], 1):
            answers[str(idx)] = letter.upper()
        return answers
    return answers


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
    "evening", "morning", "tired", "math", "hard", "also", "really",
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

_sanity_vocab_cache: dict = {"key": None, "vocab": frozenset()}


def _graph_vocab() -> frozenset:
    """Token vocabulary of every concept id/label/alias in the loaded graph."""
    key = (id(st.CONCEPTS_DATA), len(st.CONCEPTS_DATA))
    if _sanity_vocab_cache["key"] == key:
        return _sanity_vocab_cache["vocab"]
    vocab = set()
    for cid, concept in st.CONCEPTS_DATA.items():
        for text in (
            cid.replace("_", " "),
            concept.get("label") or "",
            concept.get("name") or "",
            *(concept.get("aliases") or []),
        ):
            tl = (text or "").lower()
            vocab |= _clean_query_words(tl)
            # Compact multi-word form: "graph rag" → "graphrag"
            compact = re.sub(r"[\s\-_]+", "", tl)
            if 3 <= len(compact) <= 24:
                vocab.add(compact)
    for term in st._DOMAIN_TERMS:
        vocab |= _clean_query_words(term)
    _sanity_vocab_cache["key"] = key
    _sanity_vocab_cache["vocab"] = frozenset(vocab)
    return _sanity_vocab_cache["vocab"]


def _foreign_tokens(query: str) -> list:
    """Content tokens not explained by the graph vocabulary or filler words."""
    vocab = _graph_vocab()
    out = []
    for tok in re.findall(r"[a-z][a-z']{2,}", (query or "").lower()):
        tok = tok.strip("'")
        if tok in _SANITY_FILLER or tok in vocab:
            continue
        if tok.endswith("s") and (tok[:-1] in vocab or tok[:-1] in _SANITY_FILLER):
            continue
        if _TECHNICAL_MARKERS.search(tok):
            continue
        out.append(tok)
    return out


def _run_sanity_guard(query: str) -> bool:
    """LLM check for absurd cross-domain mixes and external-authority trivia.

    Returns True when the query should be refused. Only invoked when the query
    contains graph-known concepts *plus* foreign content tokens (Batman,
    sourdough, carbon footprint, a researcher's opinions…) — a serious theory
    question about indexed concepts never pays this extra call.
    """
    import os
    import sys
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        from archipelago.inference.llm_gateway import gateway_chat

        ans = gateway_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer YES only if this question can be answered purely with "
                        "mathematics and machine learning theory from a textbook. "
                        "Answer NO if answering would require knowledge about: food, sports, "
                        "sports predictions or winners, movies, fictional or famous people, "
                        "magic, law, history, gardening, personal life, anyone's opinions or "
                        "stance or ethics views, companies, hardware, software or library "
                        "versions, prices, energy or carbon footprints, patents, downloads, "
                        "or replication logistics.\n"
                        "Examples:\n"
                        "Q: Can a hidden Markov model predict who wins the World Cup? -> NO (sports prediction)\n"
                        "Q: Which framework version do the authors recommend? -> NO (software version)\n"
                        "Q: What is the stance of the authors on ethics? -> NO (opinions/ethics stance)\n"
                        "Q: Compare energy usage of training two models. -> NO (energy/carbon)\n"
                        "Q: What is the chain rule used for in backpropagation? -> YES\n"
                        "Q: Which concepts are prerequisites for attention? -> YES\n"
                        "Answer YES or NO only."
                    ),
                },
                {"role": "user", "content": query},
            ],
            purpose="routing",
            temperature=0.0,
            max_tokens=8,
            timeout=8,
        ) or ""
        ans = ans.strip().upper()
        return not ans.startswith("YES")
    except Exception:
        return False


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


def _graph_block_override(query: str, ranked: list) -> list | None:
    """Graph-grounded veto of intent-gate hard blocks.

    Returns the matched top labels when the graph itself clearly covers the
    query (alias/acronym/core hit AND the match explains most of the query's
    content words) — meaning a "not in scope" verdict from the tiny classifier
    is wrong and routing should continue. Returns None when the graph has
    nothing genuinely related, so real off-topic blocks still stand.
    """
    if not ranked:
        return None
    norm = normalize_user_query(query)
    core = _QUESTION_FRAMING_RE.sub("", norm).strip(" ?!.") or norm
    tokens = {
        t for t in _clean_query_words(core)
        if t not in _COVERAGE_STOPWORDS
    }
    if not tokens:
        return None
    for r in ranked[:5]:
        alias_boost = float(r.get("alias_boost") or 0.0)
        core_boost = float(r.get("core_boost") or 0.0)
        lexical = float(r.get("lexical") or 0.0)
        if alias_boost < 0.26 and core_boost < 0.35 and lexical < 0.72:
            continue
        concept = st.CONCEPTS_DATA.get(r.get("id") or "", {})
        aliases = concept.get("aliases") or generate_aliases(concept)
        alias_tokens = set()
        for a in aliases:
            alias_tokens |= _clean_query_words((a or "").lower())
        label_tokens = _clean_query_words(
            (r.get("label") or r.get("name") or "").lower()
        )
        alias_tokens |= label_tokens
        matched = {
            t for t in tokens
            if t in alias_tokens or (t.endswith("s") and t[:-1] in alias_tokens)
        }
        if len(matched) / len(tokens) >= 0.5:
            return [
                x.get("label") or x.get("name") or x.get("id")
                for x in ranked[:3]
            ]
    return None

def resolve_query_routing(query: str, history: list | None = None) -> dict:
    res = _resolve_query_routing(query, history=history)
    if isinstance(res, dict):
        reason = res.get("reason") or ""
        rl = reason.lower()
        if res.get("route") == "out_of_scope":
            if "implementation" in rl:
                reason = "implementation_request"
            elif "not_in_corpus" in rl or "entity" in rl:
                reason = "not_in_corpus"
            elif "meta" in rl:
                reason = "meta_refused"
            else:
                reason = "out_of_scope"
            res["reason"] = reason
            res["block_reason"] = reason
        else:
            res["block_reason"] = None

        # ── Semantic Safety Net only for general Out-of-Scope (non-policy) ──
        # Sanity-guard / dual-pass verdicts are deliberate rejections of
        # absurd or trivia asks — never soften those back into suggestions.
        guarded = (res.get("slots") or {}).get("intent_method") in (
            "sanity_guard", "dual_pass_guard", "offtopic_mix", "emotional_homework_ood",
        )
        if (
            res.get("route") == "out_of_scope"
            and res.get("reason") == "out_of_scope"
            and not guarded
        ):
            from archipelago.inference.ranking import rank_concepts
            q_raw = (query or "").strip()
            ranked = rank_concepts(q_raw, top_k=3)
            best_cos = float(ranked[0]["cos"]) if ranked else 0.0
            best_lex = float(ranked[0].get("lexical") or 0.0) if ranked else 0.0
            
            # Check if query has a domain signal
            has_domain_signal = _is_learning_or_domain_query(q_raw)
            if has_domain_signal:
                closest = [
                    r.get("label") or r.get("name") or r.get("id")
                    for r in ranked[:3]
                ]
                res["route"] = "low_similarity_reject"
                res["reason"] = "kill_switch_low_similarity_in_scope"
                res["scope"] = "soft"
                res["slots"] = {
                    **(res.get("slots") or {}),
                    "closest_concepts": closest,
                    "query": q_raw,
                }
                res["block_reason"] = None

        from archipelago.inference.query_classifier import classify_query_mode
        res["query_mode"] = classify_query_mode(query, routing_result=res).value
    return res

def _resolve_query_routing(query: str, history: list | None = None) -> dict:
    """Decide how to answer.

    Routes: out_of_scope | library_* | onboarding | identity | small_talk
    | graph_strong | graph_soft | general_chat | low_similarity_reject

    Order:
      1) De-grease (small-talk prefix + style noise)
      2) Intent gate (embed prototypes / LLM) — blocks implementation,
         entity trivia, OOD, meta without keyword banlists
      3) Identity / onboarding / library
      4) Embedder kill-switch (strict cosine threshold)
      5) Scope + graph pin
    """
    if not st.CONCEPTS_DATA:
        from archipelago.inference.routes_chat import init_concepts_data
        try:
            init_concepts_data()
        except Exception as e:
            print(f"Failed to auto-initialize concepts data: {e}")

    q_raw = (query or "").strip()

    library = _detect_library_intent(q_raw)
    if library:
        lib_intent = library["intent"]
        lib_route = lib_intent
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {key: value for key, value in library.items() if key != "raw"},
            "scope": "yes",
            "route": lib_route,
            "reason": lib_intent,
        }

    from archipelago.inference.demo_query_books import match_demo_query_key
    suggested_key = match_demo_query_key(q_raw)
    suggested_anchor = _SUGGESTED_QUERY_ANCHORS.get(suggested_key or "")
    if suggested_anchor:
        from archipelago.inference.intent_gate import classify_intent as classify_suggested_intent
        suggested_intent = classify_suggested_intent(q_raw)
        suggested_block = intent_to_block_reason(suggested_intent["intent"], suggested_intent["score"])
        if suggested_block:
            return {
                "anchor_id": None,
                "score": suggested_intent["score"],
                "related": [],
                "slots": {
                    "intent": suggested_intent["intent"],
                    "intent_method": suggested_intent["method"],
                    "suggested_query": suggested_key,
                },
                "scope": "no",
                "route": "out_of_scope",
                "reason": suggested_block,
            }
        return {
            "anchor_id": suggested_anchor,
            "score": 1.0,
            "related": [],
            "slots": {"suggested_query": suggested_key},
            "scope": "yes",
            "route": "graph_strong",
            "reason": "suggested_query_grounded_route",
        }

    if "my dataset" in q_raw.lower() or "my data" in q_raw.lower():
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "direct_block"},
            "scope": "no",
            "route": "out_of_scope",
            "reason": REASON_OUT_OF_SCOPE,
        }

    q, style_stripped = _strip_persona_style(q_raw)

    # Searchable portion: drop conversational lead-ins
    search_q = q
    prefixed = _SMALL_TALK_PREFIXES.sub("", q).strip()
    if prefixed:
        search_q = prefixed

    # Re-run style strip on search portion
    search_q, _ = _strip_persona_style(search_q)

    # Pure greetings short-circuit BEFORE intent/LLM (cheap + stable)
    if _is_chitchat(q_raw) and not _TECHNICAL_MARKERS.search(search_q or q_raw):
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {"intent": INTENT_SOCIAL, "intent_method": "chitchat_short_circuit"},
            "scope": "yes",
            "route": "general_chat",
            "reason": "chitchat",
        }

    # Identity short-circuit BEFORE the intent gate: "who are you" style asks
    # are self-introduction requests, never entity trivia about a person — the
    # embedder cannot tell them apart, so we route on the deterministic matcher.
    if _is_identity(q_raw) and not _TECHNICAL_MARKERS.search(search_q or q_raw):
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {"intent": INTENT_SOCIAL, "intent_method": "identity_short_circuit"},
            "scope": "yes",
            "route": "identity",
            "reason": "identity",
        }

    ranked = rank_concepts(search_q, top_k=max(st.TOP_K_RELATED, 10))
    best = ranked[0] if ranked else None
    best_cos = float(best["cos"]) if best else 0.0
    best_lex = float(best.get("lexical") or 0.0) if best else 0.0
    learning = _is_learning_intent(q)

    # Check if user is replying to a diagnostic quiz with answers
    quiz_answers = _extract_quiz_answers(q_raw)
    is_quiz_response = False
    if len(quiz_answers) >= 3:
        is_quiz_response = True
    elif history and len(quiz_answers) >= 1:
        last_asst = next((h.get("content", "") for h in reversed(history) if h.get("role") == "assistant"), "")
        if "Knowledge Assessment" in last_asst or "diagnostic question" in last_asst.lower() or "Question 1:" in last_asst:
            is_quiz_response = True

    if is_quiz_response:
        target_concept = _get_active_concept_from_history(history) or "low_rank_adaptation"
        return {
            "anchor_id": target_concept,
            "score": 1.0,
            "related": ranked,
            "slots": {
                "intent": "roadmap_quiz_eval",
                "target_concept": target_concept,
                "answers": quiz_answers,
            },
            "scope": "yes",
            "route": "roadmap_quiz_eval",
            "reason": "diagnostic_evaluation",
        }

    # Diagnostic knowledge assessment check (Context-Aware)
    if re.search(r"\b(quiz\s+me|diagnostic\s+quiz|test\s+my\s+knowledge|assess\s+my\s+knowledge|evaluate\s+my\s+knowledge)\b", q_raw, re.I):
        # 1. Check if user explicitly named a specific concept in this query
        clean_quiz_q = re.sub(
            r"\b(can\s+you\s+)?(quiz\s+me|diagnostic\s+quiz|test\s+my\s+knowledge|assess\s+my\s+knowledge|evaluate\s+my\s+knowledge)\b",
            " ", q_raw, flags=re.I
        )
        clean_quiz_q = re.sub(r"\b(on|about|for|to|prerequisites|prereqs|baseline|this|it|that|topic|concept|what\s+we\s+discussed|please)\b", " ", clean_quiz_q, flags=re.I).strip()
        target_concept = None
        if clean_quiz_q and len(clean_quiz_q) >= 3:
            specific_ranked = rank_concepts(clean_quiz_q, top_k=1)
            if specific_ranked and (float(specific_ranked[0].get("cos", 0)) >= 0.48 or float(specific_ranked[0].get("lexical", 0)) >= 0.70):
                target_concept = specific_ranked[0]["id"]

        # 2. If no explicit concept named, or query leans on context ("this", "it"), check history!
        if not target_concept and history:
            target_concept = _get_active_concept_from_history(history)

        if not target_concept:
            target_concept = best["id"] if (best and best["id"] != "knowledge_graph") else "low_rank_adaptation"

        return {
            "anchor_id": target_concept,
            "score": best_cos,
            "related": ranked,
            "slots": {"intent": "roadmap_quiz", "target_concept": target_concept},
            "scope": "yes",
            "route": "roadmap_quiz",
            "reason": "diagnostic_assessment",
        }

    # Roadmap between two concepts check (e.g. roadmap from X to Y)
    roadmap_match = re.search(r"\broadmap\s+(?:from|between)\s+(.+?)\s+(?:to|and)\s+(.+)", q_raw, re.I)
    if roadmap_match:
        from_term = roadmap_match.group(1).strip()
        to_term = roadmap_match.group(2).strip()
        from_ranked = rank_concepts(from_term, top_k=1)
        to_ranked = rank_concepts(to_term, top_k=1)
        start_id = from_ranked[0]["id"] if from_ranked else from_term.lower().replace(" ", "_")
        target_id = to_ranked[0]["id"] if to_ranked else to_term.lower().replace(" ", "_")
        return {
            "anchor_id": target_id,
            "score": 1.0,
            "related": ranked,
            "slots": {"intent": "roadmap_between", "start_id": start_id, "target_id": target_id},
            "scope": "yes",
            "route": "roadmap_between",
            "reason": "personalized_roadmap",
        }

    # Conversational memory/pronoun expansion — fires whenever the query leans
    # on a prior turn (pronouns / deictic follow-ups) and the graph shows no
    # direct surface hit of its own, not only when cosine is very low.
    if history:
        has_pronoun = bool(re.search(
            r"\b(it|this|that|them|these|its|starting|before|after|next|prereq|prerequisites|requirements|downstream|upstream|concept|topic|more|deeper|further)\b",
            q_raw, re.I
        ))
        own_surface_hit = _has_surface_concept_hit(ranked, search_q)
        needs_context = best_cos < 0.45 or (has_pronoun and not own_surface_hit)
        if needs_context and (has_pronoun or learning):
            active_concept = _get_active_concept_from_history(history)
            if active_concept and active_concept in st.CONCEPTS_DATA:
                concept_name = st.CONCEPTS_DATA[active_concept].get("label") or active_concept
                search_q = f"{search_q} {concept_name}"
                q = f"{q} {concept_name}"
                # Re-calculate routing parameters with the expanded query
                ranked = rank_concepts(search_q, top_k=max(st.TOP_K_RELATED, 10))
                best = ranked[0] if ranked else None
                best_cos = float(best["cos"]) if best else 0.0
                best_lex = float(best.get("lexical") or 0.0) if best else 0.0
                learning = _is_learning_intent(q)

    domain = _is_learning_or_domain_query(q)
    chitchat = _is_chitchat(q)
    offtopic = _is_offtopic(q)
    has_domain = _has_domain_terms(q)
    identity = _is_identity(q)
    onboarding = _is_onboarding(q)

    # Intent on degreased technical ask first (style-stripped), then raw.
    # Classifying slang-laden raw text alone made backprop→OOD / RAG theory→impl.
    intent_info = classify_intent(search_q or q)
    if intent_info["intent"] == INTENT_SOCIAL and search_q and search_q != q_raw:
        intent_info = classify_intent(search_q)
    if intent_info["intent"] == INTENT_SOCIAL and _TECHNICAL_MARKERS.search(search_q or ""):
        intent_info = classify_intent(search_q)
    # Meta / system-leak still needs the raw wording ("as an AI… token limits")
    if intent_info["intent"] not in (INTENT_META, INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA):
        raw_info = classify_intent(q_raw)
        if raw_info["intent"] in (INTENT_META, INTENT_IMPLEMENTATION, INTENT_ENTITY_TRIVIA):
            # Only adopt raw block if search path was not clear pedagogy/theory
            if intent_info["intent"] != INTENT_THEORY:
                intent_info = raw_info

    intent = intent_info["intent"]
    intent_score = float(intent_info.get("score") or 0.0)

    base = {
        "anchor_id": None,
        "score": best_cos,
        "related": ranked,
        "slots": {
            "intent": intent,
            "intent_score": intent_score,
            "intent_method": intent_info.get("method"),
        },
        "scope": "skipped",
    }
    if style_stripped:
        base["slots"]["sterile"] = True
        base["slots"]["persona_hijack"] = True

    # Suspect check for dual-pass activation
    has_suspicious_terms = bool(re.search(
        r"\b(code|script|scripts|write|generate|provide|give|draft|email|schema|tutorial|"
        r"install|setup|pseudocode|pseudo-code|dataset|dataset\b|analyze|my\s+data|my\s+dataset|"
        r"implement|implementation|create)\b",
        q_raw, re.I
    ))
    is_creative = bool(re.search(r"\b(audio|emotional|story|poem|song|fiction|novel|creative|play)\b", q_raw, re.I))
    has_theory_terms = bool(re.search(
        r"\b(matrix|matrices|attention|transformer|gradient|regression|classification|neural|probability|chain\s+rule)\b",
        q_raw, re.I
    ))
    if is_creative and has_theory_terms:
        has_suspicious_terms = False
    if intent in (INTENT_IMPLEMENTATION, INTENT_OUT_OF_DOMAIN, INTENT_ENTITY_TRIVIA, INTENT_META) or has_suspicious_terms:
        guard_input = search_q if (history and search_q and search_q != q_raw) else q_raw
        if _run_dual_pass_guard(guard_input):
            # Artifact/procedural request confirmed → implementation refusal
            # (never the generic OOS reason: the safety net must not soften it).
            if intent == INTENT_IMPLEMENTATION or re.search(
                r"\b(code|script|scripts|pseudocode|pseudo-code|function|tutorial|"
                r"install|deploy|email|draft|schema|config|commands?)\b",
                q_raw, re.I
            ):
                return {
                    "anchor_id": None,
                    "score": 1.0,
                    "related": ranked,
                    "slots": {
                        "intent": INTENT_IMPLEMENTATION,
                        "intent_method": "dual_pass_guard",
                        "closest_concepts": [
                            r.get("label") or r.get("name") or r.get("id")
                            for r in ranked[:3]
                        ],
                    },
                    "scope": "no",
                    "route": "out_of_scope",
                    "reason": REASON_IMPLEMENTATION,
                }
            else:
                return {
                    "anchor_id": None,
                    "score": 1.0,
                    "related": ranked,
                    "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "dual_pass_guard"},
                    "scope": "no",
                    "route": "out_of_scope",
                    "reason": REASON_OUT_OF_SCOPE,
                }

    # ── Intent gate hard blocks (scalable — no entity keyword lists) ──
    # Graph-grounded veto: if the library graph itself clearly covers the
    # query (alias/acronym/core match, e.g. "what is rag" vs the RAG node),
    # the tiny classifier's OOD/entity verdict is wrong — let routing continue
    # to the anchor stages. Implementation/meta blocks are never vetoed.
    block = intent_to_block_reason(intent, intent_score)
    graph_override = None
    if block == REASON_OUT_OF_SCOPE or intent == INTENT_OUT_OF_DOMAIN:
        # OOD verdicts only — entity/authority trivia stays blocked even when
        # the graph covers the mentioned concept ("PyTorch version for LoRA").
        graph_override = _graph_block_override(search_q or q, ranked)
    closest_labels = [
        r.get("label") or r.get("name") or r.get("id") for r in ranked[:3]
    ]
    # Meta blocks before identity so "system constraints" never becomes identity chat
    if block == REASON_META or intent == INTENT_META:
        return {
            **base,
            "route": "out_of_scope",
            "reason": REASON_META,
            "scope": "no",
        }
    if not library:
        if block == REASON_IMPLEMENTATION or intent == INTENT_IMPLEMENTATION:
            return {
                **base,
                "route": "out_of_scope",
                "reason": REASON_IMPLEMENTATION,
                "scope": "no",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest_labels,
                }),
            }
        if graph_override is None:
            if block == REASON_NOT_IN_CORPUS or intent == INTENT_ENTITY_TRIVIA:
                return {
                    **base,
                    "route": "out_of_scope",
                    "reason": REASON_NOT_IN_CORPUS,
                    "scope": "no",
                    "slots": _merge_slots(base["slots"], {
                        "closest_concepts": closest_labels,
                    }),
                }
            if block == REASON_OUT_OF_SCOPE or intent == INTENT_OUT_OF_DOMAIN:
                return {
                    **base,
                    "route": "out_of_scope",
                    "reason": REASON_OUT_OF_SCOPE,
                    "scope": "no",
                    "slots": _merge_slots(base["slots"], {
                        "closest_concepts": closest_labels,
                    }),
                }
        elif intent in (INTENT_OUT_OF_DOMAIN, INTENT_ENTITY_TRIVIA):
            # Continue as theory: the graph knows this topic.
            intent = INTENT_THEORY
            base["slots"]["intent"] = intent
            base["slots"]["intent_method"] = (
                f"{base['slots'].get('intent_method')}+graph_override"
            )

    # Dual-pass kill-switch: high concept cosine but intent near-OOD (e.g. film
    # "Matrix" vs math matrices). Prefer intent OOD scores when close.
    ood_score = float((intent_info.get("scores") or {}).get(INTENT_OUT_OF_DOMAIN) or 0.0)
    if (
        intent == INTENT_THEORY
        and best_cos >= 0.55
        and ood_score >= intent_score - 0.08
        and ood_score >= 0.25
    ):
        # Re-check with LLM when margin is thin
        recheck = classify_intent(q_raw, force_llm=True)
        if recheck.get("intent") == INTENT_OUT_OF_DOMAIN:
            return {
                **base,
                "route": "out_of_scope",
                "reason": REASON_OUT_OF_SCOPE,
                "scope": "no",
                "slots": _merge_slots(base["slots"], {
                    "intent": INTENT_OUT_OF_DOMAIN,
                    "intent_method": recheck.get("method"),
                    "dual_pass": True,
                }),
            }

    # 0) Identity / onboarding
    if identity and intent != INTENT_META:
        return {**base, "route": "identity", "reason": "identity", "scope": "yes"}

    if onboarding:
        return {
            **base, "route": "onboarding", "reason": "onboarding_syllabus",
            "scope": "yes", "related": ranked,
        }

    # Early fast reject for completely out-of-scope queries
    graph_evidence = _has_strong_graph_evidence(ranked)
    in_scope, scope_reason = is_aiml_in_scope(
        q_raw,
        chitchat=chitchat,
        offtopic_keyword=offtopic,
        has_domain_terms=has_domain,
        strong_anchor=False,
        best_cos=best_cos,
        best_lex=best_lex,
        force_llm=False,
        learning_intent=learning,
        graph_evidence=graph_evidence,
    )
    if not in_scope and scope_reason == "no_domain_signal_low_similarity":
        return {
            "anchor_id": None,
            "score": best_cos,
            "related": ranked,
            "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "early_fast_reject"},
            "scope": "no",
            "route": "out_of_scope",
            "reason": REASON_OUT_OF_SCOPE,
        }

    # 0.5) Library intents
    if library:
        in_scope, scope_reason = is_aiml_in_scope(
            q,
            chitchat=False,
            offtopic_keyword=offtopic,
            has_domain_terms=has_domain,
            strong_anchor=False,
            best_cos=best_cos,
            best_lex=best_lex,
            force_llm=not has_domain,
            learning_intent=learning,
            graph_evidence=graph_evidence,
        )
        if not in_scope:
            return {
                **base,
                "route": "out_of_scope",
                "reason": f"out_of_scope_library:{scope_reason}",
                "scope": "no",
            }
        lib_intent = library["intent"]
        slots = _merge_slots(base["slots"], {"limit": library.get("limit", 5)})
        return {
            **base,
            "route": lib_intent,
            "reason": lib_intent,
            "slots": slots,
            "scope": "yes",
        }

    # 1) Small talk — mixed pleasantry + technical tail
    is_small_talk, remaining = _strip_small_talk(q)
    if is_small_talk:
        has_technical_tail = bool(remaining) and bool(_TECHNICAL_MARKERS.search(remaining))
        has_learning_or_domain = (
            _is_learning_intent(remaining) or _has_domain_terms(remaining)
        )
        if has_technical_tail and not has_learning_or_domain:
            return {
                **base,
                "route": "small_talk",
                "reason": "conversational_greeting",
                "score": 1.0,
                "slots": _merge_slots(base["slots"], {
                    "technical_portion": remaining if remaining != q else "",
                }),
            }

    # 2) Pure social → free chat
    if chitchat or intent == INTENT_SOCIAL:
        # If social but search_q has domain content, fall through to graph
        if not (_TECHNICAL_MARKERS.search(search_q or "") or has_domain or learning):
            return {**base, "route": "general_chat", "reason": "chitchat"}

    # 2.5) Absurdity / external-authority sanity gate — only when the query
    # mixes graph-known concepts with foreign content tokens (Batman, sourdough,
    # carbon footprint, a researcher's opinions…). Clean theory questions have
    # no foreign tokens and never pay this LLM call. An off-topic marker plus
    # foreign tokens is decisive on its own (assist list, no LLM needed).
    foreign = _foreign_tokens(search_q or q)
    if foreign and (
        has_domain or _has_strong_graph_evidence(ranked)
        or _has_surface_concept_hit(ranked, search_q or q)
    ):
        guard_input = search_q if (history and search_q and search_q != q_raw) else q_raw
        if offtopic or _run_sanity_guard(guard_input):
            return {
                **base,
                "route": "out_of_scope",
                "reason": REASON_OUT_OF_SCOPE,
                "scope": "no",
                "slots": _merge_slots(base["slots"], {
                    "intent": INTENT_OUT_OF_DOMAIN,
                    "intent_method": "offtopic_mix" if offtopic else "sanity_guard",
                    "foreign_tokens": foreign[:6],
                    "closest_concepts": [
                        r.get("label") or r.get("name") or r.get("id")
                        for r in ranked[:3]
                    ],
                }),
            }

    strong_id, strong_score = find_anchor_concept(search_q)
    strong_anchor = bool(strong_id)

    # 3) Embedder kill-switch — strict cosine gate (default 0.75 with embeddings)
    threshold = float(getattr(st, "KILL_SWITCH_THRESHOLD", 0.75)) if st.use_embeddings else 0.50
    has_strong_surface_hit = best_lex >= 0.70
    if best_cos < threshold and not has_strong_surface_hit:
        force_llm = learning and not has_domain and not strong_anchor and not domain
        in_scope, scope_reason = is_aiml_in_scope(
            q,
            chitchat=False,
            offtopic_keyword=offtopic,
            has_domain_terms=has_domain,
            strong_anchor=strong_anchor,
            best_cos=best_cos,
            best_lex=best_lex,
            force_llm=force_llm,
            learning_intent=learning,
            graph_evidence=graph_evidence,
        )
        if in_scope:
            closest = [
                r.get("label") or r.get("name") or r.get("id")
                for r in ranked[:3]
            ]
            return {
                **base,
                "route": "low_similarity_reject",
                "reason": "kill_switch_low_similarity_in_scope",
                "score": best_cos,
                "scope": "yes",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest, "query": q,
                }),
            }
        return {
            **base,
            "route": "out_of_scope",
            "reason": f"kill_switch_low_similarity_out_of_scope:{scope_reason}",
            "scope": "no",
        }

    # 4) Hybrid scope gate
    force_llm = learning and not has_domain and not strong_anchor and not domain
    in_scope, scope_reason = is_aiml_in_scope(
        q,
        chitchat=False,
        offtopic_keyword=offtopic,
        has_domain_terms=has_domain,
        strong_anchor=strong_anchor,
        best_cos=best_cos,
        best_lex=best_lex,
        force_llm=force_llm,
        learning_intent=learning,
        graph_evidence=graph_evidence,
    )
    if not in_scope:
        if learning and not offtopic:
            closest = [
                r.get("label") or r.get("name") or r.get("id")
                for r in ranked[:3]
            ]
            return {
                **base,
                "route": "low_similarity_reject",
                "reason": "not_indexed_learning_topic",
                "score": best_cos,
                "scope": "soft",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest, "query": q,
                }),
            }
        return {
            **base,
            "route": "out_of_scope",
            "reason": f"out_of_scope:{scope_reason}",
            "scope": "no",
        }

    # 5) Graph strong / soft
    target_route = None
    target_anchor = None
    target_score = 0.0
    target_reason = ""

    if strong_id:
        target_route = "graph_strong"
        target_anchor = strong_id
        target_score = strong_score
        target_reason = "strong_embed_or_lexical"
    elif domain:
        soft = _select_soft_anchor(ranked, search_q) or best
        target_route = "graph_soft"
        target_anchor = soft["id"] if soft else None
        target_score = float(soft.get("cos") or 0.0) if soft else 0.0
        target_reason = "domain_soft_match"
    elif best and best_cos >= st.DOMAIN_SOFT_THRESHOLD + 0.12 and best_lex >= 0.35:
        soft = _select_soft_anchor(ranked, search_q) or best
        target_route = "graph_soft"
        target_anchor = soft["id"] if soft else None
        target_score = float(soft.get("cos") or 0.0) if soft else best_cos
        target_reason = "soft_high_confidence"

    if target_route:
        max_cos = max(
            (float(r.get("cos") or 0.0) for r in ranked), default=0.0
        )
        best_alias = float((best or {}).get("alias_boost") or 0.0)
        best_blended = float((best or {}).get("blended") or 0.0)
        surface_hit = _has_surface_concept_hit(ranked, q)

        hard_miss = (
            st.use_embeddings
            and target_route == "graph_soft"
            and max_cos < st.REJECT_SIMILARITY_THRESHOLD
            and best_lex < 0.40
            and best_alias < 0.12
            and not surface_hit
        )
        if hard_miss:
            closest = [
                r.get("label") or r.get("name") or r.get("id")
                for r in ranked[:3]
            ]
            return {
                **base,
                "route": "low_similarity_reject",
                "score": max_cos,
                "reason": "low_similarity_reject",
                "scope": "yes",
                "slots": _merge_slots(base["slots"], {
                    "closest_concepts": closest, "query": q,
                }),
            }

        if (
            st.use_embeddings
            and target_route == "graph_soft"
            and max_cos < st.REJECT_SIMILARITY_THRESHOLD
        ):
            return {
                **base,
                "route": "graph_soft",
                "anchor_id": target_anchor,
                "score": max_cos,
                "reason": "partial_coverage_low_cos",
                "scope": "yes",
                "slots": _merge_slots(base["slots"], {
                    "partial": True,
                    "closest_concepts": [
                        r.get("label") or r.get("name") or r.get("id")
                        for r in ranked[:3]
                    ],
                }),
            }

        out_score = target_score
        if target_route == "graph_soft" and best_blended > out_score:
            out_score = min(1.0, best_blended * 0.5 + out_score * 0.5)

        return {
            **base,
            "route": target_route,
            "anchor_id": target_anchor,
            "score": out_score,
            "reason": target_reason,
            "scope": "yes",
        }

    if learning:
        closest = [
            r.get("label") or r.get("name") or r.get("id")
            for r in ranked[:3]
        ]
        return {
            **base,
            "route": "low_similarity_reject",
            "score": best_cos,
            "reason": "not_indexed_low_signal",
            "scope": "yes",
            "slots": _merge_slots(base["slots"], {
                "closest_concepts": closest, "query": q,
            }),
        }

    return {
        **base,
        "route": "general_chat",
        "reason": "low_similarity_open_chat",
        "scope": "yes",
    }


def _detect_library_intent(query: str) -> dict | None:
    """Detect all library, book, journal, inventory, hours, and holdings intents."""
    q = (query or "").strip()
    ql = q.lower()
    if not ql:
        return None

    from archipelago.inference.library_credentials import detect_credentials_query

    catalog_stats = (
        ("subject" in ql and any(term in ql for term in ("highest", "leaderboard", "title count")))
        or ("journal" in ql and any(term in ql for term in ("title count", "issue count", "total issues")))
        or ("keyword" in ql and any(term in ql for term in ("catalog", "titles", "search")))
        or ("zero" in ql and "copies" in ql)
    )
    if catalog_stats:
        return {"intent": "library_catalog_stats", "raw": q}

    journal_status = re.search(r"\b(journals?|periodicals?|magazines?)\b", ql) and re.search(r"\b(late|issues?|subscription|status|latest|available)\b", ql)
    if journal_status:
        return {"intent": "library_journal_status", "raw": q}

    circulation_request = re.search(r"\b(borrow|check\s*out|checkout|reserve|physical\s+cop(?:y|ies)|copies?\s+of)\b|\bphysical\s+book\b", ql)
    if circulation_request:
        return {"intent": "library_resource_lookup", "raw": q}

    if re.search(r"\bworking\s+hours\b|\boperating\s+schedule\b|\blibrary\s+(?:hours?|times?|timings?|schedule)\b|\b(?:hours?|times?|timings?)\s+(?:of|for)\s+(?:the\s+)?library\b|\bwhen\s+is\s+(?:the\s+)?library\s+open\b|\btell\s+timing\s+of\s+library\b", ql):
        return {"intent": "library_hours", "raw": q}

    credential_request = detect_credentials_query(q)
    if credential_request:
        return {
            "intent": "library_resources",
            "resource_key": credential_request.get("resource_key", ""),
            "raw": q,
            "slots": {**credential_request.get("slots", {}), "resource_access": True},
        }

    if re.search(
        r"\b(e[- ]?resources?|e[- ]?resource\s+portals?|library\s+portals?|"
        r"research\s+databases?|digital\s+library\s+portals?|pearson\s+e[- ]?library|"
        r"sciencedirect|science\s+direct|ieee\s*xplore|springer(?:\s+link)?)\b",
        ql,
    ):
        return {"intent": "library_resources", "raw": q, "resource_access": True}

    # 1. Book Details / Specific Book Summary
    book_detail_patterns = (
        r"\b(tell\s+me\s+about\s+(?:this\s+|the\s+)?(?:book|paper|textbook))\b",
        r"\b(details?\s+(?:of|for|about)\s+(?:this\s+|the\s+)?(?:book|paper|textbook))\b",
        r"\b(what\s+is\s+(?:this|the)?\s*(?:book|paper|textbook))\b",
        r"\b(about\s+this\s+book:?)\b",
        r"\b(book\s+details:?)\b",
        r"\b(details\s+(?:on|about)\s+(?:book|paper|textbook))\b",
    )
    if any(re.search(p, ql) for p in book_detail_patterns):
        return {"intent": "library_book_details", "raw": q}

    # 2. Journal & Inventory & Holdings
    holdings_patterns = (
        r"\b(journal|journals|inventory|holdings|copies|accession|periodicals?)\b",
        r"\b(how\s+many\s+copies|available\s+copies|total\s+copies|stock|shelf\s+location)\b",
        r"\b(show\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?:book|journal|library)?\s*(?:inventory|holdings|details|status|records))\b",
        r"\b(what\s+(?:books|journals|holdings)\s+(?:do\s+you\s+have|are\s+available|exist))\b",
        r"\b(is\s+.+\s+available\s+in\s+(?:the\s+)?library)\b",
        r"\b(library\s+catalog|library\s+database|library\s+records)\b",
    )
    if any(re.search(p, ql) for p in holdings_patterns):
        return {"intent": "library_holdings", "raw": q}

    # 3. Hours & Services
    hours_patterns = (
        r"\b(library\s+hours|hours\s+of\s+library|when\s+is\s+(?:the\s+)?library\s+open|library\s+timings?|library\s+schedule)\b",
        r"\b(is\s+(?:the\s+)?library\s+open\b)",
        r"\b(open\s+on\s+(?:saturdays?|sundays?|weekends?))\b",
    )
    if any(re.search(p, ql) for p in hours_patterns):
        return {"intent": "library_hours", "raw": q}

    # 4. Chapter lookup (must run before generic book-recommendation patterns)
    concept_verbs = r"\b(discuss(?:es|ed)?|mention(?:s|ed)?|contain(?:s|ed)?|cover(?:s|ed)?)\b"
    if (
        re.search(r"\b(which|what)\s+(chapters?|sections?)\b", ql)
        and (re.search(concept_verbs, ql) or re.search(r"\babout\b", ql))
    ):
        return {"intent": "library_chapter_lookup", "raw": q}

    if (
        re.search(r"\b(chapters?|sections?)\s+(of|in)\b", ql)
        and re.search(concept_verbs, ql)
    ):
        return {"intent": "library_chapter_lookup", "raw": q}

    if re.search(
        r"\bwhere\s+(in|does)\b", ql
    ) and re.search(r"\b(talk(?:s|ed)?|discuss(?:es|ed)?|mention(?:s|ed)?|cover(?:s|ed)?)\b", ql):
        return {"intent": "library_chapter_lookup", "raw": q}

    if re.search(
        r"\b("
        r"chapters?\s+of|chapters?\s+in|sections?\s+of|sections?\s+in|"
        r"table\s+of\s+contents|list\s+chapters|show\s+chapters|"
        r"what\s+are\s+the\s+chapters|what\s+are\s+the\s+sections"
        r")\b",
        ql,
    ):
        return {"intent": "library_chapters", "raw": q}

    # 5. Book recommendations / suggested readings
    book_patterns = (
        r"\b(suggest|recommend)\b.+\b(books?|papers?|readings?|textbooks?)\b",
        r"\b(top|best)\s+\d*\s*(books?|papers?|readings?)\b",
        r"\b(books?|papers?)\s+(for|on|about|regarding)\b",
        r"\bwhat\s+(books?|papers?)\s+(should|can|to|on|for|about)\b",
        r"\b(reading\s+list|bibliography)\b.+\b(for|on|about)\b",
        r"\b(resources?|readings?|material)\s+(for|on|about)\b",
        r"\bwhat\s+should\s+i\s+read\b",
        r"\b(suggest|recommend)\b.+\b(reading|resources?|materials?)\b",
    )
    if any(re.search(p, ql) for p in book_patterns):
        # Recommendation cards cap at 4 (chat UI shelf grid) — test-pinned.
        limit = 4
        m = re.search(r"\btop\s+(\d+)\b", ql) or re.search(r"\b(\d+)\s+(books?|papers?)\b", ql)
        if m:
            try:
                limit = max(1, min(4, int(m.group(1))))
            except ValueError:
                limit = 4
        # The topic must sit inside the library's shelf ("suggest books about
        # stars" is out of scope even though the intent is book-shaped).
        if not _is_learning_or_domain_query(q):
            return None
        from archipelago.inference.ranking_seeds import detect_subject_key
        subject = detect_subject_key(q)
        return {
            "intent": "library_books",
            "raw": q,
            "limit": limit,
            **({"seed_subject": subject} if subject else {}),
        }

    return None


def parse_multi_topic_query(query: str) -> list[str]:
    """Parse a compound query into multiple topic phrases or return single topic.

    Handles '+', 'vs', 'versus', 'differ from', commas, and 'and' conjunctions,
    while treating subordinate explanatory clauses (e.g. 'and how it reduces...')
    as a single unified topic.
    """
    if not query or not query.strip():
        return []

    q = query.strip()
    # Strip common leading question / imperative phrasing
    prefix_match = re.match(
        r"^(?:explain|compare|describe|analyze|discuss|what\s+(?:is|are)|how\s+does|how\s+do)\s+",
        q,
        re.I,
    )
    cleaned = q[prefix_match.end():] if prefix_match else q
    cleaned = cleaned.rstrip("?.! ")

    # Check for dependent explanatory clauses with 'and' (e.g. 'and how', 'and why', 'and what', 'and its')
    # If the conjunction is explanatory, do not split on 'and'
    if re.search(r"\band\s+(?:how|why|what|where|when|which|who|its|their|the\s+way)\b", cleaned, re.I):
        if not re.search(r"\+|\bvs\.?\b|\bversus\b", cleaned, re.I):
            return [cleaned]

    # Delimiters: '+', 'vs', 'versus', 'differ from', or ',' / 'and'
    if "+" in cleaned:
        parts = [p.strip() for p in cleaned.split("+") if p.strip()]
        return parts

    vs_match = re.split(r"\s+(?:vs\.?|versus|differ(?:s)?\s+from)\s+", cleaned, flags=re.I)
    if len(vs_match) > 1:
        return [p.strip() for p in vs_match if p.strip()]

    # Otherwise split on commas and conjunction 'and'
    split_parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", cleaned, flags=re.I)
    parts = [p.strip() for p in split_parts if p.strip()]
    if parts:
        return parts[:4]
    return [cleaned]
