"""Multi-Paper Parameter Comparison Matrix Engine.

Generates structured comparison tables across extracted parameters:
experimental rigor, reported metrics, datasets, reproducibility, and evidence provenance.
"""

from __future__ import annotations

from typing import Any

from archipelago.scholarly.contracts.okf_models import OKFPaperRecord


class ParameterComparisonEngine:
    """Generates structured cross-paper parameter comparison matrices."""

    def build_comparison_matrix(self, okf_records: list[OKFPaperRecord]) -> dict[str, Any]:
        """Produce a side-by-side comparison matrix across all ingested papers."""
        rows = []
        for rec in okf_records:
            paper = rec.paper

            # Feature lookup
            feat_map = {f.feature_name: f.value for f in rec.features}

            # Datasets
            ds_names = [d.name for d in rec.datasets]
            ds_str = ", ".join(ds_names) if ds_names else "Not reported"

            # Results / Metrics
            metric_strs = []
            for res in rec.results:
                m_str = f"{res.metric_name}: {res.metric_value}{res.metric_unit or ''}"
                if m_str not in metric_strs:
                    metric_strs.append(m_str)
            metrics_display = "; ".join(metric_strs[:3]) if metric_strs else "Qualitative only"

            # Code URL
            code_url = feat_map.get("code_url")
            code_display = (
                code_url if code_url else ("Available" if feat_map.get("code_available") else "No")
            )

            # Ablation & Error analysis
            ablation = (
                "Yes"
                if feat_map.get("ablation_present") is True
                else ("No" if feat_map.get("ablation_present") is False else "Unknown")
            )
            error_analysis = (
                "Yes"
                if feat_map.get("error_analysis_present") is True
                else ("No" if feat_map.get("error_analysis_present") is False else "Unknown")
            )

            rows.append(
                {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "year": paper.publication_date[:4] if paper.publication_date else "N/A",
                    "venue": paper.venue or "Preprint",
                    "citations": feat_map.get("citation_count", 0),
                    "datasets": ds_str,
                    "metrics_reported": metrics_display,
                    "ablation_study": ablation,
                    "error_analysis": error_analysis,
                    "code_available": code_display,
                    "evidence_coverage": f"{int(rec.quality.get('evidence_coverage', 1.0) * 100)}%",
                    "pdf_url": paper.oa_url
                    or (
                        f"https://arxiv.org/pdf/{paper.identifiers.arxiv_id}.pdf"
                        if paper.identifiers.arxiv_id
                        else None
                    ),
                    "doi": paper.identifiers.doi,
                }
            )

        return {
            "num_papers": len(rows),
            "comparison_table": rows,
        }

    def format_markdown_table(self, matrix: dict[str, Any]) -> str:
        """Format comparison table into clear Markdown."""
        rows = matrix.get("comparison_table", [])
        if not rows:
            return "No papers to compare."

        md = "| Title | Year | Venue | Citations | Datasets Evaluated | Top Metrics | Ablation? | Code? | Evidence % |\n"
        md += "| :--- | :---: | :--- | :---: | :--- | :--- | :---: | :--- | :---: |\n"

        for r in rows:
            title_short = r["title"][:45] + "..." if len(r["title"]) > 48 else r["title"]
            md += f"| **{title_short}** | {r['year']} | {r['venue']} | {r['citations']} | {r['datasets']} | {r['metrics_reported']} | {r['ablation_study']} | {r['code_available']} | {r['evidence_coverage']} |\n"

        return md
