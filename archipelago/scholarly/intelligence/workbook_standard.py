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

from datetime import date
from io import BytesIO
import math
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .graph import author_key, venue_key

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


def _safe_cell(value: Any) -> Any:
    """Prevent spreadsheet formula execution from untrusted metadata."""
    if value is None or isinstance(value, (int, float, bool, date)):
        return value
    text = str(value)[:MAX_CELL_CHARS]
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


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
                lines = sum(max(1, math.ceil(len(part) / col_w)) for part in cell.value.splitlines() or [""])
                max_lines = max(max_lines, min(lines, 12))
        sheet.row_dimensions[row_idx].height = max(20, max_lines * 14.5 + 6)


def _set_link(cell: Any, url: str | None, display_text: str | None = None) -> None:
    if not url or not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return
    if display_text is not None:
        cell.value = _safe_cell(display_text)
    cell.hyperlink = url
    cell.font = LINK_FONT


def _pick_author_observation(
    observations: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Select one clearly attributed metric observation without blending counts."""
    priority = {"openalex": 0, "semantic_scholar": 1, "orcid": 2}
    available = [
        o for o in observations
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

    papers = run.get("papers") or []
    topic = str((run.get("options") or {}).get("topic") or "Research Topic")
    retrieved_date = _short_date(run.get("retrieved_at"))
    sort_meta = run.get("sort_metadata") or {}
    sort_label = sort_meta.get("label") or run.get("ordering") or "Relevance"

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
        for idx, author in enumerate(paper.get("authors") or []):
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
                    "obs": [],
                    "seen_obs_keys": set(),
                },
            )
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
            for t in (paper.get("topics") or [])[:3]:
                if t:
                    ventry["topics"].add(str(t))

    # Collect contributing live source labels
    contributing_sources = sorted(
        {
            _provider_label(p.get("source_type"))
            for paper in papers
            for p in (paper.get("provenance") or [])
            if _provider_label(p.get("source_type"))
        }
        | {
            _provider_label(o.get("provider"))
            for o in (run.get("citation_observations") or [])
            if _provider_label(o.get("provider"))
        }
        | {
            _provider_label(o.get("provider"))
            for o in (run.get("author_observations") or [])
            if o.get("enrichment_status") == "AVAILABLE" and _provider_label(o.get("provider"))
        }
    )

    # ------------------------------------------------------------------
    # Sheet 1: Start Here
    # ------------------------------------------------------------------
    sh = sheets["Start Here"]
    sh.views.sheetView[0].showGridLines = True
    sh.column_dimensions["A"].width = 28
    sh.column_dimensions["B"].width = 78

    sh.append(["Archipelago Research Report", ""])
    sh["A1"].font = TITLE_FONT
    sh.row_dimensions[1].height = 28
    sh.append(["Prepared for students, educators, and librarians", ""])
    sh["A2"].font = BODY_FONT
    sh.append(["", ""])

    summary_rows = [
        ("Research topic", topic),
        ("Collected on", retrieved_date or "Not recorded"),
        ("Papers included", len(papers)),
        ("Distinct researchers", len(authors_by_key)),
        ("Publications / venues", len(venues_by_key)),
        ("Sorted by", sort_label),
        ("Sources consulted", ", ".join(contributing_sources) or "OpenAlex"),
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

    sh.append(["", ""])
    sh.append(["How to use this workbook", "Sheet contents"])
    for c in sh[sh.max_row]:
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.border = THIN_BORDER
    guide_rows = [
        ("Papers", "Bibliographic details, abstracts, citation counts, open-access status, and direct links."),
        ("Authors", "Deduplicated researchers with affiliations, publication/citation metrics, and ORCID links."),
        ("Publications", "Journals, conferences, and repositories where these papers appeared."),
        ("Sources", "Direct links to each scholarly database that verified each paper."),
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
    sh.append(["Notes on reading this export", ""])
    sh.cell(sh.max_row, 1).font = SUBTITLE_FONT
    notes = [
        "Blank metric cells mean the consulted databases did not report that value. Missing values are never replaced with zero.",
        "Citation counts reflect a single attributed database (shown in 'Citation source') rather than blending counts across sources.",
        "Researcher rows are merged only when verified by persistent identifiers (ORCID, OpenAlex, or Semantic Scholar); same-name researchers without shared IDs are kept separate.",
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
    papers_headers = [
        "Paper title", "Authors", "Publication year", "Journal/conference",
        "Paper type", "Citation count", "Citation source", "Open access",
        "DOI", "Paper link", "Indexed by", "Abstract",
    ]
    papers_widths = [44, 30, 14, 28, 18, 14, 18, 12, 26, 16, 30, 56]
    _init_data_sheet(papers_sh, papers_headers, papers_widths)
    for paper in papers:
        authors_str = "; ".join(a.get("name") or "" for a in (paper.get("authors") or []) if a.get("name"))
        doi = paper.get("doi")
        doi_url = f"https://doi.org/{doi}" if doi else None
        paper_url = paper.get("url") or paper.get("oa_url") or doi_url
        indexed_by = ", ".join(
            sorted(
                {
                    lbl
                    for p in (paper.get("provenance") or [])
                    if (lbl := _provider_label(p.get("source_type")))
                }
            )
        )
        oa_val = "Yes" if paper.get("is_open_access") is True else ("No" if paper.get("is_open_access") is False else None)
        cit_count = paper.get("citation_count")
        cit_prov = _provider_label(paper.get("citation_provider")) if cit_count is not None else None
        abstract = paper.get("abstract") or ""
        if len(abstract) > 1200:
            abstract = abstract[:1197].rstrip() + "..."
        papers_sh.append(
            [
                _safe_cell(paper.get("title")),
                _safe_cell(authors_str or None),
                paper.get("year"),
                _safe_cell(paper.get("venue")),
                _safe_cell(_clean_human_type(paper.get("publication_type"))),
                cit_count,
                _safe_cell(cit_prov),
                oa_val,
                _safe_cell(doi),
                _safe_cell(paper_url),
                _safe_cell(indexed_by or None),
                _safe_cell(abstract or None),
            ]
        )
        r = papers_sh.max_row
        if doi_url:
            _set_link(papers_sh.cell(r, 9), doi_url, doi)
        if paper_url:
            _set_link(papers_sh.cell(r, 10), paper_url, "Open paper")

    _style_data_sheet(
        papers_sh,
        papers_headers,
        widths=[44, 30, 14, 28, 18, 14, 18, 12, 26, 16, 30, 56],
        wrap_cols={1, 2, 4, 11, 12},
        int_cols={3: "0", 6: "#,##0"},
    )

    # ------------------------------------------------------------------
    # Sheet 3: Authors
    # ------------------------------------------------------------------
    authors_sh = sheets["Authors"]
    authors_headers = [
        "Author name", "Affiliation (latest / reported)", "Indexed publications",
        "Citation count", "h-index", "Metric source", "ORCID profile",
        "Researcher profile", "Other verified sources", "Identity verification note",
    ]
    authors_widths = [26, 36, 18, 15, 11, 18, 22, 16, 24, 38]
    _init_data_sheet(authors_sh, authors_headers, authors_widths)
    collisions = set(run.get("author_collisions") or [])
    for key, entry in authors_by_key.items():
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

        other_sources = sorted(
            {
                lbl
                for o in other_obs
                if (lbl := _provider_label(o.get("provider"))) and lbl != metric_src
            }
        )
        if orcid_url and metric_src != "ORCID" and "ORCID" not in other_sources and any(
            o.get("orcid_verified") for o in entry["obs"]
        ):
            other_sources.append("ORCID")

        # Identity verification note (only when helpful/needed)
        notes_parts: list[str] = []
        alt_names = {
            str(o.get("name")).strip()
            for o in entry["obs"]
            if o.get("name") and str(o.get("name")).strip().casefold() != str(display_name).strip().casefold()
        }
        if alt_names:
            notes_parts.append(f"Also listed as: {', '.join(sorted(alt_names))}")
        norm_disp = " ".join(str(display_name).casefold().split())
        if norm_disp in collisions or len(name_to_keys.get(norm_disp, ())) > 1:
            notes_parts.append("Multiple researchers share this name; kept separate by verified ID")
        elif key.startswith("author-unverified:"):
            notes_parts.append("Name-only entry; no persistent researcher ID")

        authors_sh.append(
            [
                _safe_cell(display_name),
                _safe_cell(aff_str),
                pub_count,
                cit_count,
                h_index,
                _safe_cell(metric_src),
                _safe_cell(orcid_url),
                _safe_cell(profile_url),
                _safe_cell(", ".join(other_sources) or None),
                _safe_cell("; ".join(notes_parts) or None),
            ]
        )
        r = authors_sh.max_row
        if orcid_url:
            _set_link(authors_sh.cell(r, 7), orcid_url, orcid_short)
        if profile_url:
            _set_link(authors_sh.cell(r, 8), profile_url, "View profile")

    _style_data_sheet(
        authors_sh,
        authors_headers,
        widths=[26, 36, 18, 15, 11, 18, 22, 16, 24, 38],
        wrap_cols={1, 2, 9, 10},
        int_cols={3: "#,##0", 4: "#,##0", 5: "0"},
    )

    # ------------------------------------------------------------------
    # Sheet 4: Publications
    # ------------------------------------------------------------------
    pubs_sh = sheets["Publications"]
    pubs_headers = [
        "Publication / venue name", "Publication type", "Publisher",
        "Research areas", "Official website", "Metadata source",
    ]
    pubs_widths = [38, 24, 28, 38, 20, 18]
    _init_data_sheet(pubs_sh, pubs_headers, pubs_widths)
    for ventry in venues_by_key.values():
        paper = ventry["paper"]
        det = paper.get("venue_details") or {}
        vcat = str(det.get("venue_category") or "unknown")
        vtype_label = VENUE_CATEGORY_LABELS.get(vcat, "Unverified")
        v_url = det.get("url")
        v_prov = _provider_label(det.get("provider"))
        pubs_sh.append(
            [
                _safe_cell(paper.get("venue")),
                _safe_cell(vtype_label),
                _safe_cell(det.get("publisher")),
                _safe_cell(", ".join(sorted(ventry["topics"])) or None),
                _safe_cell(v_url),
                _safe_cell(v_prov),
            ]
        )
        r = pubs_sh.max_row
        if v_url:
            _set_link(pubs_sh.cell(r, 5), v_url, "Official website")

    _style_data_sheet(
        pubs_sh,
        pubs_headers,
        widths=[38, 24, 28, 38, 20, 18],
        wrap_cols={1, 3, 4},
        int_cols={},
    )

    # ------------------------------------------------------------------
    # Sheet 5: Sources
    # ------------------------------------------------------------------
    sources_sh = sheets["Sources"]
    source_cols = ["openalex", "crossref", "semantic_scholar", "openaire", "datacite", "arxiv"]
    sources_headers = ["Paper title", "DOI"] + [PROVIDER_LABELS[s] for s in source_cols]
    sources_widths = [46, 26, 18, 18, 22, 18, 18, 16]
    _init_data_sheet(sources_sh, sources_headers, sources_widths)
    for paper in papers:
        doi = paper.get("doi")
        doi_url = f"https://doi.org/{doi}" if doi else None
        prov_urls: dict[str, str] = {}
        for p in paper.get("provenance") or []:
            stype = str(p.get("source_type") or "").casefold()
            surl = p.get("source_url")
            if stype in source_cols and isinstance(surl, str) and surl.startswith(("https://", "http://")):
                prov_urls.setdefault(stype, surl)
        row_vals: list[Any] = [_safe_cell(paper.get("title")), _safe_cell(doi)]
        for sc in source_cols:
            row_vals.append(_safe_cell(prov_urls.get(sc)))
        sources_sh.append(row_vals)
        r = sources_sh.max_row
        if doi_url:
            _set_link(sources_sh.cell(r, 2), doi_url, doi)
        for idx, sc in enumerate(source_cols, 3):
            if sc in prov_urls:
                _set_link(sources_sh.cell(r, idx), prov_urls[sc], f"View on {PROVIDER_LABELS[sc]}")

    _style_data_sheet(
        sources_sh,
        sources_headers,
        widths=[46, 26, 18, 18, 22, 18, 18, 16],
        wrap_cols={1},
        int_cols={},
    )

    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output
