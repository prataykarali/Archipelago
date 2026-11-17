"""S4-G2: Multi-Domain Controlled Experiment Runner.

Executes fair evaluation of Baseline vs MultiDomainExtractor prototype
across six representative academic domains:
1. Operating Systems (OS)
2. Database Management Systems (DBMS)
3. Computer Networks (Networks)
4. Automata Theory & Computation (TOC)
5. Probability & Statistics (ProbStats)
6. Artificial Intelligence & Machine Learning (AIML)

Outputs:
- research/s4-g2-multidomain-evaluation/s4g2_multidomain_eval_results.json
- research/s4-g2-multidomain-evaluation/domain_level_evaluation.csv
- research/s4-g2-multidomain-evaluation/multidomain_experimental_manifest.json
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import kuzu

from okf.eval.gold.part01_load_gold_graph import (
    load_gold_graph,
    compare_concepts,
    compare_edges,
)
from okf.eval.gold.compare_aligned import compare_edges_aligned
from okf.eval.integrity_validators import (
    calculate_provenance_coverage,
    detect_directed_cycles,
)
from okf.graph_db import export_graph
from okf.pilot.multidomain_extractor import MultiDomainExtractor
from okf.query_rows import query_rows

OUTPUT_DIR = ROOT / "research" / "s4-g2-multidomain-evaluation"
RESULTS_JSON = OUTPUT_DIR / "s4g2_multidomain_eval_results.json"
RESULTS_CSV = OUTPUT_DIR / "domain_level_evaluation.csv"
MANIFEST_JSON = OUTPUT_DIR / "multidomain_experimental_manifest.json"


def build_manifest() -> dict[str, Any]:
    manifest = {
        "manifest_version": "1.0",
        "description": "S4-G2 Multi-Domain Experimental Manifest across 6 Core Academic Domains",
        "domains": {
            "Operating Systems": {
                "code": "OS",
                "development": [
                    {
                        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf",
                        "title": "OSTEP Chapter 06: Address Spaces",
                        "source_type": "open_textbook_chapter",
                        "level": "foundational",
                    }
                ],
                "evaluation": [
                    {
                        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf",
                        "title": "OSTEP Chapter 07: Address Translation",
                        "source_type": "open_textbook_chapter",
                        "level": "intermediate",
                    },
                    {
                        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
                        "title": "OSTEP Chapter 08: Paging",
                        "source_type": "open_textbook_chapter",
                        "level": "advanced",
                    },
                ],
            },
            "Database Management Systems": {
                "code": "DBMS",
                "development": [
                    {
                        "doc_id": "pilot/silberschatz_3nf_card.txt",
                        "title": "Silberschatz Database: 3NF Decomposition Card",
                        "source_type": "grounded_card",
                        "level": "foundational",
                    }
                ],
                "evaluation": [
                    {
                        "doc_id": "doc_fundamentals_of_database_system_7e",
                        "title": "Fundamentals of Database Systems 7e",
                        "source_type": "catalog_chapter_excerpt",
                        "level": "intermediate",
                    }
                ],
            },
            "Computer Networks": {
                "code": "Networks",
                "development": [
                    {
                        "doc_id": "doc_computer_networks_6_e",
                        "title": "Tanenbaum Computer Networks 6e Excerpts",
                        "source_type": "textbook_excerpt",
                        "level": "foundational",
                    }
                ],
                "evaluation": [
                    {
                        "doc_id": "papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
                        "title": "Real-time Network Security (Elsevier 2024)",
                        "source_type": "research_paper",
                        "level": "advanced",
                        "chunk_limit": 20,
                    }
                ],
            },
            "Automata Theory & Computation": {
                "code": "TOC",
                "development": [
                    {
                        "doc_id": "papers/Willard2023_Outlines.pdf",
                        "title": "Willard 2023 Outlines (Part 1: Formal Grammars)",
                        "source_type": "research_preprint",
                        "level": "foundational",
                        "chunk_range": [0, 9],
                    }
                ],
                "evaluation": [
                    {
                        "doc_id": "papers/Willard2023_Outlines.pdf",
                        "title": "Willard 2023 Outlines (Part 2: Finite State Machines & Regex)",
                        "source_type": "research_preprint",
                        "level": "advanced",
                        "chunk_range": [10, 19],
                    }
                ],
            },
            "Probability & Statistics": {
                "code": "ProbStats",
                "development": [
                    {
                        "doc_id": "pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf",
                        "title": "Theodoridis Pattern Recognition: Probability Appendix",
                        "source_type": "textbook_appendix",
                        "level": "foundational",
                    },
                    {
                        "doc_id": "pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf",
                        "title": "Theodoridis Pattern Recognition: Bayes Theorem",
                        "source_type": "textbook_chapter",
                        "level": "foundational",
                    },
                ],
                "evaluation": [
                    {
                        "doc_id": "data_science_2019/Index_2019_Data-Science.pdf",
                        "title": "Data Science 2019: Statistical Estimation & Distributions",
                        "source_type": "scholarly_book_index",
                        "level": "intermediate",
                        "chunk_limit": 10,
                    }
                ],
            },
            "Artificial Intelligence & Machine Learning": {
                "code": "AIML",
                "development": [
                    {
                        "doc_id": "papers/Hu2021_LoRA.pdf",
                        "title": "Hu et al. 2021: LoRA (Legacy Diagnostic Case)",
                        "source_type": "research_paper",
                        "level": "diagnostic",
                        "gold_file": "pilot_corpus/gold/gold_lora.json",
                    },
                    {
                        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
                        "title": "Vaswani et al. 2017: Attention (Legacy Diagnostic Case)",
                        "source_type": "research_paper",
                        "level": "diagnostic",
                        "gold_file": "pilot_corpus/gold/gold_attention.json",
                    },
                ],
                "evaluation": [
                    {
                        "doc_id": "papers/Bahdanau2014_Attention.pdf",
                        "title": "Bahdanau et al. 2014: Neural Machine Translation (Held-Out Source)",
                        "source_type": "research_paper",
                        "level": "held_out",
                        "gold_file": None,
                    },
                    {
                        "doc_id": "papers/Devlin2018_BERT.pdf",
                        "title": "Devlin et al. 2018: BERT (Held-Out Source)",
                        "source_type": "research_paper",
                        "level": "held_out",
                        "gold_file": None,
                    },
                ],
            },
        },
    }
    return manifest


def run_experiment() -> dict[str, Any]:
    print("=== Running S4-G2 Multi-Domain Controlled Experiment ===")
    t_start = time.time()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    db_path = ROOT / "okf_graph.db"
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)

    # Pre-load full baseline export
    baseline_export = export_graph(conn)

    extractor = MultiDomainExtractor(confidence_threshold=0.65)
    domain_results: dict[str, Any] = {}
    csv_rows = []

    for domain_name, dom_info in manifest["domains"].items():
        domain_code = dom_info["code"]
        print(f"\nProcessing Domain: {domain_name} ({domain_code})")

        domain_results[domain_name] = {
            "code": domain_code,
            "partitions": {},
            "summary": {},
        }

        for partition_name in ("development", "evaluation"):
            doc_specs = dom_info.get(partition_name, [])
            partition_res = []

            for spec in doc_specs:
                doc_id = spec["doc_id"]
                title = spec["title"]
                gold_file = spec.get("gold_file")

                # Fetch chunks from okf_graph.db
                rows = list(
                    query_rows(
                        conn,
                        f'MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = "{doc_id}" RETURN c.chunk_id, c.text_passage',
                    )
                )

                # Apply chunk range or limit if specified
                if "chunk_range" in spec:
                    start_idx, end_idx = spec["chunk_range"]
                    rows = rows[start_idx : end_idx + 1]
                elif "chunk_limit" in spec:
                    rows = rows[: spec["chunk_limit"]]

                chunks = [{"chunk_id": r[0], "text_passage": r[1]} for r in rows]
                print(f"  [{partition_name}] {title}: loaded {len(chunks)} chunks")

                # --- 1. Fair Baseline Metrics (Document Scoped) ---
                base_metrics = {}
                # Query baseline concepts connected to this document in DB
                db_doc_concepts_rows = list(
                    query_rows(
                        conn,
                        f'MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(cp:Concept) WHERE d.id = "{doc_id}" RETURN distinct cp.name',
                    )
                )
                db_doc_concept_names = [r[0] for r in db_doc_concepts_rows]
                base_concept_count = len(db_doc_concept_names)

                # Query baseline edges originating from or scoped to this document
                db_doc_edges = [
                    e for e in baseline_export.get("edges", [])
                    if isinstance(e, dict) and (
                        str(e.get("source", "")).startswith(doc_id)
                        or str(e.get("doc_id", "")).startswith(doc_id)
                    )
                ]
                base_directed_edges = [
                    e for e in db_doc_edges
                    if str(e.get("edge_type", "")).upper() in ("REQUIRES", "UNLOCKS")
                ]

                # Check gold comparison if verified gold exists
                if gold_file and (ROOT / gold_file).exists():
                    gold = load_gold_graph(str(ROOT / gold_file))
                    # Fair document-scoped baseline concept evaluation
                    fair_base_export = {
                        "concepts": {
                            name.lower().replace(" ", "_"): {"name": name}
                            for name in db_doc_concept_names
                        },
                        "edges": [],
                    }
                    cc_base_fair = compare_concepts(fair_base_export, gold)
                    ce_base_exact = compare_edges(baseline_export, gold, doc_id=doc_id)
                    ce_base_aligned = compare_edges_aligned(
                        baseline_export, gold, concept_comparison=cc_base_fair, doc_id=doc_id
                    )

                    base_metrics = {
                        "concept_precision": cc_base_fair["precision"],
                        "concept_recall": cc_base_fair["recall"],
                        "concept_f1": cc_base_fair["f1"],
                        "concept_tp": cc_base_fair["true_positives"],
                        "concept_fp": cc_base_fair["false_positives"],
                        "concept_fn": cc_base_fair["false_negatives"],
                        "directed_edge_f1_exact": ce_base_exact["directed"]["f1"],
                        "directed_edge_f1_aligned": ce_base_aligned["directed"]["f1"],
                        "undirected_edge_f1": ce_base_aligned["undirected"]["f1"],
                        "direction_accuracy": ce_base_aligned["direction_accuracy"],
                        "direction_accuracy_status": ce_base_aligned["direction_accuracy_status"],
                        "gold_available": True,
                    }
                else:
                    base_metrics = {
                        "concept_count": base_concept_count,
                        "edges_count": len(db_doc_edges),
                        "directed_edges_count": len(base_directed_edges),
                        "gold_available": False,
                    }

                # --- 2. MultiDomainExtractor Prototype Execution ---
                t_proto0 = time.time()
                proto_res = extractor.extract_document_graph(chunks, doc_id, domain=domain_name)
                t_proto_dur = time.time() - t_proto0
                proto_export = proto_res["graph_export"]

                proto_metrics = {}
                if gold_file and (ROOT / gold_file).exists():
                    gold = load_gold_graph(str(ROOT / gold_file))
                    cc_proto = compare_concepts(proto_export, gold)
                    ce_proto_exact = compare_edges(proto_export, gold, doc_id=doc_id)
                    ce_proto_aligned = compare_edges_aligned(
                        proto_export, gold, concept_comparison=cc_proto, doc_id=doc_id
                    )

                    proto_metrics = {
                        "concept_precision": cc_proto["precision"],
                        "concept_recall": cc_proto["recall"],
                        "concept_f1": cc_proto["f1"],
                        "concept_tp": cc_proto["true_positives"],
                        "concept_fp": cc_proto["false_positives"],
                        "concept_fn": cc_proto["false_negatives"],
                        "directed_edge_f1_exact": ce_proto_exact["directed"]["f1"],
                        "directed_edge_f1_aligned": ce_proto_aligned["directed"]["f1"],
                        "undirected_edge_f1": ce_proto_aligned["undirected"]["f1"],
                        "direction_accuracy": ce_proto_aligned["direction_accuracy"],
                        "direction_accuracy_status": ce_proto_aligned["direction_accuracy_status"],
                        "gold_available": True,
                    }
                else:
                    proto_metrics = {
                        "concept_count": proto_res["concept_count"],
                        "gold_available": False,
                    }

                total_evaluated_pairs = (
                    proto_res["abstention_count"]
                    + proto_res["rejection_count"]
                    + proto_res["edge_count"]
                )
                abstention_rate = (
                    proto_res["abstention_count"] / total_evaluated_pairs
                    if total_evaluated_pairs > 0
                    else 0.0
                )

                # --- Provenance Validity Coverage (calculated from actual DB and chunk text) ---
                prov_report = calculate_provenance_coverage(proto_export["edges"], conn)

                # --- Full Directed Cycle Detection (length k >= 2 on prerequisite/enablement paths) ---
                cycle_report = detect_directed_cycles(
                    proto_export["edges"], edge_types=("REQUIRES", "UNLOCKS")
                )

                # --- Unsupported Relation Rate: requires independently validated human ground truth ---
                # Scientifically invalid to report 0.0 without gold support labels.
                unsupported_rate_str = "NOT_MEASURED"

                doc_report = {
                    "doc_id": doc_id,
                    "title": title,
                    "partition": partition_name,
                    "chunks_count": len(chunks),
                    "baseline": base_metrics,
                    "prototype": {
                        **proto_metrics,
                        "concept_count": proto_res["concept_count"],
                        "edge_count": proto_res["edge_count"],
                        "directed_edge_count": proto_res["directed_edge_count"],
                        "explicit_prereq_count": proto_res["explicit_prereq_count"],
                        "inferred_prereq_count": proto_res["inferred_prereq_count"],
                        "unlocks_count": proto_res["unlocks_count"],
                        "part_of_count": proto_res["part_of_count"],
                        "uses_count": proto_res["uses_count"],
                        "contrasts_count": proto_res["contrasts_count"],
                        "abstention_count": proto_res["abstention_count"],
                        "rejection_count": proto_res["rejection_count"],
                        "cycles_prevented_count": proto_res["cycles_prevented_count"],
                        "abstention_rate": abstention_rate,
                        "valid_provenance_coverage": prov_report["valid_provenance_coverage"],
                        "valid_provenance_edges_count": prov_report["valid_edges_count"],
                        "provenance_total_denominator": prov_report["total_edges_denominator"],
                        "provenance_status": prov_report["status"],
                        "unsupported_relation_rate": unsupported_rate_str,
                        "unsupported_rate_documentation": "Requires independently validated support labels; NOT_MEASURED in absence of gold annotations",
                        "detected_cycles_count": cycle_report["cycle_count"],
                        "has_directed_cycles": cycle_report["has_cycles"],
                        "detected_cycles_sample": cycle_report["cycles"][:5],
                        "runtime_seconds": round(t_proto_dur, 3),
                        "sample_edges": proto_export["edges"][:4],
                        "sample_abstentions": proto_res["abstentions"][:3],
                    },
                }
                partition_res.append(doc_report)

                # Add to CSV rows with documented denominators
                prov_cov_str = (
                    f"{prov_report['valid_provenance_coverage']:.2%}"
                    if prov_report["valid_provenance_coverage"] is not None
                    else "N/A"
                )
                csv_rows.append(
                    {
                        "Domain": domain_name,
                        "Partition": partition_name,
                        "Doc ID": doc_id,
                        "Chunks": len(chunks),
                        "Baseline Concepts": base_metrics.get("concept_count", base_metrics.get("concept_tp", 0) + base_metrics.get("concept_fp", 0)),
                        "Proto Concepts": proto_res["concept_count"],
                        "Proto Edges Total": proto_res["edge_count"],
                        "Explicit Prereq": proto_res["explicit_prereq_count"],
                        "Inferred Prereq": proto_res["inferred_prereq_count"],
                        "Part-Of": proto_res["part_of_count"],
                        "Uses": proto_res["uses_count"],
                        "Contrasts": proto_res["contrasts_count"],
                        "Abstentions": proto_res["abstention_count"],
                        "Abstention Rate": f"{abstention_rate:.2%}",
                        "Unsupported Rate": unsupported_rate_str,
                        "Provenance Coverage": prov_cov_str,
                        "Provenance Valid / Total": f"{prov_report['valid_edges_count']}/{prov_report['total_edges_denominator']}",
                        "Cycles": cycle_report["cycle_count"],
                        "Runtime (s)": f"{t_proto_dur:.2f}",
                    }
                )

            domain_results[domain_name]["partitions"][partition_name] = partition_res

    total_runtime = time.time() - t_start
    final_output = {
        "experiment_name": "S4-G2 Multi-Domain Evaluation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_runtime_seconds": round(total_runtime, 2),
        "manifest": manifest,
        "domain_results": domain_results,
    }

    # Write output JSON
    RESULTS_JSON.write_text(json.dumps(final_output, indent=2, default=str), encoding="utf-8")
    print(f"\nExperiment complete. Saved results to {RESULTS_JSON}")

    # Write output CSV
    if csv_rows:
        with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"Saved domain-level CSV to {RESULTS_CSV}")

    return final_output


if __name__ == "__main__":
    run_experiment()
