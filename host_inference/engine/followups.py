"""Contextual follow-up recommendations derived strictly from verified evidence.

One concern: attach query-specific, domain-consistent, non-repetitive follow-up
questions to chat metadata (3-5 for anchored academic answers, up to 3 for
unanchored fallback answers, and 0 when no relevant grounded follow-up exists).
Never emits cross-domain noise, misleading prerequisite directions, or
source-specific prompts for unavailable/metadata-only documents.
"""

from __future__ import annotations

import re
from typing import Any

from .access_profile import is_open_access_profile
from .conversational import strip_prior_context
from .corpus_titles import clean_bibliographic_title
from .evidence_selection import infer_doc_domains, infer_text_domains
from .suggestions import NON_AI_FALLBACK_SUGGESTION_COUNT, sample_fallback_questions

MAX_FOLLOW_UP_QUESTIONS = 5
MAX_FALLBACK_FOLLOW_UPS = 3
MAX_QUESTION_CHARS = 96
MAX_TITLE_SNIPPET_CHARS = 44
MIN_FALLBACK_NODE_LABEL_LEN = 3
MAX_FALLBACK_NODE_LABEL_LEN = 60
MIN_PASSAGE_SNIPPET_LEN = 20
SUMMARY_PREVIEW_CHARS = 300

DOMAIN_SECURITY = "SECURITY"
DOMAIN_AUTOMATA = "AUTOMATA"
DOMAIN_COMPILERS = "COMPILERS"
DOMAIN_SE = "SE"
DOMAIN_COA = "COA"
DOMAIN_PROBABILITY = "PROBABILITY"
DOMAIN_OS = "OS"
DOMAIN_DB = "DB"
DOMAIN_DSA = "DSA"
DOMAIN_NETWORKS = "NETWORKS"
DOMAIN_ML_AI = "ML_AI"
DOMAIN_MATH = "MATH"

_BLOCKED_ROUTES = frozenset({"EMPTY", "PERSONA_LOCK", "CODE_TRAP"})
_NON_AI_FALLBACK_ROUTES = frozenset(
    {
        "GREETING", "CAPABILITY_INQUIRY", "GUARDRAIL_INTERCEPT",
        "OUT_OF_SCOPE", "DISCONNECTED", "CURRICULUM_UNINDEXED", "RESEARCH_UNVERIFIED",
    }
)
_UNSUPPORTED_REASONS = frozenset(
    {
        "cosine_below_0.75", "curriculum_not_indexed", "research_not_indexed",
        "both_missing", "unsupported_intent", "no_verified_concept_match",
        "out_of_scope", "corpus_coverage_gap", "academic_general_not_indexed",
    }
)
_NOISE_FOLLOWUP_CIDS = frozenset(
    {"fast", "memory_efficient", "data", "equation_only", "table_only", "figure_only"}
)
_NON_VERIFIED_SOURCE_KINDS = frozenset({"metadata_only_record", "unavailable_document"})
_OPEN_ACCESS_DOC_MARKERS = ("papers/", "textbooks/", "ostep", "deisenroth", ".pdf")

# Known inverted or spurious pedagogical pairs that must never appear in follow-ups.
_BLOCKED_DIRECTED_EDGES: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("dpo", "reinforcement_learning", "unlocks"),
        ("direct_preference_optimization", "reinforcement_learning", "unlocks"),
        ("dpo", "rl", "unlocks"),
        ("dpo", "reinforcement_learning", "prerequisites"),
        ("direct_preference_optimization", "reinforcement_learning", "prerequisites"),
        ("maximum_likelihood_estimation", "neural_network", "prerequisites"),
        ("mle", "neural_network", "prerequisites"),
        ("attention_mechanism", "neural_network", "unlocks"),
        ("data_link_layer", "bit_transmission", "unlocks"),
    }
)
_BLOCKED_UNDIRECTED_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"dfa", "autonomous_system"}),
        frozenset({"deterministic_finite_automaton", "autonomous_system"}),
        frozenset({"probability", "inheritance_hierarchy"}),
        frozenset({"pca", "web_traffic"}),
        frozenset({"principal_component_analysis", "web_traffic"}),
        frozenset({"tcp", "constitutional_principle"}),
    }
)
_INTERDISCIPLINARY_FOLLOWUP_BRIDGES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"paging", "paged_attention"}),
        frozenset({"paging", "vllm"}),
        frozenset({"virtual_memory", "paged_attention"}),
        frozenset({"priority_queue_mechanics", "heuristic_search"}),
    }
)

_EXTENDED_DOMAIN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        DOMAIN_SECURITY,
        re.compile(
            r"\b(?:rsa|aes|des|diffie[-\s]?hellman|public[-\s]?key|asymmetric\s+crypt|"
            r"symmetric\s+crypt|cryptograph(?:y|ic)|encryption|decryption|\btls\b|\bssl\b|"
            r"https\s+handshake|tls\s+handshake|digital\s+signature|x\.?509|certificate\s+authority|"
            r"\bnids\b|intrusion\s+detection|firewall|hash\s+function|\bsha[-\s]?\d+\b|"
            r"\bhmac\b|cipher|euler\s+totient|modular\s+exponentiation|information\s+security|"
            r"network\s+security)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_AUTOMATA,
        re.compile(
            r"\b(?:pumping\s+lemma|regular\s+languages?|regular\s+expressions?|\bdfa\b|\bnfa\b|"
            r"finite\s+automat(?:a|on)|context[-\s]?free\s+grammars?|\bcfg\b|\bpda\b|"
            r"pushdown\s+automat(?:a|on)|turing\s+machines?|decidability|undecidable|"
            r"halting\s+problem|chomsky\s+hierarchy|formal\s+languages?|automata\s+theory)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_COMPILERS,
        re.compile(
            r"\b(?:compilers?|lexical\s+analysis|lexers?|scanners?|syntax\s+analysis|"
            r"parsers?|\blalr\b|lr\([01]\)|ll\([01]\)|bottom[-\s]?up\s+parsing|"
            r"top[-\s]?down\s+parsing|shift[-\s]?reduce|abstract\s+syntax\s+tree|\bast\b|"
            r"semantic\s+analysis|symbol\s+table|intermediate\s+representation|"
            r"three[-\s]?address\s+code|register\s+allocation|code\s+generation)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_SE,
        re.compile(
            r"\b(?:software\s+engineering|\bsdlc\b|agile\s+methodology|scrum|waterfall\s+model|"
            r"requirements\s+engineering|\buml\b|design\s+patterns?|solid\s+principles?|"
            r"unit\s+testing|integration\s+testing|ci/cd|refactoring|technical\s+debt|"
            r"coupling\s+and\s+cohesion|software\s+architecture|microservices|devops)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_COA,
        re.compile(
            r"\b(?:computer\s+architecture|computer\s+organization|cpu\s+pipelin(?:e|ing)|"
            r"pipelining|pipeline\s+hazards?|data\s+hazards?|control\s+hazards?|"
            r"structural\s+hazards?|branch\s+prediction|cache\s+coherence|cache\s+hierarchy|"
            r"l1\s+cache|l2\s+cache|\bisa\b|\brisc\b|\bcisc\b|\balu\b|instruction\s+cycle|"
            r"superscalar|out[-\s]?of[-\s]?order\s+execution|tomasulo|register\s+file)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_PROBABILITY,
        re.compile(
            r"\b(?:probability|statistics|bayes(?:'s)?\s+theorem|bayesian|"
            r"maximum\s+likelihood|\bmle\b|kl\s+divergence|kullback[-\s]?leibler|"
            r"variational\s+inference|gaussian\s+distribution|normal\s+distribution|"
            r"random\s+variables?|conditional\s+probability|expectation|variance|covariance|"
            r"posterior\s+distribution|prior\s+distribution)\b",
            re.I,
        ),
    ),
)

_COMPATIBLE_DOMAIN_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({DOMAIN_MATH, DOMAIN_PROBABILITY}),
        frozenset({DOMAIN_MATH, DOMAIN_ML_AI}),
        frozenset({DOMAIN_PROBABILITY, DOMAIN_ML_AI}),
        frozenset({DOMAIN_AUTOMATA, DOMAIN_COMPILERS}),
        frozenset({DOMAIN_OS, DOMAIN_COA}),
        frozenset({DOMAIN_SECURITY, DOMAIN_NETWORKS}),
    }
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _infer_followup_domains(text: str) -> set[str]:
    """Infer coarse academic domains using both base and D14 extended taxonomies."""
    raw = text or ""
    if not raw.strip():
        return set()
    found = set(infer_text_domains(raw))
    for domain, pattern in _EXTENDED_DOMAIN_PATTERNS:
        if pattern.search(raw):
            found.add(domain)
    return found


def _domains_are_strictly_compatible(anchor_doms: set[str], target_doms: set[str]) -> bool:
    """Require strict domain consistency; reject unlabeled targets when anchor has a domain."""
    if not anchor_doms:
        return bool(target_doms)
    if not target_doms:
        return False
    if anchor_doms & target_doms:
        return True
    return any(
        frozenset({a_dom, t_dom}) in _COMPATIBLE_DOMAIN_PAIRS
        for a_dom in anchor_doms
        for t_dom in target_doms
    )


def _node_domains(graph: Any, cid: str) -> set[str]:
    node = (getattr(graph, "nodes", None) or {}).get(cid) or {}
    label = str(node.get("label") or node.get("name") or cid)
    summary = str(node.get("summary") or "")
    base = set(graph.node_domains(cid)) if hasattr(graph, "node_domains") else set()
    ext = _infer_followup_domains(f"{cid.replace('_', ' ')} {label} {summary[:SUMMARY_PREVIEW_CHARS]}")
    return base | ext


def _is_blocked_pedagogical_edge(anchor_cid: str, neighbor_cid: str, group_key: str) -> bool:
    a_low = anchor_cid.strip().lower()
    n_low = neighbor_cid.strip().lower()
    if frozenset({a_low, n_low}) in _BLOCKED_UNDIRECTED_PAIRS:
        return True
    return (a_low, n_low, group_key) in _BLOCKED_DIRECTED_EDGES


def _neighbor_is_domain_consistent(
    graph: Any,
    anchor_cid: str,
    neighbor_cid: str,
    *,
    group_key: str = "",
    query_domains: set[str] | None = None,
) -> bool:
    """Reject noise unigrams, blocked pedagogical pairs, and cross-domain neighbors."""
    if neighbor_cid in _NOISE_FOLLOWUP_CIDS:
        return False
    if group_key and _is_blocked_pedagogical_edge(anchor_cid, neighbor_cid, group_key):
        return False
    if frozenset({anchor_cid, neighbor_cid}) in _INTERDISCIPLINARY_FOLLOWUP_BRIDGES:
        return True
    anchor_doms = _node_domains(graph, anchor_cid) | set(query_domains or ())
    neighbor_doms = _node_domains(graph, neighbor_cid)
    return _domains_are_strictly_compatible(anchor_doms, neighbor_doms)


def _citation_has_verified_full_text(cite: dict[str, Any]) -> bool:
    """Gate source-specific follow-ups strictly on verified full-text document support."""
    if cite.get("withdrawn") or cite.get("metadata_only"):
        return False
    if cite.get("evidence_backed") is False or cite.get("pdf_available") is False:
        return False
    source_kind = str(cite.get("source_kind") or "").strip().lower()
    if source_kind in _NON_VERIFIED_SOURCE_KINDS:
        return False
    if source_kind == "institutional_licensed" and is_open_access_profile():
        return False
    if not str(cite.get("doc_id") or cite.get("document_id") or "").strip():
        return False
    if source_kind == "verified_full_text_passage":
        return True
    passage = str(cite.get("text_passage") or cite.get("passage") or cite.get("snippet") or "").strip()
    return len(passage) >= MIN_PASSAGE_SNIPPET_LEN


def _citation_is_domain_consistent(
    graph: Any,
    anchor_cid: str,
    anchor_label: str,
    cite: dict[str, Any],
    *,
    query_domains: set[str] | None = None,
) -> bool:
    """Ensure citation-based follow-ups only reference verified, domain-consistent sources."""
    if not _citation_has_verified_full_text(cite):
        return False
    doc_id = str(cite.get("doc_id") or "").strip()
    raw_title = str(cite.get("doc_title") or cite.get("title") or "").strip()
    if not doc_id and not raw_title:
        return False
    anchor_doms = (
        _node_domains(graph, anchor_cid)
        | _infer_followup_domains(f"{anchor_cid.replace('_', ' ')} {anchor_label}")
        | set(query_domains or ())
    )
    doc_text = f"{raw_title} {str(cite.get('text_passage') or '')[:SUMMARY_PREVIEW_CHARS]}"
    doc_doms = infer_doc_domains(doc_id or raw_title, str(cite.get("concept_id") or ""), doc_text)
    return _domains_are_strictly_compatible(anchor_doms, doc_doms | _infer_followup_domains(doc_text))


def _truncate_title(title: str) -> str:
    clean = title.split("(", 1)[0].split("—", 1)[0].strip()
    if len(clean) <= MAX_TITLE_SNIPPET_CHARS:
        return clean
    return clean[: MAX_TITLE_SNIPPET_CHARS - 1].rstrip() + "…"


def _valid_concept_label(graph: Any, node_dict: Any) -> tuple[str, str] | None:
    """Return ``(cid, label)`` only when ``node_dict`` resolves to an indexed graph node."""
    if not isinstance(node_dict, dict):
        return None
    cid = str(node_dict.get("id") or "").strip()
    nodes = getattr(graph, "nodes", None) or {}
    if not cid or cid not in nodes:
        return None
    label = str(nodes[cid].get("label") or nodes[cid].get("name") or cid).strip()
    return (cid, label) if label else None


def _node_has_supported_sources(node: dict[str, Any], *, open_only: bool) -> bool:
    label = str(node.get("label") or node.get("name") or "").strip()
    if len(label) < MIN_FALLBACK_NODE_LABEL_LEN or len(label) > MAX_FALLBACK_NODE_LABEL_LEN:
        return False
    sources = node.get("sources") or []
    if not sources:
        return False
    if not open_only:
        return True
    return any(
        isinstance(src, dict)
        and any(m in str(src.get("doc_id") or "").lower() for m in _OPEN_ACCESS_DOC_MARKERS)
        and not str(src.get("doc_id") or "").lower().startswith("upload_")
        for src in sources
    )


def _domain_filtered_fallback_questions(
    graph: Any,
    clean_query: str,
    query_domains: set[str],
    *,
    max_count: int = MAX_FALLBACK_FOLLOW_UPS,
) -> list[str]:
    """Return up to ``max_count`` domain-consistent follow-ups, or ``[]`` if none apply."""
    nodes = getattr(graph, "nodes", None) or {}
    if not nodes or not query_domains:
        return []

    open_only = is_open_access_profile()
    query_tokens = set(_norm(clean_query).split())
    norm_query = _norm(clean_query)
    scored: list[tuple[int, int, str, str]] = []

    for cid, node in nodes.items():
        if not isinstance(node, dict) or cid in _NOISE_FOLLOWUP_CIDS:
            continue
        if not _node_has_supported_sources(node, open_only=open_only):
            continue
        if not (_node_domains(graph, cid) & query_domains):
            continue
        label = str(node.get("label") or node.get("name") or cid).strip()
        overlap = len(query_tokens & set(_norm(label).split()))
        weight = int(node.get("source_count") or len(node.get("sources") or []))
        scored.append((overlap, weight, label.lower(), label))

    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    templates = (
        "Explain {label} and its core mechanics.",
        "What are the prerequisites for {label}?",
        "Walk through a concrete example of {label}.",
    )
    out: list[str] = []
    seen: set[str] = {norm_query}
    for idx, (_ov, _w, _low, label) in enumerate(scored):
        if len(out) >= max_count:
            break
        candidate = templates[idx % len(templates)].format(label=label)
        if len(candidate) > MAX_QUESTION_CHARS:
            candidate = f"Explain {label}"
        key = _norm(candidate)
        if key and key not in seen and len(candidate) <= MAX_QUESTION_CHARS:
            seen.add(key)
            out.append(candidate)
    return out


def _first_valid_neighbor(
    graph: Any, payload: dict[str, Any], anchor_cid: str, group_key: str,
    query_domains: set[str], used_cids: set[str],
) -> tuple[str, str] | None:
    for item in payload.get(group_key) or []:
        pair = _valid_concept_label(graph, item)
        if pair and pair[0] != anchor_cid and pair[0] not in used_cids and _neighbor_is_domain_consistent(
            graph, anchor_cid, pair[0], group_key=group_key, query_domains=query_domains
        ):
            return pair
    return None


def build_follow_up_questions(
    graph: Any, payload: dict[str, Any], query: str, route: str, *, reason: str = "",
) -> list[str]:
    """Return 0-5 query-specific, domain-consistent, non-repetitive follow-up questions."""
    if route in _BLOCKED_ROUTES or (
        route == "GUARDRAIL_INTERCEPT" and reason == "security_abuse_guardrail"
    ):
        return []

    clean_query = strip_prior_context(query)
    query_domains = _infer_followup_domains(clean_query)
    is_unanchored_fallback = (
        route in _NON_AI_FALLBACK_ROUTES
        or reason in _UNSUPPORTED_REASONS
        or (route == "GENERAL_EXPLANATION" and not payload.get("anchor_concept"))
    )

    if is_unanchored_fallback:
        if query_domains:
            return _domain_filtered_fallback_questions(
                graph, clean_query, query_domains, max_count=MAX_FALLBACK_FOLLOW_UPS
            )
        return sample_fallback_questions(graph, count=NON_AI_FALLBACK_SUGGESTION_COUNT)

    norm_query = _norm(clean_query)
    suggestions: list[str] = []
    seen: set[str] = {norm_query}
    used_neighbor_cids: set[str] = set()

    def _push(candidate: str) -> None:
        text = candidate.strip()
        if not text or len(text) > MAX_QUESTION_CHARS:
            return
        key = _norm(text)
        if not key or key in seen or len(suggestions) >= MAX_FOLLOW_UP_QUESTIONS:
            return
        seen.add(key)
        suggestions.append(text)

    anchor_pair = _valid_concept_label(graph, payload.get("anchor_concept"))
    if anchor_pair is not None:
        anchor_cid, anchor_label = anchor_pair
        if anchor_cid in _NOISE_FOLLOWUP_CIDS:
            return (
                _domain_filtered_fallback_questions(
                    graph, clean_query, query_domains, max_count=MAX_FALLBACK_FOLLOW_UPS
                )
                if query_domains
                else sample_fallback_questions(graph, count=NON_AI_FALLBACK_SUGGESTION_COUNT)
            )

        for group_key, template in (
            ("prerequisites", "How does {label} connect to {anchor}?"),
            ("unlocks", "Explore next concept: {label}"),
            ("related_concepts", "Compare {anchor} and {label}"),
        ):
            pair = _first_valid_neighbor(
                graph, payload, anchor_cid, group_key, query_domains, used_neighbor_cids
            )
            if pair is not None:
                used_neighbor_cids.add(pair[0])
                _push(template.format(label=pair[1], anchor=anchor_label))

        for cite in payload.get("citations") or []:
            if not isinstance(cite, dict) or not _citation_is_domain_consistent(
                graph, anchor_cid, anchor_label, cite, query_domains=query_domains
            ):
                continue
            doc_id = str(cite.get("doc_id") or "").strip()
            raw_title = str(cite.get("doc_title") or cite.get("title") or "").strip()
            short_title = _truncate_title(clean_bibliographic_title(doc_id, raw_title))
            if short_title:
                _push(f"What does {short_title} say about {anchor_label}?")
                break

        if "example" not in norm_query:
            _push(f"Walk through a concrete example of {anchor_label}")
        if "quiz" not in norm_query:
            _push(f"Quiz me on {anchor_label}")

        for group_key, prefix in (
            ("prerequisites", "Review foundational concept: "),
            ("unlocks", "Explain "),
            ("related_concepts", "Explain "),
        ):
            for neighbor in payload.get(group_key) or []:
                pair = _valid_concept_label(graph, neighbor)
                if (
                    pair
                    and pair[0] != anchor_cid
                    and pair[0] not in used_neighbor_cids
                    and _neighbor_is_domain_consistent(
                        graph, anchor_cid, pair[0], group_key=group_key, query_domains=query_domains
                    )
                ):
                    used_neighbor_cids.add(pair[0])
                    _push(f"{prefix}{pair[1]}")

    return suggestions[:MAX_FOLLOW_UP_QUESTIONS]


__all__ = [
    "MAX_FALLBACK_FOLLOW_UPS",
    "MAX_FOLLOW_UP_QUESTIONS",
    "build_follow_up_questions",
]
