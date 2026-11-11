#!/usr/bin/env python3
"""
Master Library Ingestion Runner — Multi-Domain Knowledge Graph Pipeline.
Ingests books, papers, and institutional library physical resources across 14 batches:
Batches 1-7:   Pearson eBooks & Computer Science / Engineering Disciplines
Batches 8-10:  Institutional Physical Resources (Bio, Chem, Physics, Mech, Civil)
Batch 11:      Applied Mathematics & Statistics (Deisenroth, Kreyszig, Strang)
Batches 12-14: Foundational Research Papers from Hugging Face Hub (Transformers, PEFT, RAG/GNNs)

Enforces:
- Strict 8-key OKF contract
- Kahn DAG Cycle Gate
- 5-layer graph connections (Subject -> Resource -> Document -> Chunk -> Concept)
- Vector embedding precomputation before zero-downtime atomic swap
- Hugging Face remote sync (Prataykarali/Library_books)
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import threading
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from archipelago.graph.engine import KuzuGraphEngine  # noqa: E402
from archipelago.graph.graph_fusion import GraphFusionEngine  # noqa: E402
from archipelago.ingestion.lib_qwen_extractor import (  # noqa: E402
    LibQwenConceptExtractor,
    canonical_concept_id,
)
from archipelago.storage.hf_remote import HFStorageClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("archipelago.master_ingest")

from scripts.master_ingest_curriculum_early import EARLY_BATCHES  # noqa: E402
from scripts.master_ingest_curriculum_late import LATE_BATCHES  # noqa: E402
from scripts.master_ingest_hammer import subgraph_hammer as _subgraph_hammer  # noqa: E402

BATCH_CURRICULUM: dict[int, dict[str, Any]] = {**EARLY_BATCHES, **LATE_BATCHES}


def run_batch_ingest(
    batch_num: int,
    target_db_path: str | Path = "okf_graph.db",
    sync_to_hf: bool = True,
) -> dict[str, Any]:
    """Execute ingestion curriculum for a specific batch with Kahn DAG gate and 5-layer graph commit."""
    target_db = Path(target_db_path)
    if batch_num not in BATCH_CURRICULUM:
        raise ValueError(
            f"Unknown batch number {batch_num}. Valid batches: {list(BATCH_CURRICULUM.keys())}"
        )

    batch_def = BATCH_CURRICULUM[batch_num]
    domain = batch_def["domain"]
    subject_name = batch_def["subject"]
    sources = batch_def["sources"]

    logger.info("================================================================================")
    logger.info("=== Starting Batch %d Ingestion: %s ===", batch_num, domain)
    logger.info("=== Subject: %s | Target DB: %s ===", subject_name, target_db)
    logger.info("================================================================================")

    extractor = LibQwenConceptExtractor(model_name="lib-qwen:latest")
    fusion = GraphFusionEngine(db_path=target_db)
    engine = KuzuGraphEngine(db_path=target_db, read_only=False)

    logger.info("Extractor model=%s host=%s", extractor.model_name, extractor.host)
    try:
        import subprocess

        gpu = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,power.draw,memory.used,temperature.gpu",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip()
        logger.info("GPU before extraction: %s", gpu)
    except Exception as gpu_err:
        logger.warning("nvidia-smi unavailable: %s", gpu_err)

    all_raw_concepts: list[dict[str, Any]] = []

    for idx, item in enumerate(sources, 1):
        book_title = item["book_title"]
        author = item.get("author", "Unknown Author")
        chapter = item.get("chapter", "Core Theory")
        page = int(item.get("page", 1))
        text = item["text"]

        logger.info(
            "[%d/%d] Extracting: '%s' (p. %d) — %s", idx, len(sources), book_title, page, chapter
        )
        extracted = extractor.extract_from_text(
            text=text,
            doc_id=f"batch{batch_num}_{idx}",
            page_number=page,
            book_title=book_title,
            domain=domain,
        )
        logger.info("    -> Extracted %d concepts conforming to 8-key OKF contract", len(extracted))
        try:
            import subprocess

            gpu = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,power.draw,memory.used,temperature.gpu",
                    "--format=csv,noheader",
                ],
                text=True,
            ).strip()
            logger.info("    GPU after chunk %d: %s", idx, gpu)
        except Exception:
            pass
        for c in extracted:
            c["author"] = author
            c["chapter"] = chapter
            all_raw_concepts.append(c)

    # 1. Entity resolution and reciprocal cycle resolution
    logger.info("Executing entity resolution & second-pass cycle resolver...")
    resolved = extractor.second_pass_relation_resolver(all_raw_concepts)
    logger.info("Total resolved concepts: %d", len(resolved))

    # 2. Kahn DAG Cycle Gate
    logger.info("Running Kahn DAG Cycle Gate verification...")
    merge_report = fusion.merge_batch(
        extracted_concepts=resolved,
        kuzu_engine=engine,
        max_batch_nodes=150,
    )
    logger.info("Merge report: %s", merge_report)

    # 3. Interconnect 5 Layers: Subject -> Resource -> Document -> Chunk -> Concept
    logger.info(
        "Interconnecting 5 graph layers (Subject -> Resource -> Document -> Chunk -> Concept)..."
    )
    conn = engine.conn

    # Ensure Subject exists
    safe_subj = subject_name.replace("'", "''")
    conn.execute(
        f"MERGE (s:Subject {{subject_name: '{safe_subj}'}}) ON CREATE SET s.total_titles = 1"
    )

    for idx, item in enumerate(sources, 1):
        b_title = item["book_title"]
        b_author = item.get("author", "Unknown Author")
        b_page = int(item.get("page", 1))
        b_chapter = item.get("chapter", "Core Section")
        b_text = item["text"][:350].replace("'", "''")

        res_id = f"res_{canonical_concept_id(b_title)}"
        doc_id = f"doc_{canonical_concept_id(b_title)}"
        chunk_id = f"{doc_id}_p{b_page}_{idx}"

        safe_btitle = b_title.replace("'", "''")
        safe_bauthor = b_author.replace("'", "''")
        safe_bchap = b_chapter.replace("'", "''")

        # 1. Subject -> Resource
        conn.execute(
            f"MERGE (r:Resource {{id: '{res_id}'}}) "
            f"ON CREATE SET r.title = '{safe_btitle}', r.author = '{safe_bauthor}', "
            f"r.copyright_year = 2024, r.publisher = 'Institutional Library', "
            f"r.biblionumber = '0', r.total_copies = 1, r.available_copies = 1, "
            f"r.barcodes = '[]', r.overdue_items = 0, r.is_periodical = false"
        )
        conn.execute(
            f"MATCH (s:Subject {{subject_name: '{safe_subj}'}}), (r:Resource {{id: '{res_id}'}}) MERGE (s)-[:CATEGORIZES]->(r)"
        )

        # 2. Resource -> Document
        conn.execute(
            f"MERGE (d:Document {{id: '{doc_id}'}}) "
            f"ON CREATE SET d.title = '{safe_btitle}', d.doc_hash = '{doc_id}', "
            f"d.page_count = 500, d.edition = 'Global', d.pdf_url = 'remote_hf/{canonical_concept_id(b_title)}.pdf'"
        )
        conn.execute(
            f"MATCH (r:Resource {{id: '{res_id}'}}), (d:Document {{id: '{doc_id}'}}) MERGE (r)-[:PROVIDES_TEXT]->(d)"
        )

        # 3. Document -> Chunk
        conn.execute(
            f"MERGE (chk:Chunk {{id: '{chunk_id}'}}) "
            f"ON CREATE SET chk.chunk_id = '{chunk_id}', chk.page_number = {b_page}, "
            f"chk.section_title = '{safe_bchap}', chk.text_passage = '{b_text}'"
        )
        conn.execute(
            f"MATCH (d:Document {{id: '{doc_id}'}}), (chk:Chunk {{id: '{chunk_id}'}}) MERGE (d)-[:HAS_CHUNK]->(chk)"
        )

        # 4. Chunk -> Concept (MENTIONS)
        for c in resolved:
            if c.get("source_book") == b_title or c.get("chapter") == b_chapter:
                cid = c["id"]
                try:
                    conn.execute(
                        f"MATCH (chk:Chunk {{id: '{chunk_id}'}}), (c:Concept {{id: '{cid}'}}) "
                        f"MERGE (chk)-[:MENTIONS]->(c)"
                    )
                except Exception:
                    pass

    # Verify counts in DB
    res_concepts = conn.execute("MATCH (c:Concept) RETURN count(c);").get_as_df().iloc[0, 0]
    res_requires = conn.execute("MATCH ()-[r:REQUIRES]->() RETURN count(r);").get_as_df().iloc[0, 0]
    res_mentions = conn.execute("MATCH ()-[r:MENTIONS]->() RETURN count(r);").get_as_df().iloc[0, 0]
    res_provides = (
        conn.execute("MATCH ()-[r:PROVIDES_TEXT]->() RETURN count(r);").get_as_df().iloc[0, 0]
    )

    logger.info(
        "KùzuDB Status: %d Concepts, %d REQUIRES edges, %d MENTIONS edges, %d PROVIDES_TEXT edges",
        res_concepts,
        res_requires,
        res_mentions,
        res_provides,
    )

    engine.close()

    # Build summary
    summary_path = ROOT / "data" / "catalogs" / f"batch{batch_num}_ingestion_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "status": "success",
        "batch_num": batch_num,
        "domain": domain,
        "subject": subject_name,
        "sources_count": len(sources),
        "total_extracted": len(all_raw_concepts),
        "committed_nodes": merge_report.get("committed_nodes", 0),
        "committed_edges": merge_report.get("committed_edges", 0),
        "db_total_concepts": int(res_concepts),
        "db_total_requires": int(res_requires),
        "db_total_mentions": int(res_mentions),
        "db_total_provides_text": int(res_provides),
        "timestamp": time.time(),
        "sample_concepts": [
            {
                "name": c["name"],
                "concept_type": c.get("concept_type", "definition"),
                "difficulty": c.get("difficulty", "intermediate"),
                "summary": c.get("summary", ""),
                "prerequisites": [
                    p["name"] if isinstance(p, dict) else str(p) for p in c.get("prerequisites", [])
                ],
                "unlocks": [
                    u["name"] if isinstance(u, dict) else str(u) for u in c.get("unlocks", [])
                ],
            }
            for c in resolved[:8]
        ],
    }
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    logger.info("Batch %d summary saved to %s", batch_num, summary_path)

    # Sync summary to Hugging Face remote dataset
    if sync_to_hf:
        try:
            client = HFStorageClient()
            if client.is_available:
                client.upload_file(
                    local_path=summary_path,
                    remote_path=f"catalogs/batch{batch_num}_ingestion_summary.json",
                    commit_message=f"Ingestion curriculum: Batch {batch_num} ({domain})",
                )
                logger.info("Synchronized batch summary to Hugging Face dataset %s", client.repo_id)
        except Exception as hf_err:
            logger.warning("Could not sync summary to Hugging Face: %s", hf_err)

    return summary_data


def main():
    parser = argparse.ArgumentParser(
        description="Master Multi-Domain Knowledge Graph Ingestion Runner"
    )
    parser.add_argument(
        "--batch", type=int, default=2, help="Batch number to ingest (1-14). Default: 2"
    )
    parser.add_argument(
        "--all", action="store_true", help="Ingest all batches 2 through 14 sequentially"
    )
    parser.add_argument(
        "--target-db", type=str, default="okf_graph.db", help="Target KùzuDB database path"
    )
    parser.add_argument(
        "--no-sync-hf", action="store_true", help="Disable Hugging Face dataset remote sync"
    )
    parser.add_argument(
        "--direct-prod",
        action="store_true",
        help="Write directly to production (unsafe). Default is staging + embed + atomic swap.",
    )
    parser.add_argument(
        "--max-delta", type=int, default=150, help="Abort publish if concept delta exceeds this"
    )
    args = parser.parse_args()

    sync_hf = not args.no_sync_hf

    from archipelago.ingestion.librarian_worker import (
        PROD_DB_PATH,
        STAGING_DB_PATH,
        clone_production_to_staging,
        count_concepts,
        publish_staging,
    )

    if args.direct_prod:
        target_db = Path(args.target_db)
        logger.warning("DIRECT PRODUCTION WRITE enabled (%s) — skipping staging swap.", target_db)
        baseline = count_concepts(target_db) if target_db.exists() else 0
    else:
        baseline = count_concepts(PROD_DB_PATH) if PROD_DB_PATH.exists() else 0
        clone_production_to_staging(force=True)
        target_db = STAGING_DB_PATH
        logger.info("Staging pipeline: baseline=%d concepts, staging=%s", baseline, target_db)

    if args.all:
        logger.info("=== Starting Master Full Ingestion Curriculum: Batches 2 through 14 ===")
        results = {}
        for b_num in sorted(BATCH_CURRICULUM.keys()):
            results[b_num] = run_batch_ingest(b_num, target_db_path=target_db, sync_to_hf=sync_hf)
            time.sleep(1.0)
        last = results[max(results)]
        logger.info("All batches completed successfully!")
    else:
        last = run_batch_ingest(args.batch, target_db_path=target_db, sync_to_hf=sync_hf)

    if args.direct_prod:
        return

    staged_total = int(last.get("db_total_concepts") or count_concepts(target_db))
    delta = staged_total - baseline
    logger.info(
        "Concept cardinality: baseline=%d staged=%d delta=%d (max %d)",
        baseline,
        staged_total,
        delta,
        args.max_delta,
    )
    if delta > args.max_delta:
        raise SystemExit(
            f"Refusing to publish: concept delta {delta} exceeds --max-delta {args.max_delta}. Staging DB left in place."
        )

    hammer_stop = threading.Event()
    hammer_results: list[dict[str, Any]] = []
    hammer = threading.Thread(
        target=_subgraph_hammer, args=(hammer_stop, hammer_results), daemon=True
    )
    hammer.start()
    try:
        publish = publish_staging()
        logger.info("Publish result: %s", publish)
    finally:
        hammer_stop.set()
        hammer.join(timeout=5.0)

    ok_hits = sum(1 for r in hammer_results if r.get("ok"))
    logger.info(
        "Concurrent /api/graph/subgraph during swap: %d/%d succeeded", ok_hits, len(hammer_results)
    )
    for r in hammer_results:
        if not r.get("ok"):
            logger.warning("  subgraph miss: %s", r)


if __name__ == "__main__":
    main()
