"""Nine-sheet consolidated Excel export from a persisted research snapshot.

Metadata only: no ranking, scoring or composite metrics. Unknown values stay
empty (or "N/A" for provider metrics) and are never replaced by zero.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
import json
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .graph import author_key, build_graph, venue_key
from .workbook_extra import EXTRA_HEADERS, populate_extra_sheets

NA = "PROVIDER_FIELD_ABSENT"
LICENSE_RESTRICTED = "LICENSE_RESTRICTED"
HEADERS = {
    "Papers": [
        "Paper ID", "Title", "Year", "Publication date", "DOI", "URL", "arXiv ID",
        "OpenAlex ID", "Semantic Scholar ID", "Publication type", "Authors", "Author IDs",
        "Keywords and topics", "Research field", "Methods", "Datasets", "Evaluation metrics",
        "Abstract", "Venue ID", "Venue", "Publisher", "Citations", "Citation provider",
        "Open access", "License", "Retrieved at", "Evidence status",
    ],
    "Authors": [
        "Author ID", "Name", "ORCID", "OpenAlex ID", "Semantic Scholar ID",
        "Affiliations (paper metadata)", "Provider affiliations", "Identity status",
        "Publication count", "Citation count", "h-index", "i10-index",
        "Primary research fields", "Representative papers", "Coauthor IDs",
        "Profile URL", "Source", "Metric definition", "Coverage", "Observed at",
    ],
    "Venues": [
        "Venue ID", "Name", "Type", "Publisher", "ISSN", "Subject areas", "Open access",
        "Venue URL", "Journal Impact Factor", "CiteScore", "SJR", "CORE classification",
        "Other metrics", "Metric source", "Provider", "Retrieved at", "Paper IDs",
    ],
    "References": [
        "Source paper ID",
        "Referenced work ID",
        "Referenced paper ID (in collection)",
        "Title",
        "DOI",
        "Source",
    ],
    "Citation_Edges": ["Citing paper ID", "Cited paper ID", "Provider", "Relationship"],
    "Topic_Results": [
        "Topic",
        "Paper ID",
        "Collection order",
        "Ordering",
        "Membership basis",
        "Providers",
        "Retrieval status",
        "Retrieved at",
    ],
    "Sources_Provenance": [
        "Paper ID",
        "Provider",
        "Source URL",
        "Retrieved at",
        "License/access",
        "Evidence classification",
    ],
    "Errors_Review": ["Paper ID", "Issue", "Details"],
    "Run_Manifest": ["Field", "Value"],
    **EXTRA_HEADERS,
}
MAX_CELL_CHARS = 32000
LINK_COLUMNS = {"Papers": (5, 6), "Venues": (8,), "Authors": (16,), "Sources_Provenance": (3,)}


def safe_cell(value: Any) -> Any:
    """Prevent spreadsheet formula execution from untrusted metadata."""
    if value is None or isinstance(value, (int, float, bool, date)):
        return value
    value = str(value)[:MAX_CELL_CHARS]
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value


def _names(items: list[Any]) -> str:
    return "; ".join(i["name"] if isinstance(i, dict) else str(i) for i in items)


def _date(value: str | None) -> date | str | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return value


def _metric(value: Any, missing_reason: str = NA) -> Any:
    return missing_reason if value is None else value


def build_workbook(run: dict[str, Any]) -> BytesIO:
    """Build typed, source-linked sheets without filling unknown metrics."""
    book = Workbook()
    default_sheet = book.active
    if default_sheet is not None:
        book.remove(default_sheet)
    sheets = {name: book.create_sheet(name) for name in HEADERS}
    for name, headers in HEADERS.items():
        sheet = sheets[name]
        sheet.append(headers)
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="17365D")
        sheet.auto_filter.ref = f"A1:{sheet.cell(1, len(headers)).coordinate}"
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                48, max(15, len(str(column[0].value)) + 3)
            )

    def add(name: str, values: list[Any]) -> None:
        sheets[name].append([safe_cell(value) for value in values])

    topic = run["options"]["topic"]
    graph = build_graph(run)
    coauthors: dict[str, set[str]] = {}
    for edge in graph["edges"]:
        if edge["type"] == "COAUTHORED_WITH":
            coauthors.setdefault(edge["source"], set()).add(edge["target"])
            coauthors.setdefault(edge["target"], set()).add(edge["source"])
    by_openalex = {
        p["identifiers"].get("openalex_id"): p
        for p in run["papers"]
        if p["identifiers"].get("openalex_id")
    }
    observations = {row["id"]: row for row in run.get("author_observations", [])}
    statuses = {s.get("source"): s.get("status") for s in run.get("sources", [])}
    authors: dict[str, dict[str, Any]] = {}
    venues: dict[str, dict[str, Any]] = {}
    for paper in run["papers"]:
        pid = paper["paper_id"]
        ids = paper["identifiers"]
        author_ids = [author_key(paper, i) for i in range(len(paper["authors"]))]
        vid = venue_key(paper)
        evidence = paper.get("source_metadata", {})
        add(
            "Papers",
            [
                pid,
                paper["title"],
                paper["year"],
                _date(paper["publication_date"]),
                paper["doi"],
                paper["url"],
                ids.get("arxiv_id"),
                ids.get("openalex_id"),
                ids.get("semantic_scholar_id"),
                paper.get("publication_type"),
                "; ".join(a["name"] for a in paper["authors"]),
                "; ".join(author_ids),
                _names(paper.get("topics") or []),
                _names(paper["research_field"])
                if isinstance(paper.get("research_field"), list)
                else paper.get("research_field"),
                _names(paper.get("methods") or []),
                _names(paper.get("datasets") or []),
                _names(paper.get("evaluation_metrics") or []),
                paper["abstract"],
                vid,
                paper["venue"],
                paper.get("publisher") or evidence.get("publisher"),
                paper["citation_count"],
                paper["citation_provider"],
                paper.get("is_open_access"),
                paper.get("license"),
                paper.get("retrieved_at") or run["retrieved_at"],
                paper["evidence_status"],
            ],
        )
        sheets["Papers"].cell(sheets["Papers"].max_row, 4).number_format = "yyyy-mm-dd"
        for index, author in enumerate(paper["authors"]):
            entry = authors.setdefault(
                author_ids[index], {"author": author, "papers": [], "ids": ids}
            )
            entry["papers"].append(paper)
            entry["index"] = index
            entry["source_paper"] = paper
        if vid:
            venues.setdefault(vid, {"paper": paper, "papers": []})["papers"].append(paper)
        for reference in paper["references"]:
            cited = by_openalex.get(reference) if isinstance(reference, str) else None
            add(
                "References",
                [
                    pid,
                    reference,
                    cited["paper_id"] if cited and cited["paper_id"] != pid else None,
                    cited["title"] if cited else None,
                    cited["doi"] if cited else None,
                    paper["citation_provider"],
                ],
            )
        providers = sorted(
            {s.get("source_type") for s in paper["provenance"] if s.get("source_type")}
        )
        add(
            "Topic_Results",
            [
                topic,
                pid,
                paper.get("collection_order") or paper.get("rank"),
                run.get("ordering"),
                "Topic terms present in provider title, abstract or fields",
                "; ".join(providers),
                "; ".join(f"{p}={statuses.get(p, 'unknown')}" for p in providers),
                paper.get("retrieved_at") or run["retrieved_at"],
            ],
        )
        for source in paper["provenance"]:
            add(
                "Sources_Provenance",
                [
                    pid,
                    source.get("source_type"),
                    source.get("source_url"),
                    source.get("fetched_at"),
                    paper.get("license")
                    or ("open access" if paper.get("is_open_access") else None),
                    paper["evidence_status"],
                ],
            )
        if not paper["abstract"]:
            add("Errors_Review", [pid, "abstract_unavailable", "No abstract in provider response"])
        if paper.get("retraction_status") is True:
            add("Errors_Review", [pid, "retracted", "Provider marked work retracted"])
        for match in paper["identity_review"]:
            add("Errors_Review", [pid, "ambiguous_identity", match])
        if not ids.get("doi"):
            add("Errors_Review", [pid, "doi_unavailable", "Other provider identifier retained"])
    author_rows_meta: list[dict[str, Any]] = []
    venue_rows_meta: list[dict[str, Any]] = []
    for key, entry in authors.items():
        author = entry["author"]
        source_paper = entry["source_paper"]
        provider_ids = (source_paper.get("source_metadata") or {}).get("author_openalex_ids") or []
        provider_id = provider_ids[entry["index"]] if entry["index"] < len(provider_ids) else None
        short = provider_id.rsplit("/", 1)[-1] if provider_id else None
        observation = observations.get(short or "", {})
        metrics = observation.get("metrics") or {}
        missing_status = (
            observation.get("enrichment_status")
            if observation
            else ("ENRICHMENT_PENDING" if short else "IDENTITY_UNRESOLVED")
        )
        if missing_status == "AVAILABLE":
            missing_status = "PROVIDER_FIELD_ABSENT"
        fields = sorted({str(t) for p in entry["papers"] for t in (p.get("topics") or [])[:3]})
        author_rows_meta.append({"key": key, "short": short})
        add(
            "Authors",
            [
                key,
                observation.get("name") or author["name"],
                observation.get("orcid") or author.get("orcid"),
                provider_id,
                None,
                "; ".join(author.get("institutions") or []),
                "; ".join(
                    str(a["institution"])
                    for a in observation.get("affiliations") or []
                    if a.get("institution")
                ),
                observation.get("identity_status")
                or ("provider_linked" if provider_id else "unverified_name_only"),
                _metric(metrics.get("publication_count"), missing_status),
                _metric(metrics.get("citation_count"), missing_status),
                _metric(metrics.get("h_index"), missing_status),
                _metric(metrics.get("i10_index"), missing_status),
                "; ".join(observation.get("topics") or fields),
                "; ".join(p["paper_id"] for p in entry["papers"][:3]),
                "; ".join(sorted(coauthors.get(key, ()))),
                f"https://openalex.org/{short}" if short else None,
                observation.get("provider") or "paper metadata",
                metrics.get("definition"),
                metrics.get("coverage"),
                observation.get("retrieved_at"),
            ],
        )
    for vid, entry in venues.items():
        paper = entry["paper"]
        details = paper.get("venue_details") or {}
        issn = details.get("issn") or []
        if isinstance(issn, str):
            issn = [issn]
        subjects = sorted({str(t) for p in entry["papers"] for t in (p.get("topics") or [])[:2]})
        other_parts = [
            f"{k}={details[k]}"
            for k in ("openalex_2yr_mean_citedness", "h_index", "i10_index", "works_count", "is_in_doaj")
            if details.get(k) is not None
        ]
        venue_rows_meta.append({"vid": vid, "details": details})
        add(
            "Venues",
            [
                vid,
                paper["venue"],
                details.get("type"),
                details.get("publisher"),
                "; ".join(issn),
                "; ".join(subjects),
                details.get("open_access"),
                details.get("url"),
                _metric(details.get("impact_factor"), LICENSE_RESTRICTED),
                _metric(details.get("citescore"), LICENSE_RESTRICTED),
                _metric(details.get("sjr"), LICENSE_RESTRICTED),
                _metric(details.get("core_rank"), LICENSE_RESTRICTED),
                "; ".join(other_parts) if other_parts else NA,
                "OpenAlex source profile (Clarivate JIF/CiteScore/SJR are LICENSE_RESTRICTED)"
                if other_parts
                else "None retrieved (licensed or restricted metrics are not scraped)",
                details.get("provider"),
                details.get("retrieved_at") or run["retrieved_at"],
                "; ".join(p["paper_id"] for p in entry["papers"]),
            ],
        )
    populate_extra_sheets(add, run, author_rows_meta, venue_rows_meta)
    for edge in graph["edges"]:
        if edge["type"] == "CITES":
            add("Citation_Edges", [edge["source"].removeprefix("paper:"), edge["target"].removeprefix("paper:"), edge["provider"], "CITES"])
    kinds: dict[str, int] = {}
    for node in graph["nodes"]:
        kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
    manifest = {
        "topic": topic,
        "requested_count": run["options"].get("top_k"),
        "query_parameters": json.dumps(run["options"], sort_keys=True),
        "executed_at": run["retrieved_at"],
        "software_version": run.get("schema"),
        "candidate_count": run.get("candidate_count"),
        "filtered_count": run.get("filtered_count"),
        "selected_count": len(run["papers"]),
        "ordering": run.get("ordering"),
        "ranking_policy": "No ranking or quality scores are computed; order is collection order only",
        "provider_status": json.dumps(run.get("sources", []), sort_keys=True),
        "provider_selection": json.dumps(run.get("provider_selection", {}), sort_keys=True),
        "google_scholar_link": run.get("google_scholar_url") or NA,
        "provider_versions": "unavailable from responses",
        "graph_nodes": json.dumps(kinds, sort_keys=True),
        "graph_edges": len(graph["edges"]),
        "compatibility": "Topic_Rankings was replaced by Topic_Results (no scores)",
    }
    for key, value in manifest.items():
        add("Run_Manifest", [key, value])
    for name, columns in LINK_COLUMNS.items():
        for row in sheets[name].iter_rows(min_row=2):
            for index in columns:
                cell = row[index - 1]
                if isinstance(cell.value, str) and cell.value.startswith(("https://", "http://")):
                    cell.hyperlink = cell.value
                    cell.style = "Hyperlink"
                elif name == "Papers" and index == 5 and cell.value:
                    cell.hyperlink = f"https://doi.org/{cell.value}"
                    cell.style = "Hyperlink"
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output
