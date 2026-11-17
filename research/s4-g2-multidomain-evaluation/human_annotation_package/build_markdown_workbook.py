"""Generate clean markdown workbook from CSV pool."""

import csv
from pathlib import Path

csv_path = Path(__file__).parent / "multidomain_human_annotation_pool.csv"
md_path = Path(__file__).parent / "multidomain_human_annotation_pool.md"

with open(csv_path, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

md_lines = [
    "# Archipelago Multi-Domain Human Annotation Workbook (Blinded Pool)",
    "",
    "**Total Items:** 36 items (6 domains x 6 items per domain)",
    "**Protocol:** Independent blinded human evaluation. System-generated labels are concealed.",
    "",
    "---",
    "",
]

current_domain = None
for r in rows:
    if r["domain"] != current_domain:
        current_domain = r["domain"]
        md_lines.append(f"## Domain: {current_domain}")
        md_lines.append("")

    item_id = r["item_id"]
    cA = r["concept_a"]
    cB = r["concept_b"]
    src = r["source_doc_id"]
    pg = r["page_number"]
    chk = r["chunk_id"]
    psg = r["evidence_passage"]

    md_lines.append(f"### Item [{item_id}] — {cA} vs. {cB}")
    md_lines.append(f"- **Source:** `{src}` (Page {pg}, Chunk `{chk}`)")
    md_lines.append(f"- **Passage:** > \"{psg}\"")
    md_lines.append("")
    md_lines.append("| Field | Value (Annotator Entry) | Options / Scale |")
    md_lines.append("|---|---|---|")
    md_lines.append(f"| Concept A Validity (`{cA}`) | [ ] | 1 = Valid, 0 = Invalid |")
    md_lines.append(f"| Concept B Validity (`{cB}`) | [ ] | 1 = Valid, 0 = Invalid |")
    md_lines.append("| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |")
    md_lines.append("| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |")
    md_lines.append("| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |")
    md_lines.append("| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |")
    md_lines.append("| Confidence Level | [ ] | High / Medium / Low |")
    md_lines.append("| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |")
    md_lines.append("| Notes / Justification | | (Optional free text) |")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

md_path.write_text("\n".join(md_lines), encoding="utf-8")
print(f"Wrote {len(rows)} items to {md_path}")
