"""Analyze overgeneration, candidate pairs, semantic argument direction, and cycles across the multi-domain benchmark."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import kuzu
from okf.eval.integrity_validators import (
    audit_semantic_direction,
    detect_directed_cycles,
)
from okf.pilot.multidomain_extractor import MultiDomainExtractor
from okf.query_rows import query_rows

GATE_DIR = ROOT / "research" / "s4-g2-1-integrity-gate"
OVERGEN_CSV = GATE_DIR / "overgeneration_and_cycle_analysis.csv"
SPLIT_CSV = GATE_DIR / "evaluation_split_audit.csv"


def run_overgeneration_audit() -> None:
    print("=== Running Overgeneration and Cycle Analysis ===")
    GATE_DIR.mkdir(parents=True, exist_ok=True)

    db_path = ROOT / "okf_graph.db"
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)

    # Load experimental manifest
    manifest_path = ROOT / "research" / "s4-g2-multidomain-evaluation" / "multidomain_experimental_manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    extractor = MultiDomainExtractor()
    overgen_rows = []
    split_rows = []

    for domain_name, dom_info in manifest["domains"].items():
        domain_code = dom_info["code"]

        # Track docs in partition for split audit
        dev_docs = [d["doc_id"] for d in dom_info.get("development", [])]
        eval_docs = [d["doc_id"] for d in dom_info.get("evaluation", [])]

        # Check split type
        overlap = set(dev_docs).intersection(set(eval_docs))
        if overlap:
            split_type = "WITHIN_DOCUMENT_CHUNK_SPLIT"
            split_rigor = "NON_DISJOINT (Data Leakage Risk: Same Document Context)"
            split_justification = "Single document available; chunk-indexed split used"
        else:
            split_type = "DOCUMENT_DISJOINT"
            split_rigor = "DISJOINT (Clean Separation across distinct files/sources)"
            split_justification = "Distinct document identifiers evaluated"

        for p_name in ("development", "evaluation"):
            specs = dom_info.get(p_name, [])
            for s in specs:
                doc_id = s["doc_id"]
                title = s["title"]
                source_type = s.get("source_type", "unknown")

                # Fetch chunks
                rows = list(query_rows(conn, f'MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = "{doc_id}" RETURN c.chunk_id, c.text_passage'))
                if "chunk_range" in s:
                    st, en = s["chunk_range"]
                    rows = rows[st : en + 1]
                elif "chunk_limit" in s:
                    rows = rows[: s["chunk_limit"]]

                chunks = [{"chunk_id": r[0], "text_passage": r[1]} for r in rows]
                chunk_count = len(chunks)

                # Split row
                split_rows.append({
                    "Domain": domain_name,
                    "Domain Code": domain_code,
                    "Partition": p_name,
                    "Doc ID": doc_id,
                    "Title": title,
                    "Source Type": source_type,
                    "Chunk Count": chunk_count,
                    "Split Type": split_type,
                    "Split Rigor": split_rigor,
                    "Split Justification": split_justification,
                })

                # Extractor output
                res = extractor.extract_document_graph(chunks, doc_id, domain_name)
                concepts = list(res["graph_export"]["concepts"].values())
                concept_names = [c["name"] for c in concepts]
                concept_count = len(concept_names)

                # Concept validity audit (estimate invalid concepts: pure digits, hex numbers, single-word stopwords)
                invalid_stopwords = {"from", "current", "early", "however", "when", "then", "also", "thus", "three", "two", "one"}
                invalid_concepts = [
                    c for c in concept_names
                    if re.match(r"^\d+[a-zA-Z]*$", c) or c.lower() in invalid_stopwords or c.lower().endswith("kb")
                ]
                invalid_concept_pct = (len(invalid_concepts) / concept_count) if concept_count > 0 else 0.0

                edges = res["graph_export"]["edges"]
                total_edges = len(edges)
                total_candidate_pairs = res["abstention_count"] + res["rejection_count"] + total_edges
                edge_density = (total_edges / total_candidate_pairs) if total_candidate_pairs > 0 else 0.0

                # Cycle detection: prerequisite vs all relations
                prereq_cycles = detect_directed_cycles(edges, edge_types=("REQUIRES", "UNLOCKS"))
                all_cycles = detect_directed_cycles(edges, edge_types=None)

                # Direction audit on sample of USES, PART_OF, REQUIRES
                asym_edges = [e for e in edges if e.get("relation") in ("uses", "part_of", "explicit_prerequisite")]
                inverted_count = 0
                natural_count = 0
                ambiguous_count = 0

                for ae in asym_edges[:50]:  # sample up to 50
                    da = audit_semantic_direction(ae["from_name"], ae["to_name"], ae.get("relation", ""), ae.get("evidence_text", ""))
                    if da["direction_type"] == "inverted":
                        inverted_count += 1
                    elif da["direction_type"] == "natural":
                        natural_count += 1
                    else:
                        ambiguous_count += 1

                total_audited_asym = natural_count + inverted_count + ambiguous_count
                inverted_pct = (inverted_count / total_audited_asym) if total_audited_asym > 0 else 0.0

                # Determine primary failure pattern
                if "index" in doc_id.lower():
                    failure_pattern = "BOOK_INDEX_CROSS_PRODUCT: Hundreds of headword concepts co-occurring in index entries trigger massive USES edge proliferation."
                elif total_edges > 1000:
                    failure_pattern = "BROAD_TRIGGER_OVERGENERATION: Generic lexical triggers ('uses', 'using', 'requires') match across noisy candidate pairs."
                elif invalid_concept_pct > 0.15:
                    failure_pattern = "STOPWORD_AND_NUMERIC_LEAKAGE: Capitalized diagram labels and numbers treated as technical concepts."
                elif prereq_cycles["cycle_count"] > 0:
                    failure_pattern = "UNRESOLVED_MULTI_HOP_CYCLES: Length-3+ prerequisite cycles undetected by 2-cycle prevention guard."
                else:
                    failure_pattern = "STABLE_OR_SPARSE: Minimal overgeneration or strict abstention on few technical concepts."

                overgen_rows.append({
                    "Doc ID": doc_id,
                    "Domain": domain_name,
                    "Partition": p_name,
                    "Chunks": chunk_count,
                    "Concepts Extracted": concept_count,
                    "Noisy/Invalid Concept Rate": f"{invalid_concept_pct:.1%}",
                    "Candidate Pairs Evaluated": total_candidate_pairs,
                    "Extracted Edges Total": total_edges,
                    "Edge Density": f"{edge_density:.2%}",
                    "Explicit Prereq": res["explicit_prereq_count"],
                    "Uses Edges": res["uses_count"],
                    "Part-Of Edges": res["part_of_count"],
                    "Contrasts Edges": res["contrasts_count"],
                    "Prereq Cycles (k>=2)": prereq_cycles["cycle_count"],
                    "All-Relation Cycles (k>=2)": all_cycles["cycle_count"],
                    "Asym Direction Inverted (Sample)": f"{inverted_pct:.1%}",
                    "Primary Failure Pattern": failure_pattern,
                })

    # Save OVERGEN_CSV
    with open(OVERGEN_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(overgen_rows[0].keys()))
        writer.writeheader()
        writer.writerows(overgen_rows)
    print(f"Saved overgeneration audit to {OVERGEN_CSV}")

    # Save SPLIT_CSV
    with open(SPLIT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(split_rows[0].keys()))
        writer.writeheader()
        writer.writerows(split_rows)
    print(f"Saved evaluation split audit to {SPLIT_CSV}")


if __name__ == "__main__":
    run_overgeneration_audit()
