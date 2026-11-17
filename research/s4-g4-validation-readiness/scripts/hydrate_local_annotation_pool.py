"""S4-G4 — Local Annotation Pool Hydrator.

Reconstructs the blinded human annotation pool and admin selection manifest
strictly on the local machine from the local okf_graph.db using public metadata pointers.

Ensures that copyrighted / proprietary verbatim source passages are NEVER tracked
in the public Git repository.

Outputs:
- data/annotation_local/blinded_human_annotation_pool.csv
- data/annotation_local/blinded_human_annotation_workbook.md
- data/annotation_local/admin_selection_manifest.json
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_INDEX = ROOT / "research" / "s4-g4-validation-readiness" / "annotation_package" / "public" / "candidate_metadata_index.csv"
FALLBACK_INDEX = ROOT / "research" / "s4-g3-extraction-repair" / "annotation_package" / "public" / "candidate_metadata_index.csv"
LOCAL_OUT_DIR = ROOT / "data" / "annotation_local"
LOCAL_OUT_DIR.mkdir(parents=True, exist_ok=True)


def sha256_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def get_kuzu_conn():
    import kuzu
    db_path = ROOT / "okf_graph.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Missing local Kùzu database at {db_path}")
    db = kuzu.Database(str(db_path))
    return kuzu.Connection(db)


def hydrate_annotation_pool(index_path: Path | None = None) -> dict[str, Any]:
    src_index = index_path or (PUBLIC_INDEX if PUBLIC_INDEX.exists() else FALLBACK_INDEX)
    if not src_index.exists():
        raise FileNotFoundError(f"Missing candidate metadata index at {src_index}")

    with open(src_index, encoding="utf-8") as f:
        metadata_rows = list(csv.DictReader(f))

    conn = get_kuzu_conn()

    blind_records = []
    admin_manifest_records = []
    verified_count = 0
    mismatch_count = 0

    for r in metadata_rows:
        blind_id = r["blind_id"]
        doc_id = r["doc_id"]
        chunk_id = r["chunk_id"]
        start_off = int(r["evidence_offset_start_in_chunk"])
        end_off = int(r["evidence_offset_end_in_chunk"])
        expected_hash = r["evidence_sha256"]
        concept_a = r["concept_a"]
        concept_b = r["concept_b"]
        page_num = int(r["page_number"])
        domain = r["domain"]
        partition = r["partition"]
        redist_status = r["redistribution_status"]

        # Fetch chunk text from KuzuDB
        query = "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = $doc AND c.chunk_id = $chunk RETURN c.text_passage"
        res = conn.execute(query, {"doc": doc_id, "chunk": chunk_id})
        if not res.has_next():
            raise ValueError(f"Chunk not found in database: {doc_id}::{chunk_id}")

        chunk_text = res.get_next()[0]
        extracted_passage = chunk_text[start_off:end_off]
        actual_hash = sha256_str(extracted_passage)

        if actual_hash != expected_hash:
            mismatch_count += 1
            raise ValueError(
                f"Hash mismatch for {blind_id} ({doc_id}::{chunk_id}): expected {expected_hash}, got {actual_hash}"
            )
        verified_count += 1

        # Blinded human record (empty judgment fields, no developer notes)
        blind_records.append({
            "item_id": blind_id,
            "concept_a": concept_a,
            "concept_b": concept_b,
            "evidence_passage": extracted_passage,
            "source_document": doc_id,
            "chunk_id": chunk_id,
            "page_number": page_num,
            "human_relation_type": "",
            "human_direction": "",
            "human_confidence": "",
            "human_notes": "",
        })

        # Admin record
        admin_manifest_records.append({
            "blind_id": blind_id,
            "original_item_id": r.get("original_item_id", ""),
            "domain": domain,
            "partition": partition,
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "page_number": page_num,
            "concept_a": concept_a,
            "concept_b": concept_b,
            "evidence_passage": extracted_passage,
            "evidence_sha256": actual_hash,
            "evidence_offset_start": start_off,
            "evidence_offset_end": end_off,
            "evidence_match_type": r.get("evidence_match_type", "EXACT"),
            "redistribution_status": redist_status,
        })

    # Write local blinded CSV
    out_csv = LOCAL_OUT_DIR / "blinded_human_annotation_pool.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "item_id", "concept_a", "concept_b", "evidence_passage",
            "source_document", "chunk_id", "page_number",
            "human_relation_type", "human_direction", "human_confidence", "human_notes"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(blind_records)

    # Write local markdown workbook
    out_wb = LOCAL_OUT_DIR / "blinded_human_annotation_workbook.md"
    with open(out_wb, "w", encoding="utf-8") as f:
        f.write("# Archipelago S4 Blinded Human Annotation Workbook\n\n")
        f.write("> **CONFIDENTIAL LOCAL ANNOTATION WORKBOOK**\n")
        f.write("> Contains verbatim source excerpts hydrated from local database. Do not commit to version control.\n\n")
        for b in blind_records:
            f.write(f"## Item {b['item_id']}\n\n")
            f.write(f"- **Concept A:** `{b['concept_a']}`\n")
            f.write(f"- **Concept B:** `{b['concept_b']}`\n")
            f.write(f"- **Document:** `{b['source_document']}`\n")
            f.write(f"- **Chunk:** `{b['chunk_id']}` (Page {b['page_number']})\n\n")
            f.write("### Quoted Evidence\n\n")
            f.write(f"> {b['evidence_passage']}\n\n")
            f.write("### Annotator Evaluation\n\n")
            f.write("- **Relation Exists?** [ ] YES  [ ] NO  [ ] UNCERTAIN\n")
            f.write("- **Relation Type:** `REQUIRES` | `PART_OF` | `USES` | `CONTRASTS_WITH` | `RELATED` | `NONE`\n")
            f.write("- **Direction:** `A_TO_B` | `B_TO_A` | `UNDIRECTED` | `NONE`\n")
            f.write("- **Confidence:** `HIGH` | `MEDIUM` | `LOW`\n")
            f.write("- **Notes:** \n\n---\n\n")

    # Write local admin manifest
    out_manifest = LOCAL_OUT_DIR / "admin_selection_manifest.json"
    with open(out_manifest, "w", encoding="utf-8") as f:
        json.dump({
            "version": "s4-g4-hydrated",
            "source_index": str(src_index),
            "pool_size": len(admin_manifest_records),
            "verified_hash_count": verified_count,
            "candidates": admin_manifest_records,
        }, f, indent=2)

    return {
        "status": "SUCCESS",
        "verified_count": verified_count,
        "mismatch_count": mismatch_count,
        "blinded_csv": str(out_csv),
        "workbook_md": str(out_wb),
        "admin_manifest": str(out_manifest),
    }


if __name__ == "__main__":
    result = hydrate_annotation_pool()
    print("Hydration successful:", result)
