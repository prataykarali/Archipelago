"""Normalized extra sheets (10-14) and Coverage_Audit for the S5 Excel workbook."""

from __future__ import annotations

from typing import Any

EXTRA_HEADERS: dict[str, list[str]] = {
    "Institutions_Affiliations": [
        "Institution Key", "Institution Name", "ROR ID", "OpenAlex Institution ID",
        "Country Code", "Institution Type", "Linked Paper IDs", "Linked Author IDs", "Provider",
    ],
    "Funding_Grants": [
        "Paper ID", "Funder Name", "Funder ID / DOI", "Award / Grant ID", "Provider",
    ],
    "Research_Claims": [
        "Paper ID", "Claim Type", "Normalized Value", "Exact Evidence",
        "Source URL", "Location", "Extraction Method", "Status", "Reviewed At",
    ],
    "Metric_Observations": [
        "Entity Type", "Entity ID", "Metric Name", "Value", "Provider",
        "Observation Timestamp", "Metric Definition", "Coverage / Notes",
    ],
    "Coverage_Audit": [
        "Entity / Field", "Total Entities", "Eligible", "Attempted",
        "Successful", "Pending", "Errors", "Populated Count", "Coverage %", "Primary Missing Reason",
    ],
}


def populate_extra_sheets(
    add: Any,
    run: dict[str, Any],
    author_rows_meta: list[dict[str, Any]],
    venue_rows_meta: list[dict[str, Any]],
) -> None:
    """Populate sheets 10-14 with institutions, grants, claims, metric observations, and Coverage_Audit."""
    papers = run.get("papers") or []
    observations = {row["id"]: row for row in run.get("author_observations") or []}
    institutions: dict[str, dict[str, Any]] = {}

    for paper in papers:
        pid = paper["paper_id"]
        prov = paper.get("citation_provider") or paper.get("source") or "provider"
        for grant in paper.get("grants") or []:
            add(
                "Funding_Grants",
                [pid, grant.get("funder_name"), grant.get("funder_id"), grant.get("award_id"), grant.get("provider") or prov],
            )
        for claim in paper.get("claims") or []:
            add(
                "Research_Claims",
                [
                    pid, claim.get("claim_type"), claim.get("normalized_value"), claim.get("exact_evidence"),
                    claim.get("source_url") or paper.get("url"), claim.get("location"),
                    claim.get("extraction_method"), claim.get("status"), claim.get("reviewed_at"),
                ],
            )
        for obs in paper.get("citation_observations") or []:
            add(
                "Metric_Observations",
                [
                    "Paper", pid, "citation_count", obs.get("count"), obs.get("provider"),
                    paper.get("retrieved_at") or run.get("retrieved_at"),
                    "Provider indexed citation count (zero is valid)", "Paper-level citation observation",
                ],
            )
        if paper.get("fwci") is not None:
            add(
                "Metric_Observations",
                [
                    "Paper", pid, "fwci", paper.get("fwci"), "openalex",
                    paper.get("retrieved_at") or run.get("retrieved_at"),
                    "OpenAlex Field-Weighted Citation Impact", "Field-normalized citation indicator",
                ],
            )
        for idx, inst_list in enumerate(paper.get("author_institutions") or []):
            aid = (paper.get("author_ids") or [None])[idx] if idx < len(paper.get("author_ids") or []) else None
            for inst in inst_list or []:
                name = inst.get("name")
                if not name:
                    continue
                ikey = inst.get("ror") or inst.get("id") or name.casefold()
                rec = institutions.setdefault(
                    ikey,
                    {
                        "key": ikey, "name": name, "ror": inst.get("ror"), "id": inst.get("id"),
                        "cc": inst.get("country_code"), "type": inst.get("type"),
                        "papers": set(), "authors": set(), "provider": prov,
                    },
                )
                rec["papers"].add(pid)
                if aid:
                    rec["authors"].add(str(aid).rsplit("/", 1)[-1])

    for rec in institutions.values():
        add(
            "Institutions_Affiliations",
            [
                rec["key"], rec["name"], rec["ror"], rec["id"], rec["cc"], rec["type"],
                "; ".join(sorted(rec["papers"])), "; ".join(sorted(rec["authors"])), rec["provider"],
            ],
        )

    for a in author_rows_meta:
        obs = observations.get(a.get("short") or "") or {}
        metrics = obs.get("metrics") or {}
        for mname in ("publication_count", "citation_count", "h_index", "i10_index"):
            if metrics.get(mname) is not None:
                add(
                    "Metric_Observations",
                    [
                        "Author", a["key"], mname, metrics[mname], obs.get("provider") or "openalex",
                        obs.get("retrieved_at"), metrics.get("definition"), metrics.get("coverage"),
                    ],
                )

    for v in venue_rows_meta:
        det = v.get("details") or {}
        for mname in ("openalex_2yr_mean_citedness", "h_index", "i10_index", "works_count", "cited_by_count"):
            if det.get(mname) is not None:
                add(
                    "Metric_Observations",
                    [
                        "Venue", v["vid"], mname, det[mname], det.get("provider") or "openalex",
                        det.get("retrieved_at"),
                        "OpenAlex source metric (not Clarivate JIF / Scopus CiteScore)",
                        "OpenAlex source profile",
                    ],
                )

    # Coverage_Audit
    n_papers = len(papers)
    n_authors = len(author_rows_meta)
    n_venues = len(venue_rows_meta)
    elig_auth = sum(1 for a in author_rows_meta if a.get("short"))
    att_auth = sum(1 for a in author_rows_meta if a.get("short") and a.get("short") in observations)
    ok_auth = sum(
        1 for a in author_rows_meta
        if (observations.get(a.get("short") or "") or {}).get("enrichment_status") == "AVAILABLE"
    )
    pend_auth = sum(
        1 for a in author_rows_meta
        if (observations.get(a.get("short") or "") or {}).get("enrichment_status") == "ENRICHMENT_PENDING"
    )
    err_auth = max(0, att_auth - ok_auth - pend_auth)

    audit_rows = [
        ("Papers: DOI", n_papers, n_papers, n_papers, sum(bool(p.get("doi")) for p in papers), 0, 0, sum(bool(p.get("doi")) for p in papers), "PROVIDER_FIELD_ABSENT"),
        ("Papers: Abstract", n_papers, n_papers, n_papers, sum(bool(p.get("abstract")) for p in papers), 0, 0, sum(bool(p.get("abstract")) for p in papers), "PROVIDER_FIELD_ABSENT"),
        ("Papers: Methods", n_papers, n_papers, n_papers, sum(bool(p.get("methods")) for p in papers), 0, 0, sum(bool(p.get("methods")) for p in papers), "NOT_FOUND_IN_AVAILABLE_EVIDENCE"),
        ("Papers: Datasets", n_papers, n_papers, n_papers, sum(bool(p.get("datasets")) for p in papers), 0, 0, sum(bool(p.get("datasets")) for p in papers), "NOT_FOUND_IN_AVAILABLE_EVIDENCE"),
        ("Papers: Evaluation Metrics", n_papers, n_papers, n_papers, sum(bool(p.get("evaluation_metrics")) for p in papers), 0, 0, sum(bool(p.get("evaluation_metrics")) for p in papers), "NOT_FOUND_IN_AVAILABLE_EVIDENCE"),
        ("Authors: Provider Bibliometrics", n_authors, elig_auth, att_auth, ok_auth, pend_auth, err_auth, ok_auth, "IDENTITY_UNRESOLVED" if elig_auth < n_authors else "PROVIDER_FIELD_ABSENT"),
        ("Venues: Official URL", n_venues, n_venues, n_venues, sum(bool((v.get("details") or {}).get("url")) for v in venue_rows_meta), 0, 0, sum(bool((v.get("details") or {}).get("url")) for v in venue_rows_meta), "PROVIDER_FIELD_ABSENT"),
        ("Venues: Licensed JIF/CiteScore/SJR", n_venues, 0, 0, 0, 0, 0, 0, "LICENSE_RESTRICTED"),
    ]
    for label, tot, elig, att, ok, pend, err, pop, reason in audit_rows:
        pct = round((pop / tot) * 100, 1) if tot else 0.0
        add("Coverage_Audit", [label, tot, elig, att, ok, pend, err, pop, pct, reason])
