"""General-purpose scholarly query intent & multi-stage semantic relevance evaluation.

Replaces bag-of-words eligibility with phrase/proximity disambiguation, sentence-level
TF-cosine similarity, research-field compatibility, and evidence-backed classification.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from archipelago.scholarly.discovery.provider_selector import (
    DOMAIN_PROFILES,
    classify_domain,
    classify_domain_candidates,
)

RULE_VERSION = "archipelago.relevance.v2"

QUERY_MODIFIERS_RE = re.compile(
    r"\b(latest|recent|newest|papers|studies|research|foundational|seminal|classic|survey|review)\b",
    re.IGNORECASE,
)
FOUNDATIONAL_RE = re.compile(r"\b(foundational|seminal|classic|highly cited|landmark)\b", re.IGNORECASE)
RECENT_RE = re.compile(r"\b(latest|recent|newest|2025|2026)\b", re.IGNORECASE)
STOPWORDS = frozenset(
    {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "using", "via", "with"}
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Common CS/AI acronym expansions (only used as supplemental aliases, never replacing the phrase)
CONTROLLED_ALIASES: dict[str, tuple[str, ...]] = {
    "graph neural networks": ("gnn", "graph convolutional", "graph attention", "message passing neural"),
    "retrieval augmented generation": ("rag", "retrieval-augmented generation", "dense passage retrieval"),
    "liquid neural networks": ("liquid time-constant", "liquid time constant", "closed-form continuous", "tau-liquid"),
    "diffusion models": ("denoising diffusion", "latent diffusion", "score-based generative", "ddpm"),
    "small language models": ("slm", "compact language model", "tiny language model", "sub-billion language model"),
    "continual learning": ("lifelong learning", "catastrophic forgetting"),
    "optical character recognition": ("ocr", "scene text recognition", "document text recognition"),
    "speech recognition": ("asr", "automatic speech recognition"),
    "state space model": ("state-space model", "structured state space", "mamba", "s4", "selective state space"),
    "space state model": ("state-space model", "state space model", "structured state space", "mamba"),
}

# Off-domain physical/clinical signals when query is AI/CS without those terms
PHYSICAL_CHEM_RE = re.compile(
    r"\b(vapor[- ]liquid|liquid[- ]vapor|liquid metal|pure[- ]liquid|liquid chromatography|"
    r"liquid crystal|level sensor|microplastics|viscosity|electrolyte|alloy|alloying|"
    r"capillary|distillation|solubility|aqueous|molar|enthalpy)\b",
    re.IGNORECASE,
)
OFF_DOMAIN_NON_AI_RE = re.compile(
    r"\b(spacecraft|orbital|satellite|thruster|attitude control|propulsion|lunar|martian|"
    r"soil moisture|watershed|hydrolog|catchment|forestry|fisheries|ecological|species abundance|"
    r"myocardial|cardiovascular|arterial|cohort|patients?|clinical trial|tumou?r|carcinoma)\b",
    re.IGNORECASE,
)
AI_CS_CONTEXT_RE = re.compile(
    r"\b(neural|deep learning|machine learning|transformer|language model|mamba|sequence model|"
    r"token|autoregressive|attention|representation learning|classification|benchmark|training|inference)\b",
    re.IGNORECASE,
)


@dataclass
class QueryIntent:
    raw_query: str
    clean_query: str
    domain: str
    temporal_intent: str
    terms: list[str]
    bigrams: list[str]
    aliases: tuple[str, ...]


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").casefold()) if len(t) > 1]


def _singular(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def understand_query(topic: str) -> QueryIntent:
    """Parse query intent, domain, temporal preference, content terms, and bigrams."""
    raw = (topic or "").strip()
    temporal = "foundational" if FOUNDATIONAL_RE.search(raw) else ("recent" if RECENT_RE.search(raw) else "balanced")
    cleaned = " ".join(QUERY_MODIFIERS_RE.sub(" ", raw).split()) or raw
    tokens = [_singular(t) for t in _tokenize(cleaned) if t not in STOPWORDS]
    bigrams = [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]
    low_clean = " ".join(_tokenize(cleaned))
    aliases: tuple[str, ...] = ()
    for phrase, al in CONTROLLED_ALIASES.items():
        if phrase in low_clean or phrase.rstrip("s") in low_clean:
            aliases = al
            break
    return QueryIntent(
        raw_query=raw,
        clean_query=cleaned,
        domain=classify_domain(raw),
        temporal_intent=temporal,
        terms=tokens,
        bigrams=bigrams,
        aliases=aliases,
    )


def _has_ordered_phrase(tokens: list[str], query_terms: list[str], max_gap: int = 2) -> bool:
    """Return True if query terms appear in order with at most `max_gap` token step between consecutive terms."""
    if not query_terms or not tokens:
        return False
    norm_tokens = [_singular(t) for t in tokens]
    if len(query_terms) == 1:
        return query_terms[0] in norm_tokens
    positions: list[list[int]] = []
    for qt in query_terms:
        pos = [idx for idx, tok in enumerate(norm_tokens) if tok == qt]
        if not pos:
            return False
        positions.append(pos)

    def _chain(step: int, prev_pos: int) -> bool:
        if step == len(positions):
            return True
        for p in positions[step]:
            if 1 <= (p - prev_pos) <= max_gap:
                if _chain(step + 1, p):
                    return True
        return False

    return any(_chain(1, start) for start in positions[0])


def _has_tight_unordered_window(
    tokens: list[str], query_terms: list[str], max_extra_gap: int = 1
) -> bool:
    """Return True if all unique query terms co-occur in a tight contiguous window regardless of order.

    Handles compound-head reorderings (e.g. 'space state model' <-> 'state-space model')
    without allowing scattered false positives across distant parts of a sentence.
    """
    unique_terms = set(query_terms)
    if len(unique_terms) < 2 or len(tokens) < len(unique_terms):
        return False
    norm_tokens = [_singular(t) for t in tokens]
    window = len(unique_terms) + max_extra_gap
    for start in range(len(norm_tokens) - len(unique_terms) + 1):
        span = norm_tokens[start : start + window]
        if unique_terms.issubset(span):
            return True
    return False


def disambiguate_query(topic: str, field_override: str | None = None) -> dict[str, Any]:
    """Expose general-purpose query disambiguation without silently rewriting the user query."""
    intent = understand_query(topic)
    domain_candidates = classify_domain_candidates(topic)
    resolved_domain = intent.domain
    if field_override:
        fov = field_override.strip().casefold()
        if fov in DOMAIN_PROFILES:
            resolved_domain = fov
        else:
            matched_override = classify_domain(fov)
            if matched_override != "general":
                resolved_domain = matched_override

    alternatives: list[dict[str, str]] = []
    if len(intent.terms) >= 2:
        # General compound-reordering / domain-polysemy check
        if len(intent.terms) in (2, 3):
            reversed_phrase = " ".join(reversed(intent.terms))
            swapped_first_two = (
                f"{intent.terms[1]} {intent.terms[0]} " + " ".join(intent.terms[2:])
            ).strip()
            for variant in dict.fromkeys([swapped_first_two, reversed_phrase]):
                if variant != " ".join(intent.terms):
                    alternatives.append(
                        {
                            "interpretation": variant,
                            "domain": resolved_domain,
                            "reason": "reordered_compound_terminology",
                        }
                    )
        for cand_dom in domain_candidates:
            if cand_dom != resolved_domain:
                alternatives.append(
                    {
                        "interpretation": f"{intent.clean_query} ({cand_dom})",
                        "domain": cand_dom,
                        "reason": "cross_disciplinary_domain_interpretation",
                    }
                )
        if resolved_domain == "general":
            alternatives.append(
                {
                    "interpretation": f"{intent.clean_query} (ai_cs: computational / ML architectures)",
                    "domain": "ai_cs",
                    "reason": "general_query_may_target_computational_or_ml_literature",
                }
            )

    is_ambiguous = bool(
        len(domain_candidates) > 1
        or (resolved_domain == "general" and len(intent.terms) >= 2)
    )
    return {
        "raw_query": intent.raw_query,
        "clean_query": intent.clean_query,
        "terms": intent.terms,
        "detected_domain": intent.domain,
        "resolved_domain": resolved_domain,
        "is_ambiguous": is_ambiguous,
        "alternative_interpretations": alternatives[:5],
        "rewritten": False,
        "note": (
            "Query retained verbatim; reordered compound forms and cross-disciplinary "
            "interpretations are exposed without silent rewriting."
        ),
    }


def _sentence_cosine(query_terms: list[str], sentence: str) -> float:
    """Compute lightweight normalized TF-cosine similarity between query terms and a sentence."""
    sent_tokens = [_singular(t) for t in _tokenize(sentence) if t not in STOPWORDS]
    if not query_terms or not sent_tokens:
        return 0.0
    q_set = set(query_terms)
    s_counts: dict[str, int] = {}
    for tok in sent_tokens:
        s_counts[tok] = s_counts.get(tok, 0) + 1
    dot = sum(s_counts.get(qt, 0) for qt in q_set)
    if dot == 0:
        return 0.0
    q_norm = math.sqrt(len(q_set))
    s_norm = math.sqrt(sum(c * c for c in s_counts.values()))
    return dot / (q_norm * s_norm) if (q_norm and s_norm) else 0.0


def evaluate_relevance(
    topic: str,
    title: str,
    abstract: str | None,
    fields: str = "",
    research_domain: str | None = None,
) -> dict[str, Any]:
    """Classify candidate relevance using phrase/proximity, sentence cosine, and domain checks."""
    intent = understand_query(topic)
    if not intent.terms:
        return {
            "label": "IRRELEVANT",
            "eligible": False,
            "confidence": 0.0,
            "reason": "empty_query",
            "supporting_fields": [],
            "rule_version": RULE_VERSION,
        }

    title_clean = " ".join(_tokenize(title))
    title_sing = " ".join(_singular(t) for t in _tokenize(title))
    abs_text = abstract or ""
    abs_clean = " ".join(_tokenize(abs_text))
    abs_sing = " ".join(_singular(t) for t in _tokenize(abs_text))
    fields_sing = " ".join(_singular(t) for t in _tokenize(fields))
    combined_sing = f"{title_sing} {abs_sing} {fields_sing}".strip()

    # 1. Exact/hyphenated phrase or controlled alias match
    clean_phrase = " ".join(intent.terms)
    phrase_in_title = clean_phrase in title_sing or any(al in title_clean for al in intent.aliases)
    phrase_in_abs = clean_phrase in abs_sing or any(al in abs_clean for al in intent.aliases)

    # 2. Bigram & ordered/reordered-phrase proximity check
    title_tokens = _tokenize(title)
    abs_tokens = _tokenize(abs_text)
    bigram_hits_title = sum(1 for bg in intent.bigrams if bg in title_sing)
    bigram_hits_abs = sum(1 for bg in intent.bigrams if bg in abs_sing)
    gap = 1 if len(intent.terms) <= 2 else 2
    tight_in_title = _has_ordered_phrase(title_tokens, intent.terms, max_gap=gap) or _has_tight_unordered_window(
        title_tokens, intent.terms, max_extra_gap=0
    )
    abs_sentences = [sent for sent in SENTENCE_SPLIT_RE.split(abs_text) if sent.strip()]
    tight_in_abs = any(
        _has_ordered_phrase(_tokenize(sent), intent.terms, max_gap=gap)
        or _has_tight_unordered_window(_tokenize(sent), intent.terms, max_extra_gap=0)
        for sent in abs_sentences
    )

    # 3. Term coverage & peak sentence cosine
    term_hits = sum(1 for t in set(intent.terms) if re.search(rf"\b{re.escape(t)}\b", combined_sing))
    term_cov = term_hits / len(set(intent.terms))
    sents = [title] + [s for s in SENTENCE_SPLIT_RE.split(abs_text) if s.strip()]
    peak_cos = max((_sentence_cosine(intent.terms, s) for s in sents), default=0.0)

    # 4. Research-field compatibility check (e.g. liquid metal / vapor-liquid vs AI/CS)
    off_domain_chem = bool(
        intent.domain == "ai_cs"
        and PHYSICAL_CHEM_RE.search(f"{title} {abs_text}")
        and not PHYSICAL_CHEM_RE.search(intent.raw_query)
        and not phrase_in_title
        and not phrase_in_abs
    )
    if off_domain_chem:
        return {
            "label": "IRRELEVANT",
            "eligible": False,
            "confidence": 0.12,
            "reason": "field_mismatch_physical_chemistry_or_materials",
            "supporting_fields": ["title", "abstract"] if abs_text else ["title"],
            "rule_version": RULE_VERSION,
        }
    off_domain_non_ai = bool(
        intent.domain == "ai_cs"
        and OFF_DOMAIN_NON_AI_RE.search(f"{title} {abs_text} {fields}")
        and not OFF_DOMAIN_NON_AI_RE.search(intent.raw_query)
        and not AI_CS_CONTEXT_RE.search(f"{title} {abs_text} {fields}")
    )
    if off_domain_non_ai:
        return {
            "label": "IRRELEVANT",
            "eligible": False,
            "confidence": 0.14,
            "reason": "field_mismatch_non_ai_domain",
            "supporting_fields": ["title", "abstract"] if abs_text else ["title"],
            "rule_version": RULE_VERSION,
        }

    # If multi-word query (2+ content terms) has NO phrase, NO alias, and NO ordered phrase in title/abs -> scattered false positive!
    # For 4+ term multi-concept queries, allow >=2 matching bigrams with >=0.8 term coverage to proceed to concept-overlap scoring.
    multiword = len(intent.terms) >= 2
    four_term_bigram_ok = len(intent.terms) >= 4 and (
        bigram_hits_title >= 2 or (bigram_hits_abs >= 2 and term_cov >= 0.8)
    )
    if multiword and not (phrase_in_title or phrase_in_abs or tight_in_title or tight_in_abs or four_term_bigram_ok):
        if not abs_text and term_cov < 1.0:
            return {
                "label": "INSUFFICIENT_EVIDENCE",
                "eligible": False,
                "confidence": 0.20,
                "reason": "no_abstract_and_incomplete_title_match",
                "supporting_fields": ["title"],
                "rule_version": RULE_VERSION,
            }
        return {
            "label": "IRRELEVANT",
            "eligible": False,
            "confidence": round(0.15 + 0.10 * term_cov, 3),
            "reason": "scattered_terms_without_phrase_or_proximity",
            "supporting_fields": ["title", "abstract"] if abs_text else ["title"],
            "rule_version": RULE_VERSION,
        }

    # For 3+ term queries (e.g. "liquid neural networks"), require either full phrase/alias OR >=2 bigrams OR tight window with >=0.67 term coverage
    if len(intent.terms) >= 3 and not (phrase_in_title or phrase_in_abs):
        if not (tight_in_title or tight_in_abs or bigram_hits_title >= 2 or (bigram_hits_abs >= 2 and term_cov >= 1.0)):
            return {
                "label": "BORDERLINE",
                "eligible": False,
                "confidence": round(0.35 + 0.1 * peak_cos, 3),
                "reason": "partial_phrase_overlap_without_full_concept_match",
                "supporting_fields": ["title", "abstract"] if abs_text else ["title"],
                "rule_version": RULE_VERSION,
            }

    # Compute calibrated relevance score [0, 1]
    score = (
        (0.42 if phrase_in_title else 0.0)
        + (0.28 if phrase_in_abs else 0.0)
        + (0.15 if tight_in_title or bigram_hits_title else 0.0)
        + (0.10 if tight_in_abs or bigram_hits_abs else 0.0)
        + 0.25 * term_cov
        + 0.20 * peak_cos
    )
    score = min(1.0, round(score, 3))

    supporting = ["title"]
    if abs_text:
        supporting.append("abstract")
    if fields:
        supporting.append("topics")

    if phrase_in_title or score >= 0.72:
        label = "HIGHLY_RELEVANT"
        eligible = True
        reason = "exact_phrase_or_concept_in_title_and_context"
    elif score >= 0.45 or phrase_in_abs or (tight_in_title and term_cov >= 1.0):
        label = "RELEVANT"
        eligible = True
        reason = "tight_phrase_or_abstract_concept_match"
    else:
        label = "BORDERLINE"
        eligible = False
        reason = "weak_contextual_alignment"

    return {
        "label": label,
        "eligible": eligible,
        "confidence": score,
        "reason": reason,
        "supporting_fields": supporting,
        "rule_version": RULE_VERSION,
    }
