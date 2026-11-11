#!/usr/bin/env python3
"""Targeted SoFerence concept seed — agent / paging / vLLM / QLoRA / 3NF.

Uses local PDF text (fitz) + hand-grounded summaries. Does NOT wipe the graph.
Backs up okf_graph.db + okf_graph.json first. Optionally reloads embeddings.

Usage (from archipealgo root, servers STOPPED or graph unlocked):
  .venv/bin/python scripts/ops/seed_soference_nodes.py
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sys

from seed_soference_catalog import SEEDS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "okf_graph.db"
JSON_PATH = ROOT / "okf_graph.json"
PDF_ROOT = ROOT / "pdfs"


def _extract(pdf_rel: str, pages: list[int], max_chars: int = 900) -> list[dict]:
    import fitz

    path = PDF_ROOT / pdf_rel
    if not path.exists():
        # try alternate roots
        alt = ROOT / "pdfs" / "archipelago-books-cs" / pdf_rel
        path = alt if alt.exists() else path
    if not path.exists():
        print(f"  WARN missing PDF: {pdf_rel}")
        return []
    doc = fitz.open(str(path))
    out = []
    for p in pages:
        idx = p - 1
        if idx < 0 or idx >= len(doc):
            continue
        text = re.sub(r"\s+", " ", doc[idx].get_text() or "").strip()
        if not text:
            continue
        # Keep path relative to pdfs/ root (do NOT use str.lstrip — it strips chars).
        rel = pdf_rel.replace("\\", "/").removeprefix("pdfs/").removeprefix("./")
        out.append(
            {
                "page": p,
                "text": text[:max_chars],
                "doc_id": rel,
                "title": path.name,
            }
        )
    return out


def _backup() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak_dir = ROOT / f"okf_graph.bak-soference-{stamp}"
    bak_dir.mkdir(exist_ok=True)
    for p in (DB_PATH, JSON_PATH):
        if p.exists():
            shutil.copy2(p, bak_dir / p.name)
            print(f"  backed up {p.name} → {bak_dir.name}/")
    return bak_dir


def _ensure_concept(conn, seed: dict) -> None:
    cid = seed["id"]
    r = conn.execute(f"MATCH (c:Concept {{id: '{cid}'}}) RETURN c.id")
    if r.has_next():
        # refresh summary
        summary = seed["summary"].replace("'", "\\'")
        name = seed["name"].replace("'", "\\'")
        conn.execute(
            f"MATCH (c:Concept {{id: '{cid}'}}) SET c.summary = '{summary}', c.name = '{name}'"
        )
        print(f"  update concept {cid}")
    else:
        summary = seed["summary"].replace("'", "\\'")
        name = seed["name"].replace("'", "\\'")
        ctype = seed.get("concept_type", "method")
        diff = seed.get("difficulty", "intermediate")
        conn.execute(
            "CREATE (c:Concept {"
            f"id: '{cid}', name: '{name}', concept_type: '{ctype}', "
            f"difficulty: '{diff}', summary: '{summary}'"
            "})"
        )
        print(f"  create concept {cid}")


def _ensure_doc(conn, doc_id: str, title: str) -> None:
    safe = doc_id.replace("'", "\\'")
    r = conn.execute(f"MATCH (d:Document {{id: '{safe}'}}) RETURN d.id")
    if r.has_next():
        return
    t = title.replace("'", "\\'")
    conn.execute(
        "CREATE (d:Document {"
        f"id: '{safe}', doc_hash: '', page_count: 0, title: '{t}', "
        "edition: '', page_label_map: ''"
        "})"
    )


def _ensure_chunk_and_link(conn, concept_id: str, chunk: dict, seq: int) -> None:
    doc_id = chunk["doc_id"]
    page = int(chunk["page"])
    chunk_id = f"{concept_id}_seed_{seq:03d}"
    node_id = f"{doc_id}_chunk_{chunk_id}"
    safe_node = node_id.replace("'", "\\'")
    r = conn.execute(f"MATCH (chk:Chunk {{id: '{safe_node}'}}) RETURN chk.id")
    if r.has_next():
        # still ensure MENTIONS
        pass
    else:
        text = (chunk["text"] or "").replace("\\", "\\\\").replace("'", "\\'")
        section = (chunk.get("section_title") or concept_id).replace("'", "\\'")
        _ensure_doc(conn, doc_id, chunk.get("title") or doc_id)
        safe_doc = doc_id.replace("'", "\\'")
        conn.execute(
            "CREATE (chk:Chunk {"
            f"id: '{safe_node}', chunk_id: '{chunk_id}', page_number: {page}, "
            f"section_title: '{section}', text_passage: '{text}', "
            "text_offset_start: 0, text_offset_end: 0, "
            "block_x: 0.0, block_y: 0.0, block_w: 0.0, block_h: 0.0"
            "})"
        )
        conn.execute(
            f"MATCH (d:Document {{id: '{safe_doc}'}}), (chk:Chunk {{id: '{safe_node}'}}) "
            f"CREATE (d)-[:HAS_CHUNK]->(chk)"
        )
    # MENTIONS edge
    r2 = conn.execute(
        f"MATCH (chk:Chunk {{id: '{safe_node}'}})-[:MENTIONS]->(c:Concept {{id: '{concept_id}'}}) "
        "RETURN chk.id"
    )
    if not r2.has_next():
        conn.execute(
            f"MATCH (chk:Chunk {{id: '{safe_node}'}}), (c:Concept {{id: '{concept_id}'}}) "
            f"CREATE (chk)-[:MENTIONS]->(c)"
        )


def _ensure_edge(conn, frm: str, to: str, rel: str) -> None:
    """rel in REQUIRES | UNLOCKS. Direction: (frm)-[:REL]->(to)."""
    if not frm or not to or frm == to:
        return
    # Only if both concepts exist
    r = conn.execute(
        f"MATCH (a:Concept {{id: '{frm}'}}), (b:Concept {{id: '{to}'}}) RETURN a.id, b.id"
    )
    if not r.has_next():
        print(f"  skip edge {frm}-[{rel}]->{to} (missing endpoint)")
        return
    r2 = conn.execute(
        f"MATCH (a:Concept {{id: '{frm}'}})-[:{rel}]->(b:Concept {{id: '{to}'}}) RETURN a.id"
    )
    if r2.has_next():
        return
    conn.execute(
        f"MATCH (a:Concept {{id: '{frm}'}}), (b:Concept {{id: '{to}'}}) CREATE (a)-[:{rel}]->(b)"
    )
    print(f"  edge {frm} -[{rel}]-> {to}")


def _patch_json(seeds: list[dict]) -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    viz = data.setdefault("visualization", {})
    nodes = viz.setdefault("nodes", data.get("nodes") or [])
    edges = viz.setdefault("edges", data.get("edges") or [])
    by_id = {n.get("id"): n for n in nodes if n.get("id")}

    for seed in seeds:
        cid = seed["id"]
        node = {
            "id": cid,
            "name": seed["name"],
            "label": seed["name"],
            "summary": seed["summary"],
            "concept_type": seed.get("concept_type", "method"),
            "difficulty": seed.get("difficulty", "intermediate"),
        }
        if seed.get("shelf"):
            node["shelf"] = seed["shelf"]
        if cid in by_id:
            by_id[cid].update(node)
        else:
            nodes.append(node)
            by_id[cid] = node

        for pre in seed.get("requires") or []:
            e = {
                "from_id": cid,
                "from_name": seed["name"],
                "relation": "requires",
                "to_id": pre,
                "to_name": pre,
                "edge_type": "REQUIRES",
                "source": "seed_soference_nodes",
            }
            if not any(
                x.get("from_id") == cid
                and x.get("to_id") == pre
                and x.get("edge_type") == "REQUIRES"
                for x in edges
            ):
                edges.append(e)
        for un in seed.get("unlocks") or []:
            e = {
                "from_id": cid,
                "from_name": seed["name"],
                "relation": "unlocks",
                "to_id": un,
                "to_name": un,
                "edge_type": "UNLOCKS",
                "source": "seed_soference_nodes",
            }
            if not any(
                x.get("from_id") == cid and x.get("to_id") == un and x.get("edge_type") == "UNLOCKS"
                for x in edges
            ):
                edges.append(e)

    # Mirror into top-level concepts (list or id→dict map, depending on export).
    concepts = data.get("concepts")
    if isinstance(concepts, list):
        c_by = {c.get("id"): c for c in concepts if isinstance(c, dict)}
        for seed in seeds:
            entry = {
                "id": seed["id"],
                "name": seed["name"],
                "summary": seed["summary"],
                "concept_type": seed.get("concept_type", "method"),
            }
            if seed["id"] in c_by:
                c_by[seed["id"]].update(entry)
            else:
                concepts.append(entry)
    elif isinstance(concepts, dict):
        for seed in seeds:
            concepts[seed["id"]] = {
                "id": seed["id"],
                "name": seed["name"],
                "summary": seed["summary"],
                "concept_type": seed.get("concept_type", "method"),
            }
    else:
        data["concepts"] = {
            seed["id"]: {
                "id": seed["id"],
                "name": seed["name"],
                "summary": seed["summary"],
                "concept_type": seed.get("concept_type", "method"),
            }
            for seed in seeds
        }

    data["stats"] = data.get("stats") or {}
    data["stats"]["concept_count"] = len(nodes)
    data["stats"]["edge_count"] = len(edges)
    data["stats"]["soference_seed"] = datetime.now().isoformat(timespec="seconds")
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {JSON_PATH.name} ({len(nodes)} nodes, {len(edges)} edges)")


def main() -> int:
    print("SoFerence targeted seed")
    print(f"  root: {ROOT}")
    if not DB_PATH.exists():
        print("ERROR: okf_graph.db missing", file=sys.stderr)
        return 1

    bak = _backup()
    print(f"  backup dir: {bak}")

    import kuzu

    # Must open read-write; if inference holds lock this will fail.
    try:
        db = kuzu.Database(str(DB_PATH), read_only=False)
    except Exception as exc:
        print(
            f"ERROR: cannot open graph RW ({exc}). Stop inference/graph servers first.",
            file=sys.stderr,
        )
        return 2
    conn = kuzu.Connection(db)

    for seed in SEEDS:
        print(f"\n== {seed['id']} ==")
        _ensure_concept(conn, seed)
        seq = 0
        for pdf_rel, pages in seed.get("pdfs") or []:
            chunks = _extract(pdf_rel, pages)
            for ch in chunks:
                seq += 1
                _ensure_chunk_and_link(conn, seed["id"], ch, seq)
                print(f"  chunk p{ch['page']} from {ch['doc_id'][:60]}")
        for ch in seed.get("hand_chunks") or []:
            seq += 1
            _ensure_chunk_and_link(conn, seed["id"], ch, seq)
            print(f"  hand chunk p{ch['page']}")
        for pre in seed.get("requires") or []:
            # REQUIRES: concept requires prerequisite → (concept)-[:REQUIRES]->(pre)
            _ensure_edge(conn, seed["id"], pre, "REQUIRES")
        for un in seed.get("unlocks") or []:
            _ensure_edge(conn, seed["id"], un, "UNLOCKS")

    # Cross-domain bridge edges (paging → paged_attention → vllm)
    print("\n== bridge edges ==")
    _ensure_edge(conn, "paging", "virtual_memory", "REQUIRES")
    _ensure_edge(conn, "paged_attention", "paging", "REQUIRES")
    _ensure_edge(conn, "paged_attention", "attention_mechanism", "REQUIRES")
    _ensure_edge(conn, "vllm", "paged_attention", "REQUIRES")
    _ensure_edge(conn, "qlora", "low_rank_adaptation", "REQUIRES")
    _ensure_edge(conn, "paging", "paged_attention", "UNLOCKS")
    _ensure_edge(conn, "paged_attention", "vllm", "UNLOCKS")
    _ensure_edge(conn, "low_rank_adaptation", "qlora", "UNLOCKS")

    _patch_json(SEEDS)

    # Verify
    print("\n== verify ==")
    for cid in ("ai_agent", "paging", "paged_attention", "vllm", "qlora", "third_normal_form"):
        r = conn.execute(
            f"MATCH (chk:Chunk)-[:MENTIONS]->(c:Concept {{id: '{cid}'}}) RETURN count(chk)"
        )
        n = r.get_next()[0] if r.has_next() else 0
        print(f"  {cid}: chunks={n}")

    print("\nDone. Restart inference to reload CONCEPTS_DATA + embeddings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
