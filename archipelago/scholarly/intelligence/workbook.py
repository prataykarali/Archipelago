"""Nine-sheet Excel export from a persisted research snapshot."""

from __future__ import annotations

from io import BytesIO
import json
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .graph import build_graph

HEADERS = {
    "Papers": [
        "Paper ID",
        "Title",
        "Year",
        "DOI",
        "URL",
        "Authors",
        "Venue",
        "Abstract",
        "Citations",
        "Citation provider",
        "Relevance score",
        "Evidence status",
    ],
    "Authors": [
        "Author ID",
        "ORCID",
        "Name",
        "Affiliations",
        "Publication count",
        "Citation metrics",
        "h-index",
        "i10-index",
        "Source",
    ],
    "Venues": [
        "Venue ID",
        "Name",
        "Type",
        "Publisher",
        "ISSN",
        "Recognized metrics",
        "Provider",
        "Timestamp",
    ],
    "References": [
        "Source paper ID",
        "Referenced work ID",
        "Title",
        "DOI",
        "Bibliographic metadata",
        "Source",
    ],
    "Citation_Edges": ["Citing paper", "Cited paper", "Verification provider", "Relationship"],
    "Topic_Rankings": [
        "Rank",
        "Paper ID",
        "Topic relevance",
        "Recency",
        "Citation signal",
        "Explanation",
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
}
MAX_CELL_CHARS = 32000


def safe_cell(value: Any) -> Any:
    """Prevent spreadsheet formula execution from untrusted metadata."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    value = str(value)[:MAX_CELL_CHARS]
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value


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

    authors: dict[str, dict[str, Any]] = {}
    venues: dict[str, dict[str, Any]] = {}
    for paper in run["papers"]:
        pid = paper["paper_id"]
        ids = paper["identifiers"]
        add(
            "Papers",
            [
                pid,
                paper["title"],
                paper["year"],
                paper["doi"],
                paper["url"],
                "; ".join(a["name"] for a in paper["authors"]),
                paper["venue"],
                paper["abstract"],
                paper["citation_count"],
                paper["citation_provider"],
                paper["relevance_score"],
                paper["evidence_status"],
            ],
        )
        for author in paper["authors"]:
            key = author.get("orcid") or f"unverified:{pid}:{author['name']}"
            authors.setdefault(key, author)
        if paper["venue"]:
            venues.setdefault(paper["venue"], paper)
        for reference in paper["references"]:
            add("References", [pid, reference, None, None, None, paper["citation_provider"]])
        add(
            "Topic_Rankings",
            [
                paper["rank"],
                pid,
                paper["topic_relevance"],
                paper["recency_signal"],
                paper["citation_signal"],
                "; ".join(paper["ranking_reasons"]),
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
                    None,
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
    for key, author in authors.items():
        add(
            "Authors",
            [
                key,
                author.get("orcid"),
                author["name"],
                "; ".join(author.get("institutions") or []),
                None,
                None,
                None,
                None,
                "paper metadata",
            ],
        )
    for venue, paper in venues.items():
        metadata = paper["source_metadata"]
        add(
            "Venues",
            [
                venue,
                venue,
                None,
                metadata.get("publisher"),
                None,
                None,
                paper["citation_provider"],
                run["retrieved_at"],
            ],
        )
    for edge in build_graph(run)["edges"]:
        if edge["type"] == "CITES":
            add("Citation_Edges", [edge["source"], edge["target"], edge["provider"], "CITES"])
    manifest = {
        "topic": run["options"]["topic"],
        "query_parameters": json.dumps(run["options"], sort_keys=True),
        "executed_at": run["retrieved_at"],
        "software_version": run["schema"],
        "candidate_count": run["candidate_count"],
        "filtered_count": run["filtered_count"],
        "selected_count": len(run["papers"]),
        "provider_status": json.dumps(run["sources"], sort_keys=True),
        "provider_versions": "unavailable from responses",
    }
    for key, value in manifest.items():
        add("Run_Manifest", [key, value])
    for name in ("Papers", "Sources_Provenance"):
        sheet = sheets[name]
        link_columns = (5,) if name == "Papers" else (3,)
        for row in sheet.iter_rows(min_row=2):
            for index in link_columns:
                cell = row[index - 1]
                if isinstance(cell.value, str) and cell.value.startswith("https://"):
                    cell.hyperlink = cell.value
                    cell.style = "Hyperlink"
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output
