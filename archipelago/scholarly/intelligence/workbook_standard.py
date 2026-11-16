"""Human-readable 5-sheet Standard Research Intelligence Excel export.

Designed for students, professors, and librarians:
  1. Start Here
  2. Papers
  3. Authors
  4. Publications
  5. Sources

Never exposes internal UUIDs, raw JSON, unavailable-metric codes, or zero-filled missing values.
"""

from __future__ import annotations

from copy import copy
from datetime import date
from io import BytesIO
import math
import re
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .graph import author_key, venue_key
from .ranking_metrics import (
    author_average_citations,
    author_m_quotient,
    author_recent_citations,
    comparable_venue_metrics,
    nonnegative_number,
    openalex_citation_percentile,
    relevance_score,
)
from .standard_validation import distinct_standard_papers

MAX_CELL_CHARS = 32000

STANDARD_SHEETS = ("Start Here", "Papers", "Authors", "Publications", "Sources")

PROVIDER_LABELS: dict[str, str] = {
    "openalex": "OpenAlex",
    "crossref": "Crossref",
    "semantic_scholar": "Semantic Scholar",
    "openaire": "OpenAIRE",
    "datacite": "DataCite",
    "arxiv": "arXiv",
    "opencitations": "OpenCitations",
    "orcid": "ORCID",
    "dblp": "DBLP",
    "europe_pmc": "Europe PMC",
    "pubmed": "PubMed",
}

PAPER_TYPE_LABELS: dict[str, str] = {
    "article": "Journal article",
    "journal-article": "Journal article",
    "proceedings-article": "Conference paper",
    "posted-content": "Preprint",
    "preprint": "Preprint",
    "report": "Report",
    "dissertation": "Dissertation",
    "review": "Review article",
    "peer-review": "Peer review",
    "dataset": "Dataset",
    "software": "Software",
    "book-chapter": "Book chapter",
    "publication": "Publication",
}

VENUE_CATEGORY_LABELS: dict[str, str] = {
    "peer_reviewed_journal": "Peer-reviewed journal",
    "peer_reviewed_conference": "Peer-reviewed conference",
    "workshop": "Workshop",
    "preprint_repository": "Preprint repository",
    "institutional_listing": "Institutional listing",
    "unknown": "Unverified",
}

FONT_FAMILY = "Calibri"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(name=FONT_FAMILY, size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name=FONT_FAMILY, size=15, bold=True, color="1F4E78")
SUBTITLE_FONT = Font(name=FONT_FAMILY, size=11, bold=True, color="1F4E78")
BODY_FONT = Font(name=FONT_FAMILY, size=10, color="1A1A1A")
LINK_FONT = Font(name=FONT_FAMILY, size=10, color="0563C1", underline="single")
ZEBRA_FILL = PatternFill("solid", fgColor="F7F9FC")
THIN_BORDER = Border(
    left=Side(style="thin", color="D9E1F2"),
    right=Side(style="thin", color="D9E1F2"),
    top=Side(style="thin", color="D9E1F2"),
    bottom=Side(style="thin", color="D9E1F2"),
)


_PLACEHOLDER_TOKENS = frozenset(
    {
        "none",
        "null",
        "n/a",
        "na",
        "unknown",
        "not_available",
        "provider_unavailable",
        "license_restricted",
        "identity_review_required",
        "unavailable",
    }
)


def _safe_cell(value: Any) -> Any:
    """Prevent spreadsheet formula execution from untrusted metadata."""
    if value is None or isinstance(value, (int, float, bool, date)):
        return value
    text = str(value)[:MAX_CELL_CHARS]
    if text.strip().casefold() in _PLACEHOLDER_TOKENS:
        return None
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def _clean_list_field(items: Any) -> str | None:
    if not isinstance(items, (list, tuple)):
        return None
    cleaned = []
    for item in items:
        value = item.get("name") if isinstance(item, dict) else item
        if value and str(value).strip().casefold() not in _PLACEHOLDER_TOKENS:
            cleaned.append(str(value).strip())
    return ", ".join(dict.fromkeys(cleaned)) or None


_ORGANIZATION_AUTHOR_TERMS = frozenset(
    {"association", "conference", "journal", "proceedings", "publisher", "university"}
)
_YEAR_IN_NAME = re.compile(r"\b(?:19|20)\d{2}\b")


def _valid_author_name(author: dict[str, Any]) -> bool:
    """Exclude obvious provider venue strings mistaken for personal authors."""
    name = str(author.get("name") or "").strip()
    words = set(re.findall(r"[a-z]+", name.casefold()))
    return bool(name) and not (
        _YEAR_IN_NAME.search(name) and words.intersection(_ORGANIZATION_AUTHOR_TERMS)
    )


def _is_standard_valid_paper(paper: dict[str, Any]) -> bool:
    if paper.get("standard_eligible") is False:
        return False
    title = str(paper.get("title") or "").strip()
    authors = [a for a in (paper.get("authors") or []) if isinstance(a, dict) and a.get("name")]
    year = paper.get("year")
    pub_date = str(paper.get("publication_date") or "").strip()
    has_year = isinstance(year, int) or (len(pub_date) >= 4 and pub_date[:4].isdigit())
    has_link = bool(paper.get("doi") or paper.get("url") or paper.get("oa_url"))
    has_prov = bool(paper.get("provenance") or paper.get("discovered_by") or paper.get("source"))
    return bool(title and authors and has_year and has_link and has_prov)


def _format_relevance(rel: dict[str, Any] | None) -> str | None:
    if not isinstance(rel, dict):
        return None
    label = str(rel.get("label") or "").replace("_", " ").title()
    conf = rel.get("confidence")
    if label and isinstance(conf, (int, float)):
        return f"{label} ({conf:.2f})"
    return label or None


def _provider_label(raw: str | None) -> str | None:
    if not raw:
        return None
    low = str(raw).strip().casefold()
    if low in ("paper metadata", "provider", "unknown", "n/a"):
        return None
    return PROVIDER_LABELS.get(low, str(raw).strip())


def _clean_human_type(raw: str | None) -> str | None:
    if not raw:
        return None
    low = str(raw).strip().casefold()
    return PAPER_TYPE_LABELS.get(low, str(raw).replace("-", " ").replace("_", " ").capitalize())


def _short_date(raw: str | None) -> str:
    if not raw:
        return ""
    return str(raw)[:10]


def _init_data_sheet(sheet: Any, headers: list[str], widths: list[int]) -> None:
    sheet.append(headers)
    sheet.freeze_panes = "A2"
    sheet.views.sheetView[0].showGridLines = True
    for col_idx, cell in enumerate(sheet[1], 1):
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER
        sheet.column_dimensions[get_column_letter(col_idx)].width = widths[col_idx - 1]
    sheet.row_dimensions[1].height = 26


def _style_data_sheet(
    sheet: Any,
    headers: list[str],
    widths: list[int],
    wrap_cols: set[int],
    int_cols: dict[int, str],
) -> None:
    sheet.auto_filter.ref = f"A1:{sheet.cell(1, len(headers)).coordinate}"

    for row_idx in range(2, sheet.max_row + 1):
        max_lines = 1
        fill = ZEBRA_FILL if row_idx % 2 == 1 else PatternFill(fill_type=None)
        for col_idx in range(1, len(headers) + 1):
            cell = sheet.cell(row_idx, col_idx)
            if not cell.hyperlink:
                cell.font = BODY_FONT
            if fill.fill_type:
                cell.fill = fill
            cell.border = THIN_BORDER
            is_wrap = col_idx in wrap_cols
            horiz = "right" if col_idx in int_cols else "left"
            cell.alignment = Alignment(horizontal=horiz, vertical="top", wrap_text=is_wrap)
            if col_idx in int_cols and isinstance(cell.value, (int, float)):
                cell.number_format = int_cols[col_idx]
            if is_wrap and isinstance(cell.value, str) and cell.value:
                col_w = max(12, widths[col_idx - 1] - 2)
                lines = sum(
                    max(1, math.ceil(len(part) / col_w)) for part in cell.value.splitlines() or [""]
                )
                max_lines = max(max_lines, min(lines, 12))
        sheet.row_dimensions[row_idx].height = max(20, max_lines * 14.5 + 6)


def _set_link(cell: Any, url: str | None, display_text: str | None = None) -> None:
    if not url or not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return
    if display_text is not None:
        cell.value = _safe_cell(display_text)
    cell.hyperlink = url
    cell.font = LINK_FONT


def _remove_empty_metric_columns(sheet: Any) -> list[str]:
    """Hide metrics for which this run contains no verified observation."""
    original_widths = [
        sheet.column_dimensions[get_column_letter(i)].width for i in range(1, sheet.max_column + 1)
    ]
    removed: list[str] = []
    kept: list[int] = []
    for col in range(1, sheet.max_column + 1):
        if any(sheet.cell(row, col).value is not None for row in range(2, sheet.max_row + 1)):
            kept.append(col)
        else:
            removed.append(str(sheet.cell(1, col).value))
    saved_rows = [
        [
            (
                sheet.cell(row, col).value,
                copy(sheet.cell(row, col)._style),
                copy(sheet.cell(row, col).hyperlink),
            )
            for col in kept
        ]
        for row in range(1, sheet.max_row + 1)
    ]
    sheet._cells.clear()
    for row_idx, cells in enumerate(saved_rows, 1):
        for col_idx, (value, style, hyperlink) in enumerate(cells, 1):
            cell = sheet.cell(row_idx, col_idx, value)
            cell._style = style
            if hyperlink:
                cell.hyperlink = hyperlink
    for new_col, old_col in enumerate(kept, 1):
        sheet.column_dimensions[get_column_letter(new_col)].width = original_widths[old_col - 1]
    for old_col in range(len(kept) + 1, len(original_widths) + 1):
        sheet.column_dimensions.pop(get_column_letter(old_col), None)
    if kept:
        sheet.auto_filter.ref = f"A1:{sheet.cell(1, len(kept)).coordinate}"
    for row in range(2, sheet.max_row + 1):
        for col in range(1, len(kept) + 1):
            cell = sheet.cell(row, col)
            if cell.value is None:
                cell.value = "N/A"
    return removed


def _pick_author_observation(
    observations: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Select one clearly attributed metric observation without blending counts."""
    priority = {"openalex": 0, "semantic_scholar": 1, "orcid": 2}
    available = [
        o
        for o in observations
        if o.get("enrichment_status") == "AVAILABLE" and isinstance(o.get("metrics"), dict)
    ]
    available.sort(key=lambda o: priority.get(str(o.get("provider") or ""), 99))
    if available:
        primary = available[0]
        others = [o for o in observations if o is not primary]
        return primary, others
    if observations:
        return observations[0], observations[1:]
    return None, []


def _format_affiliation(obs: dict[str, Any] | None, paper_affs: list[str]) -> str | None:
    if obs:
        curr = obs.get("current_affiliations") or []
        if curr and curr[0].get("institution"):
            yrs = [y for y in (curr[0].get("years") or []) if isinstance(y, int)]
            yr_note = f" (reported {max(yrs)})" if yrs else " (latest reported)"
            return f"{curr[0]['institution']}{yr_note}"
        affs = obs.get("affiliations") or []
        if affs and affs[0].get("institution"):
            return f"{affs[0]['institution']} (reported)"
    if paper_affs:
        return f"{paper_affs[0]} (paper metadata)"
    return None


def build_standard_workbook(run: dict[str, Any]) -> BytesIO:
    """Build the 5-sheet human-readable Standard Research Export."""
    book = Workbook()
    default_sheet = book.active
    if default_sheet is not None:
        book.remove(default_sheet)
    sheets = {name: book.create_sheet(name) for name in STANDARD_SHEETS}

    all_papers = run.get("papers") or []
    papers = [
        paper
        for paper in distinct_standard_papers(all_papers)
        if any(_valid_author_name(author) for author in paper.get("authors") or [])
    ]
    excluded_identity = len(all_papers) - len(papers)
    candidate_count = int(run.get("candidate_count") or len(all_papers))
    excluded_total = max(0, candidate_count - len(papers))
    topic = str((run.get("options") or {}).get("topic") or "Research Topic")
    disambig = run.get("query_disambiguation") or {}
    domain_label = str(disambig.get("resolved_domain") or "general").replace("_", " ").upper()
    retrieved_date = _short_date(run.get("retrieved_at"))
    ranking_year = int(retrieved_date[:4]) if retrieved_date[:4].isdigit() else date.today().year
    sort_meta = run.get("sort_metadata") or {}
    sort_label = sort_meta.get("label") or run.get("ordering") or "Relevance"
    sort_def = sort_meta.get("definition") or ""

    # Build deduplicated author & venue registries before Start Here so counts are exact
    obs_by_id: dict[str, dict[str, Any]] = {
        str(row["id"]): row for row in (run.get("author_observations") or []) if row.get("id")
    }
    authors_by_key: dict[str, dict[str, Any]] = {}
    name_to_keys: dict[str, set[str]] = {}
    venues_by_key: dict[str, dict[str, Any]] = {}

    for paper in papers:
        smeta = paper.get("source_metadata") or {}
        oa_ids = smeta.get("author_openalex_ids") or []
        s2_ids = smeta.get("author_s2_ids") or []
        valid_author_indices = [
            index
            for index, author in enumerate(paper.get("authors") or [])
            if _valid_author_name(author)
        ]
        paper_fields = [str(t) for t in (paper.get("topics") or [])[:2] if t]
        if paper.get("research_field"):
            paper_fields.insert(0, str(paper["research_field"]))
        for idx, author in enumerate(paper.get("authors") or []):
            if not _valid_author_name(author):
                continue
            key = author_key(paper, idx)
            norm_name = " ".join(str(author.get("name") or "").casefold().split())
            if norm_name:
                name_to_keys.setdefault(norm_name, set()).add(key)
            entry = authors_by_key.setdefault(
                key,
                {
                    "key": key,
                    "name": author.get("name") or "Unknown",
                    "orcids": set(),
                    "oa_ids": set(),
                    "s2_ids": set(),
                    "paper_affs": [],
                    "fields": [],
                    "obs": [],
                    "seen_obs_keys": set(),
                    "topic_papers": set(),
                    "first_author_papers": set(),
                    "last_author_papers": set(),
                    "best_relevance": None,
                },
            )
            entry["topic_papers"].add(str(paper.get("paper_id") or paper.get("title")))
            if idx == valid_author_indices[0]:
                entry["first_author_papers"].add(str(paper.get("paper_id") or paper.get("title")))
            if idx == valid_author_indices[-1]:
                entry["last_author_papers"].add(str(paper.get("paper_id") or paper.get("title")))
            paper_relevance = relevance_score(paper)
            if paper_relevance is not None:
                entry["best_relevance"] = max(entry["best_relevance"] or 0, paper_relevance)
            for pf in paper_fields:
                if pf and pf not in entry["fields"]:
                    entry["fields"].append(pf)
            if author.get("orcid"):
                entry["orcids"].add(str(author["orcid"]).strip())
            for inst in author.get("institutions") or []:
                if inst and inst not in entry["paper_affs"]:
                    entry["paper_affs"].append(inst)
            oa_id = oa_ids[idx] if idx < len(oa_ids) else None
            s2_id = s2_ids[idx] if idx < len(s2_ids) else None
            if oa_id:
                entry["oa_ids"].add(str(oa_id))
            if s2_id:
                entry["s2_ids"].add(str(s2_id))
            orcid_short = str(author.get("orcid") or "").rsplit("/", 1)[-1]
            for cand_id in (
                str(oa_id).rsplit("/", 1)[-1] if oa_id else None,
                f"s2:{s2_id}" if s2_id else None,
                f"orcid:{orcid_short}" if orcid_short else None,
            ):
                if cand_id and cand_id in obs_by_id and cand_id not in entry["seen_obs_keys"]:
                    entry["seen_obs_keys"].add(cand_id)
                    entry["obs"].append(obs_by_id[cand_id])

        vkey = venue_key(paper)
        if vkey:
            ventry = venues_by_key.setdefault(
                vkey,
                {"paper": paper, "papers": [], "topics": set()},
            )
            ventry["papers"].append(paper)
            current_metrics = comparable_venue_metrics(ventry["paper"].get("venue_details") or {})
            candidate_metrics = comparable_venue_metrics(paper.get("venue_details") or {})
            if sum(value is not None for value in candidate_metrics.values()) > sum(
                value is not None for value in current_metrics.values()
            ):
                ventry["paper"] = paper
            for t in (paper.get("topics") or [])[:3]:
                if t:
                    ventry["topics"].add(str(t))

    # Collect contributing live discovery vs enrichment source labels
    discovery_sources = sorted(
        {
            lbl
            for paper in papers
            for p in (paper.get("provenance") or [])
            if str(p.get("contribution_type") or "discovery").startswith("discovery")
            and (lbl := _provider_label(p.get("source_type")))
        }
    )
    enrichment_sources = sorted(
        (
            {
                lbl
                for paper in papers
                for p in (paper.get("provenance") or [])
                if str(p.get("contribution_type") or "") == "stage2_enrichment"
                and (lbl := _provider_label(p.get("source_type")))
            }
            | {
                lbl
                for o in (run.get("author_observations") or [])
                if o.get("enrichment_status") == "AVAILABLE"
                and (lbl := _provider_label(o.get("provider")))
            }
        )
        - set(discovery_sources)
    )
    source_cov_parts = []
    if discovery_sources:
        source_cov_parts.append(f"Discovery: {', '.join(discovery_sources)}")
    if enrichment_sources:
        source_cov_parts.append(f"Enrichment: {', '.join(enrichment_sources)}")
    source_cov_str = " | ".join(source_cov_parts) or "No verified source coverage"

    # Coverage stats for optional fields
    n_papers = len(papers)
    n_cit = sum(1 for p in papers if isinstance(p.get("citation_count"), int))
    n_methods = sum(1 for p in papers if _clean_list_field(p.get("methods")))
    n_datasets = sum(1 for p in papers if _clean_list_field(p.get("datasets")))
    n_metrics = sum(1 for p in papers if _clean_list_field(p.get("evaluation_metrics")))
    omitted_cols: list[str] = []
    if n_papers > 0:
        if n_methods == 0:
            omitted_cols.append("Research method")
        if n_datasets == 0:
            omitted_cols.append("Dataset / benchmark")
        if n_metrics == 0:
            omitted_cols.append("Evaluation metric")
    coverage_summary = (
        f"Citations: {n_cit}/{n_papers}; Methods: {n_methods}/{n_papers}; "
        f"Datasets: {n_datasets}/{n_papers}; Metrics: {n_metrics}/{n_papers}"
    )
    if omitted_cols:
        coverage_summary += (
            f" (Empty optional columns omitted from Papers: {', '.join(omitted_cols)})"
        )

    # ------------------------------------------------------------------
    # Sheet 1: Start Here
    # ------------------------------------------------------------------
    sh = sheets["Start Here"]
    sh.views.sheetView[0].showGridLines = True
    sh.column_dimensions["A"].width = 30
    sh.column_dimensions["B"].width = 80

    sh.append(["Archipelago Research Report", ""])
    sh["A1"].font = TITLE_FONT
    sh.row_dimensions[1].height = 28
    sh.append(["Prepared for students, educators, and librarians", ""])
    sh["A2"].font = BODY_FONT
    sh.append(["", ""])

    summary_rows = [
        ("Search query", topic),
        ("Topic / domain", domain_label),
        ("Retrieval date", retrieved_date or "Not recorded"),
        ("Discovery candidates", candidate_count),
        ("Valid papers included", n_papers),
        (
            "Excluded (filtered / incomplete)",
            f"{excluded_total} (including {excluded_identity} lacking core IDs)"
            if excluded_identity
            else excluded_total,
        ),
        ("Distinct researchers", len(authors_by_key)),
        ("Publications / venues", len(venues_by_key)),
        ("Ordering method", f"{sort_label} — {sort_def}" if sort_def else sort_label),
        ("Source coverage", source_cov_str),
        ("Google Scholar review", run.get("google_scholar_url") or ""),
        ("Optional field coverage", coverage_summary),
        ("Export mode", "Standard Research Export (5 sheets)"),
    ]
    sh.append(["Summary", "Details"])
    for c in sh[4]:
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.border = THIN_BORDER
    for label, val in summary_rows:
        sh.append([label, _safe_cell(val)])
        r = sh.max_row
        sh.cell(r, 1).font = Font(name=FONT_FAMILY, size=10, bold=True, color="1A1A1A")
        sh.cell(r, 2).font = BODY_FONT
        sh.cell(r, 1).border = THIN_BORDER
        sh.cell(r, 2).border = THIN_BORDER
        sh.cell(r, 2).alignment = Alignment(wrap_text=True, vertical="top")
        if label == "Google Scholar review" and val:
            _set_link(sh.cell(r, 2), str(val), "Open Google Scholar")

    sh.append(["", ""])
    sh.append(["How to use this workbook", "Sheet contents"])
    for c in sh[sh.max_row]:
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.border = THIN_BORDER
    guide_rows = [
        (
            "Papers",
            "One row per valid paper. Filter or sort relevance, citations, citations/year, FWCI, percentile, year, and evidence independently.",
        ),
        (
            "Authors",
            "One row per verified researcher identity. Independent publication, citation, h-index, i10, recent-citation, and topic-paper fields.",
        ),
        (
            "Publications",
            "One row per venue. Journal, conference, and repository categories remain separate; only verified venue metrics are populated.",
        ),
        (
            "Sources",
            "Readable provenance per paper and provider: source name, URL, Discovery vs Enrichment role, retrieval date, and verification status.",
        ),
    ]
    for tab, desc in guide_rows:
        sh.append([tab, desc])
        r = sh.max_row
        sh.cell(r, 1).font = Font(name=FONT_FAMILY, size=10, bold=True, color="1F4E78")
        sh.cell(r, 2).font = BODY_FONT
        sh.cell(r, 1).border = THIN_BORDER
        sh.cell(r, 2).border = THIN_BORDER
        sh.cell(r, 2).alignment = Alignment(wrap_text=True, vertical="top")

    sh.append(["", ""])
    sh.append(["Notes & limitations", ""])
    sh.cell(sh.max_row, 1).font = SUBTITLE_FONT
    notes = [
        "N/A means the consulted databases did not report that value. Missing counts are never converted to zero; wholly unavailable columns are omitted.",
        "Citation counts reflect a single attributed database (with observation provider); Citations/year = citations / max(1, current_year - year + 1).",
        "Methods, datasets, and evaluation metrics are extracted strictly from verified abstracts and structured metadata.",
        "Author rows are merged only when verified by persistent identifiers (ORCID, OpenAlex, or Semantic Scholar).",
        "Ranking fields are independent sortable observations, not a composite quality score. Provider names identify the metric source.",
        "OpenAlex 2-year mean citedness is not Clarivate JIF. Licensed venue metrics are omitted when no verified values exist.",
        "Recent author citations cover five calendar years including the retrieval year; topic-paper counts cover this export only.",
    ]
    for note in notes:
        sh.append(["Note", note])
        r = sh.max_row
        sh.cell(r, 1).font = Font(name=FONT_FAMILY, size=10, bold=True, color="595959")
        sh.cell(r, 2).font = BODY_FONT
        sh.cell(r, 2).alignment = Alignment(wrap_text=True, vertical="top")
        sh.row_dimensions[r].height = 28

    # ------------------------------------------------------------------
    # Sheet 2: Papers
    # ------------------------------------------------------------------
    papers_sh = sheets["Papers"]
    include_methods = n_papers == 0 or n_methods > 0
    include_datasets = n_papers == 0 or n_datasets > 0
    include_metrics = n_papers == 0 or n_metrics > 0

    col_specs: list[tuple[str, int, bool, str | None]] = [
        ("Paper title", 44, True, None),
        ("Authors", 30, True, None),
        ("Year", 10, False, "0"),
        ("Publication venue", 28, True, None),
        ("Publication type", 18, False, None),
        ("Citation count", 14, False, "#,##0"),
        ("Citations per year", 16, False, "0.00"),
        ("Citation source", 18, False, None),
        ("Topic relevance", 20, False, None),
        ("Relevance score (0-1)", 18, False, "0.000"),
        ("FWCI (OpenAlex)", 17, False, "0.00"),
        ("Citation percentile (OpenAlex)", 23, False, "0.0%"),
        ("Influential citations (Semantic Scholar)", 24, False, "#,##0"),
        ("Indexed references", 17, False, "#,##0"),
        ("Benchmark performance", 27, True, None),
    ]
    if include_methods:
        col_specs.append(("Research method", 26, True, None))
    if include_datasets:
        col_specs.append(("Dataset / benchmark", 24, True, None))
    if include_metrics:
        col_specs.append(("Evaluation metric", 22, True, None))
    col_specs.extend(
        [
            ("Open access", 12, False, None),
            ("DOI", 26, False, None),
            ("Paper link", 16, False, None),
            ("Verified sources", 28, True, None),
            ("Method evidence", 18, False, None),
            ("Code link available", 18, False, None),
            ("Data link available", 18, False, None),
            ("Checkpoint link available", 20, False, None),
            ("Experimental details available", 25, False, None),
        ]
    )

    papers_headers = [c[0] for c in col_specs]
    papers_widths = [c[1] for c in col_specs]
    papers_wrap = {i for i, c in enumerate(col_specs, 1) if c[2]}
    papers_num = {i: c[3] for i, c in enumerate(col_specs, 1) if c[3]}
    doi_col_idx = papers_headers.index("DOI") + 1
    link_col_idx = papers_headers.index("Paper link") + 1

    _init_data_sheet(papers_sh, papers_headers, papers_widths)
    for paper in papers:
        authors_str = "; ".join(
            a.get("name") or "" for a in (paper.get("authors") or []) if _valid_author_name(a)
        )
        doi = paper.get("doi")
        doi_url = f"https://doi.org/{doi}" if doi else None
        paper_url = paper.get("url") or paper.get("oa_url") or doi_url
        verified_sources = ", ".join(
            sorted(
                {
                    lbl
                    for p in (paper.get("provenance") or [])
                    if (lbl := _provider_label(p.get("source_type")))
                }
            )
        )
        oa_val = (
            "Yes"
            if paper.get("is_open_access") is True
            else ("No" if paper.get("is_open_access") is False else None)
        )
        cit_count = paper.get("citation_count")
        cit_py = paper.get("citations_per_year")
        cit_prov = (
            _provider_label(paper.get("citation_provider")) if cit_count is not None else None
        )
        year_val = paper.get("year")
        if (
            year_val is None
            and isinstance(paper.get("publication_date"), str)
            and paper["publication_date"][:4].isdigit()
        ):
            year_val = int(paper["publication_date"][:4])
        row_vals: list[Any] = [
            _safe_cell(paper.get("title")),
            _safe_cell(authors_str or None),
            year_val,
            _safe_cell(paper.get("venue")),
            _safe_cell(_clean_human_type(paper.get("publication_type"))),
            cit_count,
            cit_py,
            _safe_cell(cit_prov),
            _safe_cell(_format_relevance(paper.get("relevance_classification"))),
            relevance_score(paper),
            nonnegative_number(paper.get("fwci")),
            openalex_citation_percentile(paper),
            nonnegative_number(paper.get("influential_citations")),
            len(paper["references"]) if paper.get("references") else None,
            None,
        ]
        if include_methods:
            row_vals.append(_safe_cell(_clean_list_field(paper.get("methods"))))
        if include_datasets:
            row_vals.append(_safe_cell(_clean_list_field(paper.get("datasets"))))
        if include_metrics:
            row_vals.append(_safe_cell(_clean_list_field(paper.get("evaluation_metrics"))))
        row_vals.extend(
            [
                oa_val,
                _safe_cell(doi),
                _safe_cell(paper_url),
                _safe_cell(verified_sources or None),
                "Yes" if paper.get("methods") else None,
                "Yes" if paper.get("code_repo_urls") else None,
                "Yes" if paper.get("dataset_repo_urls") else None,
                "Yes" if paper.get("checkpoint_urls") else None,
                "Yes" if paper.get("experimental_details_url") else None,
            ]
        )
        papers_sh.append(row_vals)
        r = papers_sh.max_row
        if doi_url:
            _set_link(papers_sh.cell(r, doi_col_idx), doi_url, doi)
        if paper_url:
            _set_link(papers_sh.cell(r, link_col_idx), paper_url, "Open paper")

    _style_data_sheet(
        papers_sh,
        papers_headers,
        widths=papers_widths,
        wrap_cols=papers_wrap,
        int_cols=papers_num,
    )

    # ------------------------------------------------------------------
    # Sheet 3: Authors
    # ------------------------------------------------------------------
    authors_sh = sheets["Authors"]
    authors_headers = [
        "Author name",
        "Verified affiliations",
        "ORCID",
        "Publication count",
        "Citation count",
        "h-index",
        "Research field",
        "Profile URL",
        "Verified sources",
        "i10-index",
        "Avg citations / work",
        "Recent citations (5y)",
        "m-quotient",
        "Topic papers in export",
        "Best paper relevance (0-1)",
        "Metric provider",
        "g-index",
        "Median citations / work",
        "Field-normalized impact",
        "First-author papers in export",
        "Last-author papers in export",
        "Verified collaborators in export",
    ]
    authors_widths = [
        26,
        36,
        22,
        16,
        15,
        11,
        28,
        16,
        24,
        12,
        20,
        21,
        13,
        22,
        24,
        18,
        12,
        23,
        22,
        27,
        27,
        31,
    ]
    _init_data_sheet(authors_sh, authors_headers, authors_widths)
    for entry in authors_by_key.values():
        primary_obs, other_obs = _pick_author_observation(entry["obs"])
        metrics = (primary_obs or {}).get("metrics") or {}
        avail = (primary_obs or {}).get("enrichment_status") == "AVAILABLE"
        pub_count = metrics.get("publication_count") if avail else None
        cit_count = metrics.get("citation_count") if avail else None
        h_index = metrics.get("h_index") if avail else None
        metric_src = _provider_label((primary_obs or {}).get("provider")) if avail else None

        display_name = (primary_obs or {}).get("name") or entry["name"]
        aff_str = _format_affiliation(primary_obs, entry["paper_affs"])

        orcid_val = next(iter(sorted(entry["orcids"])), None) or (primary_obs or {}).get("orcid")
        orcid_short = str(orcid_val).rsplit("/", 1)[-1] if orcid_val else None
        orcid_url = f"https://orcid.org/{orcid_short}" if orcid_short else None

        profile_url = (primary_obs or {}).get("source_url")
        if not profile_url and entry["oa_ids"]:
            oa_s = next(iter(sorted(entry["oa_ids"]))).rsplit("/", 1)[-1]
            profile_url = f"https://openalex.org/{oa_s}"
        if not profile_url and entry["s2_ids"]:
            s2_s = next(iter(sorted(entry["s2_ids"])))
            profile_url = f"https://www.semanticscholar.org/author/{s2_s}"

        obs_fields = (primary_obs or {}).get("fields") or []
        research_field = _clean_list_field(obs_fields[:3] if obs_fields else entry["fields"][:3])

        all_sources = sorted(
            {
                lbl
                for o in ([primary_obs] if primary_obs else []) + list(other_obs)
                if (lbl := _provider_label(o.get("provider")))
            }
            | ({metric_src} if metric_src else set())
            | (
                {"ORCID"}
                if orcid_url and any(o.get("orcid_verified") for o in entry["obs"])
                else set()
            )
        )

        authors_sh.append(
            [
                _safe_cell(display_name),
                _safe_cell(aff_str),
                _safe_cell(orcid_url),
                pub_count,
                cit_count,
                h_index,
                _safe_cell(research_field),
                _safe_cell(profile_url),
                _safe_cell(", ".join(all_sources) or None),
                nonnegative_number(metrics.get("i10_index")) if avail else None,
                author_average_citations(metrics) if avail else None,
                author_recent_citations(metrics, ranking_year)
                if avail and metric_src == "OpenAlex"
                else None,
                author_m_quotient(metrics, ranking_year)
                if avail and metric_src == "OpenAlex"
                else None,
                len(entry["topic_papers"]),
                entry["best_relevance"],
                _safe_cell(metric_src),
                None,
                None,
                None,
                len(entry["first_author_papers"]),
                len(entry["last_author_papers"]),
                None,
            ]
        )
        r = authors_sh.max_row
        if orcid_url:
            _set_link(authors_sh.cell(r, 3), orcid_url, orcid_short)
        if profile_url:
            _set_link(authors_sh.cell(r, 8), profile_url, "View profile")

    _style_data_sheet(
        authors_sh,
        authors_headers,
        widths=authors_widths,
        wrap_cols={1, 2, 7, 9},
        int_cols={
            4: "#,##0",
            5: "#,##0",
            6: "0",
            10: "0",
            11: "0.00",
            12: "#,##0",
            13: "0.00",
            14: "#,##0",
            15: "0.000",
            20: "#,##0",
            21: "#,##0",
        },
    )

    # ------------------------------------------------------------------
    # Sheet 4: Publications
    # ------------------------------------------------------------------
    pubs_sh = sheets["Publications"]
    pubs_headers = [
        "Venue name",
        "Category",
        "Publisher",
        "Official link",
        "Covered paper count",
        "Verified available metrics",
        "Indexed works (OpenAlex)",
        "Indexed citations (OpenAlex)",
        "Venue h-index (OpenAlex)",
        "Venue i10-index (OpenAlex)",
        "2-year mean citedness (OpenAlex)",
        "JIF (Clarivate)",
        "CiteScore (Scopus)",
        "SJR (SCImago)",
        "SNIP",
        "Journal quartile",
        "CORE / ICORE rank",
        "Acceptance rate",
        "Venue metric provider",
        "h5-index",
        "h5-median",
        "Indexed status (OpenAlex)",
    ]
    pubs_widths = [
        38,
        24,
        28,
        18,
        18,
        36,
        22,
        24,
        22,
        24,
        27,
        18,
        20,
        18,
        14,
        18,
        20,
        18,
        22,
        14,
        14,
        26,
    ]
    _init_data_sheet(pubs_sh, pubs_headers, pubs_widths)
    for ventry in venues_by_key.values():
        paper = ventry["paper"]
        det = paper.get("venue_details") or {}
        vcat = str(det.get("venue_category") or "unknown")
        vtype_label = VENUE_CATEGORY_LABELS.get(vcat, "Unverified")
        v_url = det.get("url")
        rank_metrics = comparable_venue_metrics(det)
        metric_parts: list[str] = []
        if det.get("issn"):
            metric_parts.append(f"ISSN: {det['issn']}")
        if det.get("is_oa") is True:
            metric_parts.append("Open-access venue")
        if rank_metrics["works_count"] is not None:
            metric_parts.append(f"Indexed works: {rank_metrics['works_count']:,}")
        if rank_metrics["cited_by_count"] is not None:
            metric_parts.append(f"Total citations: {rank_metrics['cited_by_count']:,}")
        v_prov = _provider_label(det.get("provider"))
        if metric_parts and v_prov:
            metric_parts.append(f"Source: {v_prov}")
        pubs_sh.append(
            [
                _safe_cell(paper.get("venue")),
                _safe_cell(vtype_label),
                _safe_cell(det.get("publisher")),
                _safe_cell(v_url),
                len(ventry["papers"]),
                _safe_cell("; ".join(metric_parts) or None),
                rank_metrics["works_count"],
                rank_metrics["cited_by_count"],
                rank_metrics["h_index"],
                rank_metrics["i10_index"],
                rank_metrics["openalex_2yr_mean_citedness"],
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                _safe_cell(v_prov if rank_metrics["works_count"] is not None else None),
                None,
                None,
                "Yes" if rank_metrics["works_count"] is not None else None,
            ]
        )
        r = pubs_sh.max_row
        if v_url:
            _set_link(pubs_sh.cell(r, 4), v_url, "Official website")

    _style_data_sheet(
        pubs_sh,
        pubs_headers,
        widths=pubs_widths,
        wrap_cols={1, 3, 6},
        int_cols={5: "#,##0", 7: "#,##0", 8: "#,##0", 9: "0", 10: "0", 11: "0.00"},
    )

    # ------------------------------------------------------------------
    # Sheet 5: Sources
    # ------------------------------------------------------------------
    sources_sh = sheets["Sources"]
    sources_headers = [
        "Paper title",
        "Source name",
        "Source URL",
        "Discovery vs Enrichment",
        "Retrieved date",
        "Verification status",
    ]
    sources_widths = [46, 20, 22, 22, 14, 22]
    _init_data_sheet(sources_sh, sources_headers, sources_widths)
    for paper in papers:
        title = paper.get("title")
        seen_prov_rows: set[tuple[str, str]] = set()
        for p in paper.get("provenance") or []:
            stype = str(p.get("source_type") or "").casefold()
            sname = _provider_label(stype)
            if not sname:
                continue
            ctype = str(p.get("contribution_type") or "discovery")
            role = "Enrichment" if ctype == "stage2_enrichment" else "Discovery"
            dedup_key = (stype, role)
            if dedup_key in seen_prov_rows:
                continue
            seen_prov_rows.add(dedup_key)
            surl = p.get("source_url")
            if not (isinstance(surl, str) and surl.startswith(("https://", "http://"))):
                surl = f"https://doi.org/{paper['doi']}" if paper.get("doi") else None
            rdate = _short_date(
                p.get("fetched_at") or paper.get("retrieved_at") or run.get("retrieved_at")
            )
            vstatus = (
                "Verified record"
                if p.get("source_record_id") or p.get("artifact_sha256")
                else "Referenced"
            )
            sources_sh.append(
                [
                    _safe_cell(title),
                    _safe_cell(sname),
                    _safe_cell(surl),
                    role,
                    rdate or None,
                    vstatus,
                ]
            )
            r = sources_sh.max_row
            if surl:
                _set_link(sources_sh.cell(r, 3), surl, f"View on {sname}")

    _style_data_sheet(
        sources_sh,
        sources_headers,
        widths=sources_widths,
        wrap_cols={1},
        int_cols={},
    )

    for ranking_sheet in (papers_sh, authors_sh, pubs_sh):
        _remove_empty_metric_columns(ranking_sheet)

    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output
