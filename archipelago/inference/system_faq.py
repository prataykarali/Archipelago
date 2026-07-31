"""Deterministic system / schema / ops FAQ for Archipelago meta-questions.

Answers product facts that are not concept nodes in Kùzu (OKF schema,
guardrails, embedding model, catalog node types). Keeps LLM calls out of the
loop so eval Q6–Q18 style questions stay cheap and stable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FaqHit:
    """One matched FAQ entry."""

    faq_id: str
    answer: str
    score: float


# (id, patterns, answer) — first highest-scoring match wins.
_FAQ_ENTRIES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "okf_acronym",
        (r"\bokf\b.*\bstand", r"\bacronym\b.*\bokf\b", r"\bokf\b.*\bmean", r"\bwhat\s+does\s+okf\b"),
        "OKF stands for **Open Knowledge Format** — Archipelago's structured "
        "concept schema for teachable technical topics (prerequisites, unlocks, tags).",
    ),
    (
        "okf_keys",
        (r"\b8\b.*\b(?:json\s+)?keys?\b", r"\brequired\s+(?:json\s+)?keys?\b.*\bokf\b", r"\bokf\b.*\bconcept\s+object\b", r"\bkeys?\b.*\bvalid\s+okf\b"),
        "Every valid OKF concept object must include these 8 keys: "
        "`concept_name`, `concept_type`, `difficulty`, `summary`, "
        "`prerequisites`, `unlocks`, `related_to`, `tags`.",
    ),
    (
        "okf_name_words",
        (r"\bmaximum\s+word\b.*\bconcept_name\b", r"\bconcept_name\b.*\b(?:word|words)\b", r"\b≤\s*5\b.*\bconcept_name\b", r"\btitle\s+case\b.*\bconcept_name\b"),
        "An OKF `concept_name` must be **≤5 words**, formatted in **Title Case**.",
    ),
    (
        "okf_unlocks",
        (r"\bunlocks\b.*\bdownstream\b", r"\bdownstream\b.*\bunlocks\b", r"\barray\s+field\b.*\bdownstream\b", r"\bwhich\s+array\b.*\bmastering\b"),
        "In the OKF schema, the **`unlocks`** array lists downstream topics "
        "enabled after mastering the target concept.",
    ),
    (
        "kuzu_engine",
        (
            r"\bgraph\s+database\s+engine\b",
            r"\bk[uù]zu(?:db)?\b.*\b(?:engine|integrated|database|storing|store[sd]?)\b",
            r"\b(?:engine|integrated|database)\b.*\bk[uù]zu(?:db)?\b",
            r"\bstoring\s+connected\s+learning\s+nodes\b",
        ),
        "Archipelago stores connected learning nodes in **KùzuDB** (embedded graph database).",
    ),
    (
        "query_too_long",
        (r"\b500\s+characters?\b", r"\bquer(?:y|ies)\b.*\btoo\s+long\b", r"\bexceeding\s+500\b", r"\bguardrail\b.*\blength\b"),
        "Queries longer than **500 characters** are rejected by the Stage-1 guardrail "
        "with an immediate API error payload: `Query too long` "
        "(limit 500 characters).",
    ),
    (
        "embed_model",
        (r"\bembedding\s+model\b", r"\barctic-embed\b", r"\bsnowflake\b.*\bembed", r"\bquery\s+vectorization\b"),
        "Query vectorization uses the local embedding model "
        "**`Snowflake/snowflake-arctic-embed-m-v1.5`** (also referenced as "
        "Snowflake/arctic-embed-m-v1.5).",
    ),
    (
        "cosine_threshold",
        (
            r"\b0\.75\b",
            r"\bcosine\s+similarity\b.*\bthreshold\b",
            r"\bthreshold\b.*\bcosine\b",
            r"\bminimum\s+cosine\b",
            r"\bkill[-\s]?switch\b",
            r"\bout-of-domain\s+hallucinations?\b",
        ),
        "The minimum cosine similarity threshold before KùzuDB retrieval is "
        "**`0.75`** (out-of-domain kill-switch). Strong lexical/alias matches "
        "may still pass when embeddings are offline.",
    ),
    (
        "empty_okf_array",
        (r"\blacks?\s+any\s+teachable\b", r"\bempty\s+json\s+array\b", r"\bno\s+teachable\s+technical\s+concept\b", r"\bextraction\b.*\b\[\]"),
        "When text has no teachable technical concept, the OKF extraction engine "
        "must return an empty JSON array: **`[]`**.",
    ),
    (
        "ollama_model",
        (r"\bprimary\s+generator\b", r"\bollama\b.*\bmodel\b", r"\bhigh-speed\s+synthesis\b", r"\btwo-pass\s+inference\b.*\bmodel\b"),
        "High-speed synthesis in the two-pass inference pipeline uses **local Ollama** "
        "(configured model: `qwen3.5:0.8b` via `ARCHIPELAGO_OLLAMA_MODEL`, "
        "host: `OLLAMA_HOST`).",
    ),
    (
        "catalog_node_types",
        (r"\bthree\s+new\s+node\s+types\b", r"\bsubject\b.*\bresource\b.*\bjournal", r"\binstitutional\s+catalog\b.*\bnode\s+types\b"),
        "Institutional catalog integration introduced three node types: "
        "**`Subject`**, **`Resource`**, and **`JournalIssue`**.",
    ),
    (
        "has_issue_edge",
        (r"\bhas_issue\b", r"\bjournalissue\b.*\bresource\b", r"\brelationship\s+edge\b.*\bjournal"),
        "A **`HAS_ISSUE`** edge connects a `JournalIssue` node to its parent "
        "paper/journal `Resource` node.",
    ),
    (
        "pdf_url_property",
        (r"\bpdf_url\b", r"\bdocument\b.*\bpdf\b.*\bpropert", r"\bexternal\s+pdf\s+assets\b"),
        "The `Document` node schema stores external PDF assets via "
        "**`pdf_url STRING`** without loading full binaries into server memory.",
    ),
    (
        "no_self_cycle",
        (r"\bcircular\s+graph\b", r"\bown\s+prerequisites\b", r"\bnever\s+appear\s+in\s+its\s+own\b", r"\bcycle\b.*\bconcept\s+nodes?\b"),
        "A concept must **never** appear in its own `prerequisites` or `unlocks` "
        "arrays — this rule prevents circular graph dependencies on individual nodes.",
    ),
    (
        "citation_brackets",
        (r"\binline\s+citation\b", r"\b\[s1\]\b", r"\bpage-view\b.*\bcorrupt", r"\bcitation\s+formatting\b"),
        "Archipelago standardizes citations as bare bracket markers **`[S1]`**, **`[S2]`**, … "
        "and strips raw system routes such as `/api/page-view` or `p.X ↗` from prose "
        "so the frontend never corrupts links.",
    ),
    (
        "atomic_swap",
        (r"\batomic\s+swap\b", r"\bingestion_worker\b", r"\bzero\s+user\s+downtime\b", r"\bokf_graph\.db\b.*\bswap\b"),
        "During database updates, `ingestion_worker` builds a new graph offline and "
        "**atomically swaps** `okf_graph.db` under a write lock so live readers see "
        "zero downtime.",
    ),
)


def match_system_faq(query: str) -> FaqHit | None:
    """Return the best FAQ hit for a meta/system query, or None."""
    q = (query or "").strip()
    if len(q) < 8:
        return None
    ql = q.lower()
    best: FaqHit | None = None
    for faq_id, patterns, answer in _FAQ_ENTRIES:
        score = 0.0
        for pat in patterns:
            if re.search(pat, ql, flags=re.I):
                score += 1.0
        if score <= 0:
            continue
        # Prefer multi-pattern agreement
        if best is None or score > best.score:
            best = FaqHit(faq_id=faq_id, answer=answer, score=score)
    # Require at least one solid pattern hit
    if best is None or best.score < 1.0:
        return None
    return best


def try_system_faq(query: str) -> dict[str, Any] | None:
    """If query matches FAQ, return a full inference-shaped result dict."""
    hit = match_system_faq(query)
    if hit is None:
        return None
    return {
        "text": hit.answer,
        "anchor_concept": None,
        "prerequisites": [],
        "unlocks": [],
        "citations": [],
        "routing": {
            "route": "system_faq",
            "reason": hit.faq_id,
            "score": hit.score,
            "anchor_id": None,
            "related": [],
            "slots": {"intent": "system_faq", "faq_id": hit.faq_id},
        },
        "logs": [{"step": "SystemFAQ", "status": "OK", "details": hit.faq_id}],
        "generation": {"provider": "deterministic", "source": "system_faq", "reason": hit.faq_id},
    }
