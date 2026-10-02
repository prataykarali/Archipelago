"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from . import _deps as _rt  # noqa: F401


def print_report(report: dict):
    """Print a formatted report of the pipeline evaluation metrics."""
    print("\n" + "=" * 70)
    print("OKF PIPELINE EVALUATION REPORT")
    print("=" * 70)

    cc = report.get("concept_comparison", {})
    print("\nConcept Comparison Metrics:")
    print(f"  Precision: {cc.get('precision', 0.0):.2%}")
    print(f"  Recall:    {cc.get('recall', 0.0):.2%}")
    print(f"  F1 Score:  {cc.get('f1', 0.0):.2%}")
    print(f"  True Positives:  {cc.get('true_positives', 0)}")
    print(f"  False Positives: {cc.get('false_positives', 0)}")
    print(f"  False Negatives: {cc.get('false_negatives', 0)}")

    em = report.get("edge_comparison", {})
    dir_e = em.get("directed", {})
    undir_e = em.get("undirected", {})
    print("\nEdge Comparison Metrics (Directed):")
    print(f"  Precision: {dir_e.get('precision', 0.0):.2%}")
    print(f"  Recall:    {dir_e.get('recall', 0.0):.2%}")
    print(f"  F1 Score:  {dir_e.get('f1', 0.0):.2%}")

    print("\nEdge Comparison Metrics (Undirected):")
    print(f"  Precision: {undir_e.get('precision', 0.0):.2%}")
    print(f"  Recall:    {undir_e.get('recall', 0.0):.2%}")
    print(f"  F1 Score:  {undir_e.get('f1', 0.0):.2%}")
    print(f"  Direction Accuracy: {em.get('direction_accuracy', 0.0):.2%}")

    sa = report.get("structural_audit", {})
    print("\nStructural Audit:")
    print(f"  Total Self-Loops / Self-Edges: {len(sa.get('self_edges', []))}")
    print(f"  Total Cycles Detected:         {len(sa.get('cycles', []))}")
    print(f"  Orphan Count:                  {sa.get('orphan_count', 0)}")
    print(f"  Orphan Percentage:             {sa.get('orphan_percentage', 0.0):.2%}")
    print(f"  Edge Provenance Issues:        {len(sa.get('edge_provenance_issues', []))}")
    print(f"  Connected Components Count:    {sa.get('connected_components_count', 0)}")
    print("=" * 70 + "\n")
