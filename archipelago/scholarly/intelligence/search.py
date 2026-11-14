"""Bounded scholarly discovery with conservative topic eligibility."""

from __future__ import annotations

from datetime import UTC, datetime
import html
import re
from typing import Any

from archipelago.scholarly.discovery.canonicalizer import normalize_title
from archipelago.scholarly.discovery.orchestrator import DiscoveryOrchestrator

from .enrichment import enrich_authors, enrich_venues, venue_observation
from .extraction import extract_evidence

DEFAULT_TOP_K = 20
MAX_TOP_K = 100
SOURCE_MULTIPLIER = 2
MAX_QUERY_CHARS = 200
VERSION_SUFFIX = re.compile(r"/v\d+$", re.IGNORECASE)
VALID_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
QUERY_MODIFIERS = re.compile(r"\b(latest|recent|newest|papers|studies|research)\b", re.IGNORECASE)
TOPIC_STOPWORDS = frozenset({"a", "an", "and", "for", "in", "of", "on", "the", "with", "to"})
TOPIC_ALIASES = {
    "graph neural networks": "gnn",
    "retrieval augmented generation": "rag",
    "bengali": "bangla",
    "speech recognition": "asr",
    "continual learning": "lifelong learning",
    "ocr": "optical character recognition",
    "document understanding": "document",
}


SLM_CONCEPT_RE = re.compile(
    r"\b(small language models?|slms?|compact language models?|lightweight language models?|"
    r"tiny language models?|mini language models?|sub[- ]?billion|lfm2|mobilellm|tinyllama|phi-[23])\b",
    re.I,
)
EDGE_CONCEPT_RE = re.compile(
    r"\b(on[- ]device|edge devices?|edge inference|edge ai|edge intelligence|edge deployment|"
    r"mobile devices?|embedded devices?|microcontrollers?|mcu|npu|iot|smartphones?|local inference)\b",
    re.I,
)
EFF_CONCEPT_RE = re.compile(
    r"\b(efficien(?:t|cy)|quantiz(?:ation|ed|e)|pruning|distillation|compression|"
    r"low[- ]memory|dvfs|latency|energy[- ]efficient|lightweight|inference)\b",
    re.I,
)
QUERY_SLM_RE = re.compile(r"\b(small language models?|slms?)\b", re.I)
QUERY_EDGE_RE = re.compile(r"\b(on[- ]device|edge)\b", re.I)
QUERY_GNN_RE = re.compile(r"\b(graph neural networks?|gnns?)\b", re.I)
GNN_CONCEPT_RE = re.compile(
    r"\b(graph neural networks?|gnns?|graph convolutional|graph attention|message passing neural)\b",
    re.I,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def clean_scholarly_text(raw: str | None) -> str:
    """Decode single/double-escaped HTML entities, strip markup tags, normalize spaces."""
    text = raw or ""
    for _ in range(3):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return " ".join(_HTML_TAG_RE.sub(" ", text).split())


def assess_topic_eligibility(
    topic: str, title: str, abstract: str | None, fields: str = ""
) -> tuple[bool, str]:
    """Evaluate central-concept eligibility without ranking scores."""
    text_ta = " ".join((title or "", abstract or ""))
    evidence = re.sub(r"[^\w]+", " ", " ".join((title, abstract or "", fields)).casefold())
    query = re.sub(r"[^\w]+", " ", QUERY_MODIFIERS.sub(" ", topic).casefold()).strip()
    if not query:
        return False, "empty_query"
    if QUERY_SLM_RE.search(query) and QUERY_EDGE_RE.search(query):
        has_slm = bool(SLM_CONCEPT_RE.search(text_ta))
        has_edge = bool(EDGE_CONCEPT_RE.search(text_ta))
        has_eff = bool(EFF_CONCEPT_RE.search(text_ta))
        if has_slm and has_edge and has_eff:
            return True, "matched_slm_edge_efficiency_concepts"
        missing = [
            name
            for name, ok in (("slm", has_slm), ("edge_on_device", has_edge), ("efficiency", has_eff))
            if not ok
        ]
        return False, f"missing_central_concepts:{','.join(missing)}"
    if QUERY_GNN_RE.search(query) and not GNN_CONCEPT_RE.search(text_ta):
        return False, "missing_central_concepts:gnn"
    alias_matched = False
    for phrase, alias in TOPIC_ALIASES.items():
        if phrase in query and re.search(rf"\b{re.escape(alias)}\b", evidence):
            query = query.replace(phrase, " ")
            alias_matched = True
    terms = [word for word in query.split() if word not in TOPIC_STOPWORDS]
    matched = (bool(terms) or alias_matched) and all(
        re.search(rf"\b{re.escape(word)}s?\b", evidence) for word in terms
    )
    return matched, ("matched_query_terms" if matched else "missing_query_terms")


def topic_matches(topic: str, title: str, abstract: str | None, fields: str = "") -> bool:
    """Require the named research concepts in provider title, abstract or fields."""
    ok, _reason = assess_topic_eligibility(topic, title, abstract, fields)
    return ok


def _version_key(row: dict[str, Any]) -> tuple[str, str, str, int | None] | None:
    """Unify explicit DOI versions only with matching title, author and year."""
    doi = row.get("doi") or ""
    if not VERSION_SUFFIX.search(doi):
        return None
    authors = row.get("authors") or []
    if not authors or not row.get("year"):
        return None
    return (
        VERSION_SUFFIX.sub("", doi.casefold()),
        normalize_title(row["title"]),
        authors[0]["name"].casefold().strip(),
        row["year"],
    )


def validate_options(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate user filters without accepting arbitrary provider URLs."""
    topic = str(payload.get("topic") or "").strip()
    top_k = payload.get("top_k", DEFAULT_TOP_K)
    if not 3 <= len(topic) <= MAX_QUERY_CHARS:
        raise ValueError("invalid_topic")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError("invalid_top_k")
    start = payload.get("year_from")
    end = payload.get("year_to")
    current = datetime.now(UTC).year
    if any(
        v is not None
        and (isinstance(v, bool) or not isinstance(v, int) or not 1800 <= v <= current + 1)
        for v in (start, end)
    ):
        raise ValueError("invalid_year")
    if start and end and start > end:
        raise ValueError("invalid_year_range")
    sort = payload.get("sort", "newest")
    if sort not in {"relevance", "newest", "provider"}:
        raise ValueError("invalid_sort")
    oa = payload.get("open_access")
    if oa is not None and not isinstance(oa, bool):
        raise ValueError("invalid_open_access")
    return {
        "topic": topic,
        "top_k": top_k,
        "year_from": start,
        "year_to": end,
        "sort": "newest" if sort == "relevance" else sort,
        "open_access": oa,
        "paper_type": str(payload.get("paper_type") or "").strip()[:80],
        "field": str(payload.get("field") or "").strip()[:80],
        "venue": str(payload.get("venue") or "").strip()[:120],
    }


def discover(
    payload: dict[str, Any], orchestrator: DiscoveryOrchestrator | None = None
) -> dict[str, Any]:
    """Return source-linked, filtered papers without PDF or GPU work."""
    options = validate_options(payload)
    engine = orchestrator or DiscoveryOrchestrator()
    search_query = " ".join(QUERY_MODIFIERS.sub(" ", options["topic"]).split()) or options["topic"]
    explicit_sources = (
        [str(s).strip() for s in payload["sources"] if str(s).strip()]
        if isinstance(payload.get("sources"), list)
        else None
    )
    if explicit_sources is not None:
        candidates, sources = engine.discover_with_status(
            search_query, min(MAX_TOP_K, options["top_k"] * SOURCE_MULTIPLIER), explicit_sources=explicit_sources
        )
    else:
        candidates, sources = engine.discover_with_status(
            search_query, min(MAX_TOP_K, options["top_k"] * SOURCE_MULTIPLIER)
        )
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        paper = candidate["paper"]
        clean_title = clean_scholarly_text(paper.title)
        clean_abstract = clean_scholarly_text(paper.abstract) if paper.abstract else None
        year = (
            int(paper.publication_date[:4])
            if paper.publication_date and paper.publication_date[:4].isdigit()
            else None
        )
        metadata = candidate.get("source_metadata") or {}
        if options["year_from"] and (year is None or year < options["year_from"]):
            continue
        if options["year_to"] and (year is None or year > options["year_to"]):
            continue
        if (
            options["open_access"] is not None
            and paper.is_open_access is not options["open_access"]
        ):
            continue
        if (
            options["paper_type"]
            and options["paper_type"].casefold() not in (paper.publication_type or "").casefold()
        ):
            continue
        if options["venue"] and options["venue"].casefold() not in (paper.venue or "").casefold():
            continue
        fields = " ".join(
            str(value) for value in (metadata.get("topics") or metadata.get("keywords") or [])
        )
        if options["field"] and options["field"].casefold() not in fields.casefold():
            continue
        eligible, eligibility_reason = assess_topic_eligibility(
            options["topic"], clean_title, clean_abstract, fields
        )
        if not eligible:
            continue
        provenance = [candidate.get("provenance")]
        provenance.extend(entry.get("provenance") for entry in candidate.get("merge_history", []))
        source_links = [p.model_dump(mode="json") for p in provenance if p is not None and hasattr(p, "model_dump")]
        citation_observations = [
            {"provider": candidate.get("source"), "count": candidate.get("citation_count")}
        ] + [
            {"provider": entry.get("source"), "count": entry.get("citation_count")}
            for entry in candidate.get("merge_history", [])
        ]
        citation_observations = [
            entry for entry in citation_observations if isinstance(entry["count"], int)
        ]
        citation_observation = max(
            citation_observations, key=lambda entry: entry["count"], default=None
        )
        doi = paper.identifiers.doi
        valid_doi = doi if doi and VALID_DOI.fullmatch(doi) else None
        review = list(candidate.get("identity_review") or [])
        if doi and not valid_doi:
            review.append("invalid_doi_from_provider")
        source_url = next((p.get("source_url") for p in source_links if p.get("source_url")), None)
        found = extract_evidence(clean_title, clean_abstract, source_url=source_url)
        fetched = [p.get("fetched_at") for p in source_links if p.get("fetched_at")]
        rows.append(
            {
                "paper_id": paper.paper_id,
                "title": clean_title,
                "subtitle": metadata.get("subtitle"),
                "year": year,
                "publication_date": paper.publication_date,
                "doi": valid_doi,
                "identifiers": paper.identifiers.model_dump(mode="json"),
                "authors": [a.model_dump(mode="json") for a in paper.authors],
                "venue": paper.venue,
                "publication_type": paper.publication_type,
                "language": paper.language,
                "abstract": clean_abstract,
                "is_open_access": paper.is_open_access,
                "oa_status": metadata.get("oa_status"),
                "version_status": metadata.get("version_status"),
                "url": source_url,
                "landing_page_url": metadata.get("landing_page_url"),
                "citation_count": citation_observation["count"] if citation_observation else None,
                "citation_provider": citation_observation["provider"]
                if citation_observation
                else None,
                "citation_observations": citation_observations,
                "fwci": metadata.get("fwci"),
                "citation_normalized_percentile": metadata.get("citation_normalized_percentile"),
                "references": metadata.get("referenced_works") or [],
                "source_metadata": metadata,
                "topics": metadata.get("topics") or metadata.get("keywords") or [],
                "primary_topic": metadata.get("primary_topic"),
                "research_domain": metadata.get("research_domain"),
                "research_field": metadata.get("research_field") or metadata.get("research_domain"),
                "research_subfield": metadata.get("research_subfield"),
                "methods": metadata.get("methods") or found["methods"],
                "models": found["models"],
                "datasets": metadata.get("datasets") or found["datasets"],
                "tasks": found["tasks"],
                "evaluation_metrics": metadata.get("evaluation_metrics")
                or found["evaluation_metrics"],
                "claims": found["claims"],
                "claim_status": found["claim_status"],
                "grants": metadata.get("grants") or [],
                "corresponding_authors": metadata.get("corresponding_authors") or [],
                "author_institutions": metadata.get("author_institutions") or [],
                "countries_distinct_count": metadata.get("countries_distinct_count"),
                "institutions_distinct_count": metadata.get("institutions_distinct_count"),
                "author_ids": metadata.get("author_openalex_ids") or [],
                "publisher": metadata.get("publisher"),
                "license": paper.license,
                "oa_url": paper.oa_url,
                "retrieved_at": max(fetched) if fetched else None,
                "retraction_status": metadata.get("retraction_status"),
                "provenance": source_links,
                "source": candidate.get("source"),
                "evidence_status": "REFERENCE_METADATA_AVAILABLE"
                if metadata.get("referenced_works")
                else "ABSTRACT_AVAILABLE"
                if paper.abstract
                else "METADATA_ONLY",
                "eligibility_reason": eligibility_reason,
                "identity_review": review,
            }
        )
    versioned: dict[tuple[str, str, str, int | None], dict[str, Any]] = {}
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = _version_key(row)
        if key is None:
            unique.append(row)
            continue
        prior = versioned.get(key)
        if prior is None or (row["doi"] or "") > (prior["doi"] or ""):
            versioned[key] = row
    dedup_rows = unique + list(versioned.values())
    by_work: dict[tuple[str, str, int], dict[str, Any]] = {}
    rows = []
    for row in dedup_rows:
        authors = row.get("authors") or []
        ntitle = normalize_title(row.get("title") or "")
        yr = row.get("year")
        if not ntitle or not authors or not yr:
            rows.append(row)
            continue
        wkey = (ntitle, authors[0]["name"].casefold().strip(), int(yr))
        existing = by_work.get(wkey)
        if existing is None:
            by_work[wkey] = row
            rows.append(row)
            continue
        alt_dois = list(existing.get("alternate_dois") or [])
        for d in (existing.get("doi"), row.get("doi")):
            if d and d not in alt_dois:
                alt_dois.append(d)
        existing["alternate_dois"] = alt_dois
        existing["provenance"] = list(existing.get("provenance") or []) + list(
            row.get("provenance") or []
        )
        if not existing.get("abstract") and row.get("abstract"):
            existing["abstract"] = row["abstract"]
    if options["sort"] == "newest":
        rows.sort(key=lambda row: (row["publication_date"] or "", row["paper_id"]), reverse=True)
    selected = rows[: options["top_k"]]
    for position, row in enumerate(selected, 1):
        row["collection_order"] = position
    retrieved_at = datetime.now(UTC).isoformat()
    enriched_venues = enrich_venues(selected) if orchestrator is None else {}
    if orchestrator is None:
        from archipelago.scholarly.discovery.extended_sources import fetch_opencitations_for_dois

        oc_dois = [str(r["doi"]) for r in selected if r.get("doi")]
        oc_map = fetch_opencitations_for_dois(engine.sources.session, oc_dois) if oc_dois else {}
    else:
        oc_map = {}
    for row in selected:
        row["venue_details"] = venue_observation(row, retrieved_at, enriched_venues)
        row["retrieved_at"] = row["retrieved_at"] or retrieved_at
        doi_key = str(row.get("doi") or "").strip().lower()
        if doi_key and doi_key in oc_map and oc_map[doi_key].get("count") is not None:
            row["citation_observations"].append(
                {"provider": "opencitations", "count": oc_map[doi_key]["count"]}
            )
    from archipelago.scholarly.discovery.scholar_deeplink import generate_scholar_url

    selection = dict(getattr(engine, "last_selection", {}) or {})
    selection["final_returned_count"] = len(selected)
    selection["rate_limits_encountered"] = [
        s["source"] for s in sources if s.get("rate_limited")
    ]
    return {
        "schema": "archipelago.research_intelligence.v2",
        "options": options,
        "retrieved_at": retrieved_at,
        "sources": sources,
        "provider_selection": selection,
        "google_scholar_url": generate_scholar_url(options["topic"]),
        "candidate_count": len(candidates),
        "filtered_count": len(rows),
        "ordering": "publication_date_desc" if options["sort"] == "newest" else "provider_returned",
        "papers": selected,
        "author_observations": enrich_authors(selected) if orchestrator is None else [],
    }
