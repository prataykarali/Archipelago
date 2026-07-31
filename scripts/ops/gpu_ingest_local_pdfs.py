#!/usr/bin/env python3
"""Jul 21 2026–compliant GPU ingest (local pdfs/ only, NO HuggingFace).

Policy (Meeting Jul 21):
  - BOOKS: index / TOC / content-page listings / authors / subheadings ONLY.
    Never full book body text.
  - PAPERS/JOURNALS: full text allowed — priority content (≤15 papers pilot).
  - Scope: DBMS, DSA, OS (+ AI/ML pilot papers). 5–6 books via METADATA only.

Model: Ollama ``lib-qwen`` (from ingest/lib-qwen.gguf) on GPU.
Merges into okf_graph.db — does not wipe existing pilot nodes.

  fuser -k 5151/tcp   # free VRAM
  .venv/bin/python scripts/ops/gpu_ingest_local_pdfs.py --model lib-qwen
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PDF_ROOT = ROOT / "pdfs"
BOOKS_ROOT = PDF_ROOT / "archipelago-books-cs"
PAPERS_ROOT = PDF_ROOT / "papers"
DB_PATH = ROOT / "okf_graph.db"
JSON_PATH = ROOT / "okf_graph.json"
MANIFEST = BOOKS_ROOT / "CORPUS_MANIFEST.json"

# Pilot papers (≤15) — full text OK per Jul 21
PILOT_PAPERS = [
    "Lewis2020_RAG.pdf",
    "Hu2021_LoRA.pdf",
    "Dettmers2023_QLoRA.pdf",
    "Kwon2023_vLLM.pdf",
    "Vaswani2017_Attention_Is_All_You_Need.pdf",
    "Devlin2018_BERT.pdf",
    "Karpukhin2020_DPR.pdf",
    "Edge2024_GraphRAG.pdf",
    "Yao2022_ReAct.pdf",
    "Wei2022_ChainOfThought.pdf",
    "Ouyang2022_InstructGPT.pdf",
    "Rafailov2023_DPO.pdf",
    "Rumelhart1986_Backpropagation.pdf",
    "Kipf2016_GCN.pdf",
    "Bahdanau2014_Attention.pdf",
]

# Book dirs (METADATA only — no body PDFs in tree for Silberschatz etc.)
PILOT_BOOK_DIRS = [
    "database_system_concepts_silberschatz",
    "database_management_systems_ramakrishnan",
    "data_structures_algorithm_analysis_weiss",
    "operating_system_concepts_silberschatz",
    "ostep_three_easy_pieces",
    "introduction_to_algorithms_clrs",
]

# OSTEP: chapter *titles* only (filename = TOC line), never chapter body
OSTEP_TOC_ONLY = True

EXTRACT_PROMPT = """You are an OKF extraction engine for Archipelago (pilot, copyright-safe).
From the TEXT (paper abstract/body OR book TOC/index/author metadata only),
extract 1 to 4 teachable CONCEPTS as a JSON array.

Keys per object:
- concept_name (Title Case, max 6 words)
- concept_type: method|metric|technique|theory|tool|dataset|result|definition
- difficulty: foundational|intermediate|advanced|expert
- summary: 1-2 sentences
- prerequisites: [Title Case names]
- unlocks: [Title Case names]
- related_to: [{{"concept":"Name","relation":"uses"}}]
- tags: [lowercase-hyphen]

Rules: only concepts present in the text; CS/AI/OS/DBMS/DSA preferred; JSON array only.

TEXT:
{text}
"""

_TOC_HINT = re.compile(
    r"(?i)\b(contents|table of contents|index|preface|copyright|isbn|"
    r"about the author|list of figures|chapter\s+\d|part\s+[ivx]+)\b"
)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return s[:80] or "concept"


def _parse_json_array(raw: str) -> list:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        data = json.loads(s)
        return data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    except Exception:
        pass
    m = re.search(r"\[.*\]", s, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def extract_text_gpu(model: str, text: str, keep_alive: str = "30m") -> list[dict]:
    import ollama

    prompt = EXTRACT_PROMPT.format(text=(text or "")[:1800])
    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        keep_alive=keep_alive,
        options={"temperature": 0.1, "num_predict": 640, "num_ctx": 4096},
    )
    try:
        res = ollama.chat(**kwargs, think=False)
    except TypeError:
        res = ollama.chat(**kwargs)
    msg = res.get("message") if hasattr(res, "get") else getattr(res, "message", None)
    if isinstance(msg, dict):
        content = msg.get("content") or msg.get("thinking") or ""
    else:
        content = getattr(msg, "content", None) or getattr(msg, "thinking", None) or ""
    return _parse_json_array(str(content))


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("'", "\\'")


def _ensure_concept(conn, cid: str, name: str, summary: str, ctype: str, diff: str) -> None:
    safe_id = _esc(cid)
    r = conn.execute(f"MATCH (c:Concept {{id: '{safe_id}'}}) RETURN c.id")
    name_e, sum_e = _esc(name), _esc((summary or "")[:600])
    ctype, diff = _esc(ctype[:32]), _esc(diff[:32])
    if r.has_next():
        conn.execute(
            f"MATCH (c:Concept {{id: '{safe_id}'}}) "
            f"SET c.summary = '{sum_e}', c.name = '{name_e}'"
        )
    else:
        conn.execute(
            "CREATE (c:Concept {"
            f"id: '{safe_id}', name: '{name_e}', concept_type: '{ctype}', "
            f"difficulty: '{diff}', summary: '{sum_e}'"
            "})"
        )
        print(f"    + concept {cid}")


def _ensure_doc(conn, doc_id: str, title: str) -> None:
    safe = _esc(doc_id)
    r = conn.execute(f"MATCH (d:Document {{id: '{safe}'}}) RETURN d.id")
    if r.has_next():
        return
    conn.execute(
        "CREATE (d:Document {"
        f"id: '{safe}', doc_hash: '', page_count: 0, title: '{_esc(title)}', "
        "edition: '', page_label_map: ''"
        "})"
    )


def _ensure_chunk(conn, doc_id: str, concept_id: str, page: int, text: str, seq: int, kind: str = "pilot") -> None:
    chunk_id = f"{kind}_{concept_id}_{seq:03d}"
    node_id = f"{doc_id}_chunk_{chunk_id}"
    safe_node = _esc(node_id)
    r = conn.execute(f"MATCH (chk:Chunk {{id: '{safe_node}'}}) RETURN chk.id")
    if not r.has_next():
        _ensure_doc(conn, doc_id, Path(doc_id).name)
        conn.execute(
            "CREATE (chk:Chunk {"
            f"id: '{safe_node}', chunk_id: '{_esc(chunk_id)}', page_number: {int(page)}, "
            f"section_title: '{_esc(concept_id)}', text_passage: '{_esc((text or '')[:900])}', "
            "text_offset_start: 0, text_offset_end: 0, "
            "block_x: 0.0, block_y: 0.0, block_w: 0.0, block_h: 0.0"
            "})"
        )
        conn.execute(
            f"MATCH (d:Document {{id: '{_esc(doc_id)}'}}), (chk:Chunk {{id: '{safe_node}'}}) "
            f"CREATE (d)-[:HAS_CHUNK]->(chk)"
        )
    r2 = conn.execute(
        f"MATCH (chk:Chunk {{id: '{safe_node}'}})-[:MENTIONS]->(c:Concept {{id: '{_esc(concept_id)}'}}) "
        "RETURN chk.id"
    )
    if not r2.has_next():
        conn.execute(
            f"MATCH (chk:Chunk {{id: '{safe_node}'}}), (c:Concept {{id: '{_esc(concept_id)}'}}) "
            f"CREATE (chk)-[:MENTIONS]->(c)"
        )


def _ensure_edge(conn, frm: str, to: str, rel: str) -> None:
    if not frm or not to or frm == to:
        return
    r = conn.execute(
        f"MATCH (a:Concept {{id: '{_esc(frm)}'}}), (b:Concept {{id: '{_esc(to)}'}}) RETURN a.id"
    )
    if not r.has_next():
        return
    r2 = conn.execute(
        f"MATCH (a:Concept {{id: '{_esc(frm)}'}})-[:{rel}]->(b:Concept {{id: '{_esc(to)}'}}) RETURN a.id"
    )
    if r2.has_next():
        return
    conn.execute(
        f"MATCH (a:Concept {{id: '{_esc(frm)}'}}), (b:Concept {{id: '{_esc(to)}'}}) "
        f"CREATE (a)-[:{rel}]->(b)"
    )
    print(f"    + edge {frm} -[{rel}]-> {to}")


def _apply_items(conn, items, doc_id, page, passage, seq_start, new_nodes, new_edges, kind="paper"):
    seq = seq_start
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("concept_name") or "").strip()
        if len(name) < 2:
            continue
        cid = _slug(name)
        summary = str(item.get("summary") or "")[:500]
        ctype = str(item.get("concept_type") or "method")
        diff = str(item.get("difficulty") or "intermediate")
        _ensure_concept(conn, cid, name, summary, ctype, diff)
        seq += 1
        _ensure_chunk(conn, doc_id, cid, page, passage, seq, kind=kind)
        new_nodes.append(
            {
                "id": cid,
                "name": name,
                "label": name,
                "summary": summary,
                "concept_type": ctype,
                "difficulty": diff,
                "source": f"jul21_{kind}",
            }
        )
        for pre in item.get("prerequisites") or []:
            pre_id = _slug(str(pre))
            if pre_id and pre_id != cid:
                _ensure_concept(conn, pre_id, str(pre), f"Prerequisite of {name}.", "definition", "foundational")
                _ensure_edge(conn, cid, pre_id, "REQUIRES")
                new_edges.append(
                    {"from_id": cid, "to_id": pre_id, "edge_type": "REQUIRES", "relation": "requires", "source": "jul21"}
                )
        for un in item.get("unlocks") or []:
            un_id = _slug(str(un))
            if un_id and un_id != cid:
                _ensure_concept(conn, un_id, str(un), f"Unlocked by {name}.", "method", "intermediate")
                _ensure_edge(conn, cid, un_id, "UNLOCKS")
                new_edges.append(
                    {"from_id": cid, "to_id": un_id, "edge_type": "UNLOCKS", "relation": "unlocks", "source": "jul21"}
                )
    return seq


def _patch_json(new_nodes, new_edges) -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    viz = data.setdefault("visualization", {})
    nodes = viz.setdefault("nodes", [])
    edges = viz.setdefault("edges", [])
    by_id = {n.get("id"): n for n in nodes if n.get("id")}
    for n in new_nodes:
        if n["id"] in by_id:
            by_id[n["id"]].update({k: n[k] for k in ("summary", "name", "label") if n.get(k)})
        else:
            nodes.append(n)
            by_id[n["id"]] = n
    for e in new_edges:
        if not any(
            x.get("from_id") == e["from_id"] and x.get("to_id") == e["to_id"] and x.get("edge_type") == e["edge_type"]
            for x in edges
        ):
            edges.append(e)
    concepts = data.get("concepts")
    if isinstance(concepts, dict):
        for n in new_nodes:
            concepts[n["id"]] = n
    data.setdefault("stats", {})["jul21_gpu_ingest"] = datetime.now().isoformat(timespec="seconds")
    data["stats"]["compliance"] = "books=metadata/TOC only; papers=full; no HF"
    data["stats"]["concept_count"] = len(nodes)
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  patched JSON: {len(nodes)} nodes")


def ingest_book_metadata(conn, model, new_nodes, new_edges) -> int:
    """Books: METADATA.json + synthetic TOC from chapter filenames. NO body text."""
    n = 0
    for dirname in PILOT_BOOK_DIRS:
        bdir = BOOKS_ROOT / dirname
        if not bdir.exists():
            print(f"  SKIP book dir {dirname}")
            continue
        meta_path = bdir / "METADATA.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        title = meta.get("title") or dirname.replace("_", " ").title()
        authors = meta.get("authors") or meta.get("author") or "Unknown"
        subject = meta.get("subject") or meta.get("subjects") or ""
        if isinstance(authors, list):
            authors = ", ".join(str(a) for a in authors)
        if isinstance(subject, list):
            subject = ", ".join(str(s) for s in subject)

        # TOC lines from chapter PDF *names* only (no opening those PDFs for body)
        toc_lines = []
        for pdf in sorted(bdir.glob("*.pdf")):
            # strip numbering prefixes → chapter heading
            stem = pdf.stem
            stem = re.sub(r"^\d+[_-]?", "", stem)
            stem = stem.replace("_", " ").replace("-", " ")
            toc_lines.append(stem[:120])
        toc_block = "\n".join(f"- {t}" for t in toc_lines[:40]) or "(no chapter files; metadata only)"

        passage = (
            f"BOOK METADATA (copyright-safe pilot — no body text)\n"
            f"Title: {title}\nAuthors: {authors}\nSubject: {subject}\n"
            f"Directory: {dirname}\n"
            f"Table of Contents / chapter index:\n{toc_block}\n"
        )
        print(f"\n== BOOK meta {dirname} ==")
        items = extract_text_gpu(model, passage)
        # Always seed a catalog concept for the book itself
        book_id = _slug(title) if title else _slug(dirname)
        summary = f"{title} by {authors}. Subject: {subject or 'CS pilot'}. Indexed via TOC/metadata only (Jul 21 compliance)."
        _ensure_concept(conn, book_id, title, summary, "dataset", "foundational")
        doc_id = f"books/{dirname}/METADATA"
        _ensure_chunk(conn, doc_id, book_id, 1, passage, 1, kind="book_meta")
        new_nodes.append(
            {
                "id": book_id,
                "name": title,
                "label": title,
                "summary": summary,
                "concept_type": "dataset",
                "difficulty": "foundational",
                "shelf": meta.get("call_number") or meta.get("shelf") or "",
                "authors": authors,
                "source": "jul21_book_metadata",
            }
        )
        n += 1
        if items:
            _apply_items(conn, items, doc_id, 1, passage, 1, new_nodes, new_edges, kind="book_meta")
            n += len(items)
        print(f"  extracted {len(items)} concepts from metadata/TOC")
    return n


def ingest_papers(conn, model, pages_per_paper: int, new_nodes, new_edges) -> int:
    """Papers: full text allowed — first N pages each."""
    import fitz

    n = 0
    for fname in PILOT_PAPERS:
        path = PAPERS_ROOT / fname
        if not path.exists():
            # also under archipelago-books-cs/papers
            alt = BOOKS_ROOT / "papers" / fname
            path = alt if alt.exists() else path
        if not path.exists():
            print(f"  SKIP missing paper {fname}")
            continue
        print(f"\n== PAPER {fname} ==")
        doc = fitz.open(str(path))
        doc_id = f"papers/{fname}"
        seq = 0
        for pnum in range(1, min(pages_per_paper, len(doc)) + 1):
            text = re.sub(r"\s+", " ", doc[pnum - 1].get_text() or "").strip()
            if len(text) < 60:
                continue
            t0 = time.time()
            items = extract_text_gpu(model, text)
            ms = int((time.time() - t0) * 1000)
            print(f"  p{pnum}: {len(items)} concepts {ms}ms")
            seq = _apply_items(conn, items, doc_id, pnum, text, seq, new_nodes, new_edges, kind="paper")
            n += len(items)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="lib-qwen")
    ap.add_argument("--pages-per-paper", type=int, default=3)
    ap.add_argument("--papers-only", action="store_true")
    ap.add_argument("--books-only", action="store_true")
    ap.add_argument("--keep-alive", default="30m")
    args = ap.parse_args()

    print("Jul 21 compliant GPU ingest — local pdfs/ only (NO HF)")
    print("  books = METADATA + TOC filenames only | papers = full (≤15)")
    print(f"  model={args.model}")

    if not DB_PATH.exists():
        print("ERROR: okf_graph.db missing", file=sys.stderr)
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = ROOT / f"okf_graph.bak-jul21-{stamp}"
    bak.mkdir(exist_ok=True)
    for p in (DB_PATH, JSON_PATH):
        if p.exists():
            shutil.copy2(p, bak / p.name)
    print(f"  backup → {bak.name}")

    import ollama
    import kuzu

    print("  warming lib-qwen on GPU…")
    t0 = time.time()
    try:
        ollama.chat(
            model=args.model,
            messages=[{"role": "user", "content": "[]"}],
            stream=False,
            think=False,
            keep_alive=args.keep_alive,
            options={"num_predict": 4, "temperature": 0},
        )
    except TypeError:
        ollama.chat(
            model=args.model,
            messages=[{"role": "user", "content": "[]"}],
            stream=False,
            keep_alive=args.keep_alive,
            options={"num_predict": 4},
        )
    print(f"  warm {int((time.time()-t0)*1000)}ms")

    try:
        db = kuzu.Database(str(DB_PATH), read_only=False)
    except Exception as exc:
        print(f"ERROR open RW: {exc} — stop inference first", file=sys.stderr)
        return 2
    conn = kuzu.Connection(db)
    new_nodes: list[dict] = []
    new_edges: list[dict] = []

    if not args.papers_only:
        ingest_book_metadata(conn, args.model, new_nodes, new_edges)
    if not args.books_only:
        ingest_papers(conn, args.model, args.pages_per_paper, new_nodes, new_edges)

    print("\n== bridge edges ==")
    for a, b, rel in [
        ("paging", "virtual_memory", "REQUIRES"),
        ("paged_attention", "paging", "REQUIRES"),
        ("vllm", "paged_attention", "REQUIRES"),
        ("qlora", "low_rank_adaptation", "REQUIRES"),
        ("low_rank_adaptation", "qlora", "UNLOCKS"),
        ("paging", "paged_attention", "UNLOCKS"),
        ("paged_attention", "vllm", "UNLOCKS"),
        ("rag", "retrieval_augmented_generation", "RELATED")  # may no-op if RELATED missing
        if False
        else ("ai_agent", "reinforcement_learning", "REQUIRES"),
    ]:
        try:
            _ensure_edge(conn, a, b, rel)
        except Exception as e:
            print(f"  bridge skip {a}->{b}: {e}")

    _patch_json(new_nodes, new_edges)
    print(f"\nDone. nodes_touched≈{len(new_nodes)}. Restart inference + pin qwen3.5:0.8b.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
