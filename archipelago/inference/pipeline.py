from __future__ import annotations

from collections.abc import Generator, Iterator
import json
import logging
import os
import re
import threading
import time as _time
from typing import Any

import kuzu

from archipelago.inference import state as st
from archipelago.inference.catalog_ods import format_catalog_reply
from archipelago.inference.curriculum import find_curriculum_chains
from archipelago.inference.graph_lock import graph_lock
from archipelago.inference.synthesis import prettify_doc_title
from archipelago.inference.synthesis_cleaner import enforce_four_tier, is_glued

logger = logging.getLogger(__name__)


def _t():
    return _time.perf_counter()


def _tlog(logs, step: str, start: float, **extra):
    dur = _time.perf_counter() - start
    detail = f"dur={dur:.3f}s"
    if extra:
        detail += " " + " ".join(f"{k}={v}" for k, v in extra.items())
    logs.append({"step": step, "status": "OK", "details": detail})

def _ensure_concepts_loaded() -> None:
    """Ensure CONCEPTS_DATA is loaded (lazy init for tests/imports)."""
    if not st.CONCEPTS_DATA:
        # Import here to avoid circular import
        from archipelago.inference.routes_chat import init_concepts_data
        init_concepts_data()
# Strict cosine gate only applies when real embeddings are loaded. Lexical-only
# mode uses a lower blended floor so multi-word pedagogical questions still hit
# known concept names (see docs/reports/FOUR_MODULE_ARCHITECTURE_PLAN.md).
_COSINE_KILL_SWITCH = 0.75
_LEXICAL_STRONG_SURFACE = 0.55
_LEXICAL_ONLY_BLENDED_FLOOR = 0.40
_MAX_CHUNKS_IN_PAYLOAD = 6
_OLLAMA_MAX_OUTPUT_TOKENS = int(os.environ.get("ARCHIPELAGO_OLLAMA_NUM_PREDICT", "320"))
_CHUNK_PASSAGE_CHARS = 420

# Single-flight Ollama: 0.8B on 4 GB cannot serve two concurrent chats cleanly.
# Queue / stream budgets stay tight so a hung CPU runner never strands the UI.
_OLLAMA_LOCK = threading.Lock()
_OLLAMA_BUSY = False
_OLLAMA_BUSY_SINCE = 0.0
_OLLAMA_QUEUE_WAIT_S = float(os.environ.get("ARCHIPELAGO_OLLAMA_QUEUE_WAIT_S", "12"))
_OLLAMA_STREAM_TIMEOUT_S = float(os.environ.get("ARCHIPELAGO_OLLAMA_STREAM_TIMEOUT_S", "60"))
_OLLAMA_FIRST_TOKEN_TIMEOUT_S = float(
    os.environ.get("ARCHIPELAGO_OLLAMA_FIRST_TOKEN_TIMEOUT_S", "20")
)
_OLLAMA_STALE_HOLD_S = float(os.environ.get("ARCHIPELAGO_OLLAMA_STALE_HOLD_S", "75"))
# When the runner fell off the GPU, do not queue — grounded card is faster/honest.
_OLLAMA_CPU_QUEUE_WAIT_S = float(os.environ.get("ARCHIPELAGO_OLLAMA_CPU_QUEUE_WAIT_S", "0.5"))
_OLLAMA_CPU_STREAM_TIMEOUT_S = float(
    os.environ.get("ARCHIPELAGO_OLLAMA_CPU_STREAM_TIMEOUT_S", "35")
)
_OLLAMA_CPU_FIRST_TOKEN_TIMEOUT_S = float(
    os.environ.get("ARCHIPELAGO_OLLAMA_CPU_FIRST_TOKEN_TIMEOUT_S", "12")
)


def _ollama_keep_alive() -> int | str:
    """Ollama keep_alive: int seconds, or duration str. -1 (int) = forever.

    Env often sets OLLAMA_KEEP_ALIVE=-1 as a string; the Go server rejects
    duration \"-1\" without a unit, so coerce bare -1/forever to int -1.
    """
    raw = (os.environ.get("OLLAMA_KEEP_ALIVE") or "-1").strip()
    if raw.lower() in ("-1", "forever", "inf", "infinite", "0"):
        return -1
    try:
        return int(raw)
    except ValueError:
        return raw  # e.g. "30m", "24h"


# Pin qwen on VRAM forever so idle nvidia-smi still shows the SLM resident.
_OLLAMA_KEEP_ALIVE = _ollama_keep_alive()

# Kill-switch already ran before Stage 5. NEVER instruct the model to re-judge
# domain scope — that caused false "out of scope" refusals on RAG/DBMS queries.
# Keep short for 0.8B context + latency.
_SLM_SYSTEM_INSTRUCTION: str = (
    "You are Archipelago, university AI/ML index librarian "
    "(DBMS, OS, DSA, PEFT, RAG, LLMs, OS paging, agents).\n"
    "Retrieval already succeeded — answer ONLY from TOPOLOGICAL MAP + SOURCE CHUNKS. "
    "Never refuse as out of scope.\n"
    "Shape: (1) direct factual open (2) mechanism/LaTeX if useful "
    "(3) cite only [S1],[S2],… from chunks. "
    "No greetings, no source list, no doc_id/chunk ids, no Style/LAYOUT tokens."
)

# ── Stage 1 — Guardrails ──────────────────────────────────────────────────
_CHAR_LIMIT = 500
_POLITE_NOISE_RE = re.compile(
    r"(?i)\b("
    r"hey|hi\b|hello\b|thanks?\b|thank you|please\b|can you\b|could you\b|"
    r"would you\b|i want\b|i wanna\b|explain to me\b|tell me about\b|"
    r"discuss about\b|talk about\b|ok\s+so\b|alright\s+so\b|okay\s+so\b|"
    r"by the way\b|btw\b|anyway\b|well\b|so\b"
    r")\s*[,.]?\s*",
    re.IGNORECASE,
)


def _stage1_guardrails(user_query: str) -> dict[str, Any] | None:
    """Validate length and strip pleasantries."""
    if len(user_query) > _CHAR_LIMIT:
        return {
            "reject": True,
            "payload": json.dumps({"error": "Query too long. Limit to 500 characters."}),
            "logs": [
                {
                    "step": "Guardrails",
                    "status": "Reject",
                    "details": f"Length {len(user_query)} > {_CHAR_LIMIT}",
                }
            ],
        }
    normalized = _POLITE_NOISE_RE.sub("", user_query).strip()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        normalized = user_query.strip()
    return {"reject": False, "normalized_query": normalized}


# ── Stage 2 — Vector Search & Kill-Switch ──────────────────────────────────
def _cosine_sim(a, b) -> float:
    import numpy as np

    a_n = a.numpy() if hasattr(a, "numpy") else np.array(a)
    b_n = b.numpy() if hasattr(b, "numpy") else np.array(b)
    a_n = a_n.flatten()
    b_n = b_n.flatten()
    dot = float(np.dot(a_n, b_n))
    norm_a = float(np.dot(a_n, a_n)) ** 0.5
    norm_b = float(np.dot(b_n, b_n)) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _stage2_vector_search(normalized_query: str) -> dict[str, Any] | None:
    """Rank concepts and apply domain kill-switch (cosine or lexical floor)."""
    if not st.CONCEPTS_DATA:
        logger.warning("Stage 2: CONCEPTS_DATA empty")
        return None

    from archipelago.inference.ranking import rank_concepts

    ranked = rank_concepts(normalized_query, top_k=15)
    if not ranked:
        return None

    best = ranked[0]
    best_id = str(best.get("id") or "")
    best_sim = float(best.get("cos") or 0)
    lexical = float(best.get("lexical") or 0)
    blended = float(best.get("blended") or 0)
    name_hit = bool(best.get("name_hit"))

    embeddings_live = bool(st.use_embeddings and st.CONCEPT_EMBEDDINGS)
    strong_surface = bool(name_hit) or lexical >= _LEXICAL_STRONG_SURFACE
    if embeddings_live:
        # Real vectors: keep the documented 0.75 cosine gate, with lexical escape.
        if best_sim < _COSINE_KILL_SWITCH and not strong_surface:
            return None
    else:
        # Lexical-only: require a real name/alias hit or a strong blended score.
        if not strong_surface or blended < _LEXICAL_ONLY_BLENDED_FLOOR:
            return None

    concept = st.CONCEPTS_DATA.get(best_id, {})
    concept_name = concept.get("name") or concept.get("label") or best_id
    return {
        "anchor_id": best_id,
        "concept_name": concept_name,
        "cosine_sim": best_sim,
        "lexical": lexical,
        "blended": blended,
    }


# ── Stage 3 — Graph Traversal ──────────────────────────────────────────────
_MAX_PREREQS = 6
_MAX_UNLOCKS = 6


def _stage3_graph_traversal(anchor_id: str) -> dict[str, Any]:
    """Run REQUIRES / UNLOCKS traversal and chunk retrieval."""
    result: dict[str, Any] = {
        "anchor_id": anchor_id,
        "prerequisites": [],
        "unlocks": [],
        "chunks": [],
    }
    safe_anchor = anchor_id.replace("'", "\\'")

    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)

            # Upstream
            try:
                res = conn.execute(f"""
                    MATCH (c:Concept {{id: '{safe_anchor}'}})-[:REQUIRES*1..2]->(p:Concept)
                    RETURN DISTINCT p.id, p.name, p.summary
                """)
                while res.has_next():
                    row = res.get_next()
                    result["prerequisites"].append(
                        {
                            "id": row[0],
                            "name": row[1],
                            "summary": row[2] or "",
                        }
                    )
                result["prerequisites"] = result["prerequisites"][:_MAX_PREREQS]
            except Exception as exc:
                logger.warning("REQUIRES traversal failed: %s", exc)

            # Downstream
            try:
                res = conn.execute(f"""
                    MATCH (c:Concept {{id: '{safe_anchor}'}})
                    -[:UNLOCKS*1..2]->(u:Concept)
                    RETURN DISTINCT u.id, u.name, u.summary
                """)
                seen: set[str] = set()
                while res.has_next():
                    row = res.get_next()
                    uid = str(row[0] or "")
                    if uid not in seen:
                        seen.add(uid)
                        result["unlocks"].append(
                            {
                                "id": uid,
                                "name": row[1],
                                "summary": row[2] or "",
                            }
                        )
                    if len(result["unlocks"]) >= _MAX_UNLOCKS:
                        break
            except Exception as exc:
                logger.warning("UNLOCKS traversal failed: %s", exc)

            # Chunks
            try:
                res = conn.execute(f"""
                    MATCH (d:Document)-[:HAS_CHUNK]->(chk:Chunk)-[:MENTIONS]->(c:Concept {{id: '{safe_anchor}'}})
                    RETURN d.id, d.title, chk.id, chk.page_number, chk.section_title, chk.text_passage
                    LIMIT 20
                """)
                _INDEX_RE = re.compile(r"Index_|TableOfContents|Index_2015_", re.IGNORECASE)
                while res.has_next() and len(result["chunks"]) < _MAX_CHUNKS_IN_PAYLOAD:
                    row = res.get_next()
                    doc_id = str(row[0] or "")
                    title = str(row[1] or "")
                    if _INDEX_RE.search(title):
                        continue
                    result["chunks"].append(
                        {
                            "doc_id": doc_id,
                            "title": title,
                            "chunk_id": str(row[2] or ""),
                            "page_number": int(row[3]) if row[3] is not None else 1,
                            "section_title": str(row[4] or ""),
                            "text_passage": str(row[5] or ""),
                        }
                    )
            except Exception as exc:
                logger.warning("Chunk retrieval error: %s", exc)

    except Exception as exc:
        logger.error("Graph connection error: %s", exc)

    return result


# ── Stage 4 — Payload Assembly ─────────────────────────────────────────────
def _stage4_build_payload(graph_result: dict[str, Any], normalized_query: str) -> str:
    """Build structured context payload for Ollama SLM."""
    parts: list[str] = []
    anchor_id = graph_result.get("anchor_id", "") or ""

    anchor_name = ""
    if anchor_id and anchor_id in st.CONCEPTS_DATA:
        anchor_name = st.CONCEPTS_DATA[anchor_id].get("name") or anchor_id

    parts.append("=== TOPOLOGICAL MAP ===")
    prereqs = graph_result.get("prerequisites") or []
    unlocks = graph_result.get("unlocks") or []
    p_names = [p.get("name") or p.get("id", "") for p in prereqs]
    u_names = [u.get("name") or u.get("id", "") for u in unlocks]
    parts.append(f"Prerequisites (REQUIRES): {' | '.join(p_names) if p_names else '(none)'}")
    parts.append(f"Target Concept: {anchor_name or anchor_id or '(unknown)'}")
    parts.append(f"Unlocked Applications (UNLOCKS): {' | '.join(u_names) if u_names else '(none)'}")

    parts.append("")
    parts.append("=== SOURCE CHUNKS ===")
    chunks = graph_result.get("chunks") or []
    for idx, chunk in enumerate(chunks, start=1):
        page = chunk.get("page_number") or 1
        title = chunk.get("title") or "Unknown Source"
        passage = (chunk.get("text_passage") or "")[:_CHUNK_PASSAGE_CHARS]
        parts.append(f"[S{idx}] Source: {title}; Page: {page}\n{passage}")

    parts.append("")
    parts.append("=== NORMALIZED USER QUERY ===")
    parts.append(normalized_query)

    return "\n".join(parts)


# ── Stage 5 — Local Ollama GPU SLM only ─────────────────────────────────────
_OLLAMA_MODEL = os.environ.get("ARCHIPELAGO_OLLAMA_MODEL") or os.environ.get(
    "OKF_MODEL_NAME", "qwen3.5:0.8b"
)
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


def _message_content(response: Any, *, strip_ws: bool = False) -> str:
    """Extract assistant text from ollama ChatResponse / dict / Message.

    IMPORTANT: do NOT strip stream deltas — Ollama often sends leading spaces as
    their own tokens (" is", " a"). strip() glued words into "SQLisa...".
    """
    if response is None:
        return ""
    msg = None
    # ChatResponse is a pydantic model; prefer attribute access over .get()
    if hasattr(response, "message"):
        msg = response.message
    elif hasattr(response, "get"):
        # Fallback for dict-like responses
        try:
            msg = response.get("message")
        except Exception:
            msg = None
    if msg is None:
        return ""
    if isinstance(msg, dict):
        text = msg.get("content") or ""
        if not text and not strip_ws:
            # Never use thinking tokens for live stream (burns GPU, no user text).
            text = ""
    else:
        text = getattr(msg, "content", None) or ""
        if not text and strip_ws:
            # Non-stream final only: rare builds park answer in thinking.
            text = getattr(msg, "thinking", None) or ""
    out = str(text)
    return out.strip() if strip_ws else out


def _ollama_client():
    import ollama

    return ollama.Client(host=_OLLAMA_HOST)


def ollama_runtime_info() -> dict[str, Any]:
    """Best-effort Ollama residency (GPU vs CPU) for readiness / UI badges."""
    host = _OLLAMA_HOST.rstrip("/")
    try:
        import urllib.request

        with urllib.request.urlopen(f"{host}/api/ps", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") or []
        device = "unknown"
        processor = ""
        loaded = False
        size_vram_out = 0
        for m in models:
            name = str(m.get("name") or m.get("model") or "")
            model_key = _OLLAMA_MODEL.split(":")[0].lower()
            if "qwen" not in name.lower() and model_key not in name.lower():
                # Prefer our configured model; if only one resident model, use it.
                if len(models) != 1:
                    continue
            loaded = True
            size_vram = m.get("size_vram")
            if size_vram is None:
                size_vram = (m.get("details") or {}).get("size_vram")
            try:
                size_vram_out = int(size_vram or 0)
            except (TypeError, ValueError):
                size_vram_out = 0
            # Ollama /api/ps: size_vram > 0 ⇒ weights on GPU; 0 ⇒ CPU-only runner.
            if size_vram_out > 0:
                device = "gpu"
                processor = f"GPU (vram={size_vram_out})"
            else:
                device = "cpu"
                processor = "100% CPU"
            break
        return {
            "reachable": True,
            "loaded": loaded,
            "device": device,
            "processor": processor,
            "size_vram": size_vram_out,
            "model": _OLLAMA_MODEL,
            "busy": ollama_busy(),
            "busy_for_s": round(max(0.0, _time.monotonic() - _OLLAMA_BUSY_SINCE), 1)
            if _OLLAMA_BUSY
            else 0.0,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "loaded": False,
            "device": "unknown",
            "processor": "",
            "model": _OLLAMA_MODEL,
            "busy": ollama_busy(),
            "busy_for_s": 0.0,
            "error": str(exc),
        }


def warm_ollama_gpu(timeout_s: float = 120.0) -> dict[str, Any]:
    """Load qwen onto the GPU and pin it (keep_alive=-1 / Forever)."""
    t0 = _time.time()
    client = _ollama_client()
    acquired = _acquire_ollama(timeout_s=min(30.0, timeout_s))
    if not acquired:
        raise RuntimeError("Ollama warm skipped — lock busy (another synthesis running)")
    try:
        response = client.chat(
            model=_OLLAMA_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            stream=False,
            think=False,
            keep_alive=_OLLAMA_KEEP_ALIVE,
            options={
                "temperature": 0.0,
                "num_predict": 4,
                "num_ctx": int(os.environ.get("ARCHIPELAGO_OLLAMA_NUM_CTX", "2048")),
            },
        )
        _ = _message_content(response, strip_ws=True)
    finally:
        _release_ollama()
    runtime = ollama_runtime_info()
    return {
        "ok": True,
        "model": _OLLAMA_MODEL,
        "host": _OLLAMA_HOST,
        "keep_alive": _OLLAMA_KEEP_ALIVE,
        "warm_ms": int((_time.time() - t0) * 1000),
        "timeout_budget_s": timeout_s,
        "device": runtime.get("device") or "unknown",
        "processor": runtime.get("processor") or "",
    }


def ollama_busy() -> bool:
    """True if another request currently holds the Ollama single-flight lock."""
    _maybe_clear_stale_ollama_lock()
    return _OLLAMA_BUSY or _OLLAMA_LOCK.locked()


def _maybe_clear_stale_ollama_lock() -> None:
    """Release a lock held longer than the stale budget (hung CPU / dead client)."""
    global _OLLAMA_BUSY, _OLLAMA_BUSY_SINCE
    if not _OLLAMA_BUSY or _OLLAMA_BUSY_SINCE <= 0:
        return
    held = _time.monotonic() - _OLLAMA_BUSY_SINCE
    if held < _OLLAMA_STALE_HOLD_S:
        return
    logger.warning(
        "Clearing stale Ollama lock held for %.1fs (budget=%.0fs) — "
        "likely hung CPU fallback or dropped client",
        held,
        _OLLAMA_STALE_HOLD_S,
    )
    _OLLAMA_BUSY = False
    _OLLAMA_BUSY_SINCE = 0.0
    try:
        _OLLAMA_LOCK.release()
    except RuntimeError:
        pass


def _acquire_ollama(timeout_s: float | None = None) -> bool:
    """Block until Ollama free or timeout. Sets _OLLAMA_BUSY while held."""
    global _OLLAMA_BUSY, _OLLAMA_BUSY_SINCE
    _maybe_clear_stale_ollama_lock()
    wait = _OLLAMA_QUEUE_WAIT_S if timeout_s is None else timeout_s
    ok = _OLLAMA_LOCK.acquire(timeout=wait)
    if ok:
        _OLLAMA_BUSY = True
        _OLLAMA_BUSY_SINCE = _time.monotonic()
    return ok


def _release_ollama() -> None:
    global _OLLAMA_BUSY, _OLLAMA_BUSY_SINCE
    _OLLAMA_BUSY = False
    _OLLAMA_BUSY_SINCE = 0.0
    try:
        _OLLAMA_LOCK.release()
    except RuntimeError:
        pass


def _ollama_chat_options() -> dict[str, Any]:
    return {
        "temperature": 0.1,
        "top_p": 0.9,
        "num_predict": _OLLAMA_MAX_OUTPUT_TOKENS,
        # Cap ctx for 0.8B speed on 4GB VRAM (RTX 2050 class).
        "num_ctx": int(os.environ.get("ARCHIPELAGO_OLLAMA_NUM_CTX", "2048")),
    }


def _ollama_timeout_budgets() -> tuple[float, float, float]:
    """Return (queue_wait_s, first_token_s, total_stream_s) for current device."""
    device = str(ollama_runtime_info().get("device") or "unknown")
    if device == "gpu":
        return (
            _OLLAMA_QUEUE_WAIT_S,
            _OLLAMA_FIRST_TOKEN_TIMEOUT_S,
            _OLLAMA_STREAM_TIMEOUT_S,
        )
    # CPU / unknown: laptop resume often leaves CUDA dead — keep budgets tiny.
    return (
        _OLLAMA_CPU_QUEUE_WAIT_S,
        _OLLAMA_CPU_FIRST_TOKEN_TIMEOUT_S,
        _OLLAMA_CPU_STREAM_TIMEOUT_S,
    )


def _collect_ollama_stream_with_timeout(
    context_payload: str,
    *,
    total_timeout_s: float | None = None,
    first_token_timeout_s: float | None = None,
) -> str:
    """Run Ollama stream in a worker thread; abort to grounded path on hang.

    GPU SLM should finish well under the budgets. If the runner fell to CPU
    (laptop resume / driver glitch), we refuse to hold the single-flight lock
    for minutes and surface a timeout instead.
    """
    _queue_wait, default_first, default_total = _ollama_timeout_budgets()
    del _queue_wait  # acquire path reads budgets separately
    total_budget = default_total if total_timeout_s is None else float(total_timeout_s)
    first_budget = default_first if first_token_timeout_s is None else float(first_token_timeout_s)
    box: dict[str, Any] = {"parts": [], "error": None, "done": False}
    stop = threading.Event()

    def _worker() -> None:
        try:
            client = _ollama_client()
            stream = client.chat(
                model=_OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": _SLM_SYSTEM_INSTRUCTION},
                    {"role": "user", "content": context_payload},
                ],
                stream=True,
                think=False,
                keep_alive=_OLLAMA_KEEP_ALIVE,
                options=_ollama_chat_options(),
            )
            for chunk in stream:
                if stop.is_set():
                    break
                piece = _message_content(chunk, strip_ws=False)
                if piece:
                    box["parts"].append(piece)
        except Exception as exc:
            box["error"] = exc
        finally:
            box["done"] = True

    thread = threading.Thread(target=_worker, name="ollama-stream", daemon=True)
    thread.start()
    deadline = _time.monotonic() + total_budget
    first_deadline = _time.monotonic() + first_budget
    saw_token = False
    while not box["done"]:
        if box["parts"]:
            saw_token = True
        now = _time.monotonic()
        if not saw_token and now >= first_deadline:
            stop.set()
            raise TimeoutError(
                f"Ollama first token timeout after {first_budget:.0f}s "
                f"(GPU SLM unresponsive — often CPU fallback after resume)"
            )
        if now >= deadline:
            stop.set()
            raise TimeoutError(
                f"Ollama stream timeout after {total_budget:.0f}s (tokens={len(box['parts'])})"
            )
        thread.join(timeout=0.25)
    if box["error"] is not None:
        raise RuntimeError(f"Ollama stream failed: {box['error']}") from box["error"]
    text = "".join(box["parts"]).strip()
    if not text:
        raise RuntimeError(f"Ollama model {_OLLAMA_MODEL!r} returned empty content")
    return text


def _stage5_ollama_synthesis(context_payload: str) -> str:
    """Synthesize grounded answer via local Ollama (qwen3.5:0.8b on GPU).

    Model only sees the topological map + chunks, never the raw corpus.
    think=False so Qwen3.5 does not burn tokens on chain-of-thought.
    keep_alive pins weights on VRAM between turns. Single-flight lock.
    """
    queue_wait, _, _ = _ollama_timeout_budgets()
    if not _acquire_ollama(timeout_s=queue_wait):
        raise RuntimeError("Ollama queue timeout — another synthesis still running")
    try:
        return _collect_ollama_stream_with_timeout(context_payload)
    finally:
        _release_ollama()


def _stage5_ollama_stream(context_payload: str) -> Iterator[str]:
    """Token stream from Ollama under the single-flight lock (with hard timeout)."""
    queue_wait, _, _ = _ollama_timeout_budgets()
    if not _acquire_ollama(timeout_s=queue_wait):
        # Caller falls back to grounded card — do not leave the UI on "in queue".
        yield (
            "\n[Queue] Local GPU SLM is still finishing another answer. "
            "Serving the catalog card instead.\n"
        )
        return
    try:
        # Collect under timeout (avoids endless CPU hang), then yield once.
        # Downstream cleaner needs the full draft anyway.
        text = _collect_ollama_stream_with_timeout(context_payload)
        yield text
    finally:
        _release_ollama()


def _stage5_synthesize(context_payload: str) -> tuple[str, str, str]:
    """Stage 5 is Ollama GPU SLM synthesis."""
    text = _stage5_ollama_synthesis(context_payload)
    if not text:
        raise RuntimeError(f"Ollama model {_OLLAMA_MODEL!r} returned empty content")
    return text, "ollama", f"model={_OLLAMA_MODEL} keep_alive={_OLLAMA_KEEP_ALIVE}"


# ── Public Entry Point ─────────────────────────────────────────────────────
def run_archipelago_inference(
    user_query: str,
    history: list[dict[str, Any]] | None = None,
    session_id: str = "default_session",
) -> dict[str, Any]:
    """Execute the 5-stage inference pipeline.

    Returns dict with keys: text, anchor_concept, prerequisites, unlocks,
    citations, routing, logs, generation.
    """
    _ensure_concepts_loaded()
    logs: list[dict[str, str]] = []

    # ── Stage 1: Guardrails ──────────────────────────────────────────────
    st1 = _stage1_guardrails(user_query)
    if st1.get("reject"):
        return {
            "text": st1["payload"],
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "routing": {"route": "input_error", "reason": "query_too_long"},
            "logs": st1.get("logs", []),
            "generation": {"provider": "none", "source": "guardrail"},
        }

    normalized_query: str = st1["normalized_query"]
    logs.append({"step": "Guardrails", "status": "OK", "details": "Normalized query"})

    # ── Stage 2: Vector Search & Kill-Switch ─────────────────────────────
    vector_hit = _stage2_vector_search(normalized_query)
    if vector_hit is None:
        logs.append(
            {
                "step": "VectorSearch",
                "status": "Kill-Switch",
                "details": "Cosine below 0.75 threshold",
            }
        )
        return {
            "text": "I'm sorry, that topic isn't covered in the current library catalog. Please ask a question related to AI/ML, DBMS, OS, DSA, or Math for ML.",
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "routing": {"route": "kill_switch", "reason": "cosine_below_threshold"},
            "logs": logs,
            "generation": {"provider": "none", "source": "kill_switch"},
        }

    anchor_id = vector_hit["anchor_id"]
    anchor_name = vector_hit["concept_name"]
    logs.append({"step": "VectorSearch", "status": "OK", "details": f"Anchor={anchor_id}"})

    # ── Stage 3: Graph Traversal ─────────────────────────────────────────
    graph_result = _stage3_graph_traversal(anchor_id)
    prereqs = graph_result.get("prerequisites") or []
    unlocks = graph_result.get("unlocks") or []
    chunks = graph_result.get("chunks") or []
    logs.append(
        {
            "step": "GraphTraversal",
            "status": "OK",
            "details": f"Prereqs={len(prereqs)} Unlocks={len(unlocks)} Chunks={len(chunks)}",
        }
    )

    # ── Stage 4: Payload Assembly ────────────────────────────────────────
    context_payload = _stage4_build_payload(graph_result, normalized_query)
    logs.append(
        {
            "step": "PayloadAssembly",
            "status": "OK",
            "details": f"Payload chars={len(context_payload)}",
        }
    )
    # Build citation payloads (needed for cleaner + stream footer)
    from urllib.parse import quote

    citation_payloads: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks[:15], start=1):  # limit to 15 citations
        doc_id = str(chunk.get("doc_id") or "")
        page_param = int(chunk.get("page_number") or 1)
        if page_param < 1:
            page_param = 1
        topic = anchor_name or normalized_query
        url = f"{st.PDF_BASE_URL}/api/page-view?doc_id={quote(doc_id, safe='')}&page={page_param}&highlight={quote(topic[:120], safe='')}#page={page_param}"
        pretty_title = prettify_doc_title(doc_id) or (
            chunk.get("doc_title") or chunk.get("title") or doc_id.rsplit("/", 1)[-1] or "Source"
        )
        citation_payloads.append(
            {
                "evidence_id": f"S{idx}",
                "topic": topic,
                "doc_id": doc_id,
                "title": pretty_title,
                "doc_title": pretty_title,
                "page_number": page_param,
                "section_title": chunk.get("section_title") or "",
                "url": url,
                "text_passage": chunk.get("text_passage") or "",
            }
        )

    # ── Stage 5: Local Ollama GPU SLM only (qwen3.5:0.8b) ────────────────
    generation_source = "ollama"
    generation_reason = f"model={_OLLAMA_MODEL}"
    generation_provider = "ollama"
    try:
        concept = st.CONCEPTS_DATA.get(anchor_id, {}) if anchor_id else {}
        curriculum_paths = find_curriculum_chains(anchor_id, max_hops=3, max_paths=3)
        synthesized_text = _stage5_ollama_synthesis(context_payload)
        synthesized_text = enforce_four_tier(
            synthesized_text,
            anchor_name=anchor_name,
            prerequisites=prereqs,
            unlocks=unlocks,
            citations=citation_payloads,
            concept=concept,
            curriculum_paths=curriculum_paths,
        )
    except Exception as exc:
        logger.error("Ollama GPU synthesis failed: %s", exc)
        generation_source = "grounded_fallback"
        generation_reason = f"ollama_failed:{exc}"
        generation_provider = "none"
        concept = st.CONCEPTS_DATA.get(anchor_id, {}) if anchor_id else {}
        synthesized_text = enforce_four_tier(
            _build_grounded_card(anchor_id, anchor_name, graph_result, normalized_query),
            anchor_name=anchor_name,
            prerequisites=prereqs,
            unlocks=unlocks,
            citations=citation_payloads,
            concept=concept,
            curriculum_paths=curriculum_paths,
        )

    return {
        "text": synthesized_text,
        "anchor_concept": {"id": anchor_id, "name": anchor_name, "label": anchor_name},
        "prerequisites": prereqs,
        "unlocks": unlocks,
        "citations": citation_payloads,
        "routing": {
            "route": "graph_strong",
            "score": vector_hit.get("cosine_sim", 0),
            "reason": "5_stage_pipeline",
        },
        "logs": logs,
        "generation": {
            "provider": generation_provider,
            "source": generation_source,
            "reason": generation_reason,
            "model": _OLLAMA_MODEL if generation_provider == "ollama" else None,
            "device": (ollama_runtime_info().get("device") or "gpu")
            if generation_provider == "ollama"
            else None,
        },
    }


def prepare_archipelago_context(
    user_query: str,
    history: list[dict[str, Any]] | None = None,
    session_id: str = "default_session",
) -> dict[str, Any]:
    """Stages 1–4 only (no Ollama). Used for early-stream meta + true token stream.

    Returns either a terminal result (kill_switch / guardrail) with ``terminal=True``
    and ``text``, or a live context dict with ``terminal=False`` and fields needed
    for Stage 5 streaming.
    """
    del history, session_id  # reserved for Cat6 multi-turn
    logs: list[dict[str, str]] = []

    t0 = _t()
    st1 = _stage1_guardrails(user_query)
    _tlog(logs, "Guardrails", t0)
    if st1.get("reject"):
        return {
            "terminal": True,
            "text": st1["payload"],
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "routing": {"route": "input_error", "reason": "query_too_long"},
            "logs": st1.get("logs", []),
            "generation": {"provider": "none", "source": "guardrail"},
        }

    user_query = user_query.strip()
    normalized_query: str = st1["normalized_query"]

    t0 = _t()
    vector_hit = _stage2_vector_search(normalized_query)
    _tlog(logs, "VectorSearch", t0)
    if vector_hit is None:
        logs.append({"step": "VectorSearch", "status": "Kill-Switch", "details": "Below threshold"})
        return {
            "terminal": True,
            "text": (
                "I'm sorry, that topic isn't covered in the current library catalog. "
                "Please ask a question related to AI/ML, DBMS, OS, DSA, or Math for ML."
            ),
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "routing": {"route": "kill_switch", "reason": "cosine_below_threshold"},
            "logs": logs,
            "generation": {"provider": "none", "source": "kill_switch"},
        }

    anchor_id = vector_hit["anchor_id"]
    anchor_name = vector_hit["concept_name"]
    _tlog(logs, "AnchorSelect", _t(), anchor=anchor_id)

    t0 = _t()
    graph_result = _stage3_graph_traversal(anchor_id)
    _tlog(logs, "GraphTraversal", t0)
    prereqs = graph_result.get("prerequisites") or []
    unlocks = graph_result.get("unlocks") or []
    chunks = graph_result.get("chunks") or []
    _tlog(logs, "GraphSelect", _t(), prereqs=len(prereqs), unlocks=len(unlocks), chunks=len(chunks))

    # Stage 4: Payload Assembly
    context_payload = _stage4_build_payload(graph_result, normalized_query)

    from urllib.parse import quote

    citation_payloads: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks[:15], start=1):
        doc_id = str(chunk.get("doc_id") or "")
        page_param = int(chunk.get("page_number") or 1) or 1
        topic = anchor_name or normalized_query
        url = (
            f"{st.PDF_BASE_URL}/api/page-view?doc_id={quote(doc_id, safe='')}"
            f"&page={page_param}&highlight={quote(topic[:120], safe='')}#page={page_param}"
        )
        pretty_title = prettify_doc_title(doc_id) or (
            chunk.get("doc_title") or chunk.get("title") or doc_id.rsplit("/", 1)[-1] or "Source"
        )
        citation_payloads.append(
            {
                "evidence_id": f"S{idx}",
                "topic": topic,
                "doc_id": doc_id,
                "title": pretty_title,
                "doc_title": pretty_title,
                "page_number": page_param,
                "section_title": chunk.get("section_title") or "",
                "url": url,
                "text_passage": chunk.get("text_passage") or "",
            }
        )
    return {
        "terminal": False,
        "user_query": user_query,
        "normalized_query": normalized_query,
        "anchor_id": anchor_id,
        "anchor_name": anchor_name,
        "anchor_concept": {"id": anchor_id, "name": anchor_name, "label": anchor_name},
        "prerequisites": prereqs,
        "unlocks": unlocks,
        "chunks": chunks,
        "citations": citation_payloads,
        "context_payload": context_payload,
        "vector_hit": vector_hit,
        "graph_result": graph_result,
        "logs": logs,
        "routing": {
            "route": "graph_strong",
            "score": vector_hit.get("cosine_sim", 0),
            "reason": "5_stage_pipeline",
        },
        "generation": {
            "provider": "ollama",
            "source": "ollama_stream",
            "reason": f"model={_OLLAMA_MODEL}",
            "model": _OLLAMA_MODEL,
            "device": (ollama_runtime_info().get("device") or "gpu"),
            "queued": ollama_busy(),
        },
        "curriculum_paths": find_curriculum_chains(anchor_id, max_hops=3, max_paths=3),
    }


def stream_archipelago_answer(prepared: dict[str, Any]) -> Generator[str, None, None]:
    """Buffer Ollama tokens, clean/validate, then stream the final cleaned answer.

    This avoids shipping glued/raw tokens and duplicate footers.
    """
    if prepared.get("terminal"):
        yield prepared.get("text") or ""
        return

    context_payload = prepared["context_payload"]
    anchor_id = prepared.get("anchor_id") or ""
    anchor_name = prepared.get("anchor_name") or ""
    normalized_query = prepared.get("normalized_query") or ""
    prereqs = prepared.get("prerequisites") or []
    unlocks = prepared.get("unlocks") or []
    citations = prepared.get("citations") or prepared.get("citation_payloads") or []
    logs = prepared.setdefault("logs", [])
    concept = st.CONCEPTS_DATA.get(anchor_id, {}) if anchor_id else {}

    raw_parts: list[str] = []
    runtime = ollama_runtime_info()
    device_now = str(runtime.get("device") or "unknown")
    was_busy = ollama_busy()
    # On CPU (driver glitch after resume) never advertise a long GPU queue —
    # jump straight to synthesis / grounded fallback with tiny budgets.
    announce_queue = was_busy and device_now == "gpu"
    try:
        t_lock = _t()
        if announce_queue:
            yield "⏳ Local GPU SLM is finishing the previous answer — you are next…\n\n"
        t_stream = _t()
        first_token = True
        for token in _stage5_ollama_stream(context_payload):
            # Skip the internal queue notice if we already told the user above,
            # or when we intentionally skip queue UX on CPU.
            if first_token and isinstance(token, str) and token.lstrip().startswith("[Queue]"):
                # Treat as empty so the grounded fallback path runs.
                raw_parts.append(token)
                break
            if first_token:
                first_token = False
                t_first = _time.perf_counter() - t_stream
                if (_time.perf_counter() - t_lock) > 0.1:
                    logs.append(
                        {
                            "step": "OllamaLockWait",
                            "status": "OK",
                            "details": f"dur={_time.perf_counter() - t_lock:.3f}s",
                        }
                    )
                logs.append(
                    {
                        "step": "OllamaFirstToken",
                        "status": "OK",
                        "details": f"dur={t_first:.3f}s",
                    }
                )
            raw_parts.append(token)
        total_stream = _time.perf_counter() - t_stream
        logs.append(
            {
                "step": "OllamaStream",
                "status": "OK",
                "details": f"dur={total_stream:.3f}s tokens={len(raw_parts)} device={device_now}",
            }
        )

        raw = "".join(raw_parts).strip()
        # Queue-only notice with no model text → fall through to grounded card.
        if raw.startswith("[Queue]") or (not raw and was_busy):
            raise TimeoutError(raw.strip() or "ollama_busy_served_grounded")
        # A fully-glued stream (spaces dropped) is unrecoverable garbage.
        # Do NOT ship it — fall back to the deterministic grounded card.
        if raw and is_glued(raw):
            logger.warning(
                "Ollama stream came back glued (spaces dropped); falling back to grounded card"
            )
            cleaned = enforce_four_tier(
                _build_grounded_card(
                    anchor_id,
                    anchor_name,
                    prepared.get("graph_result") or {},
                    normalized_query,
                ),
                anchor_name=anchor_name,
                prerequisites=prereqs,
                unlocks=unlocks,
                citations=citations,
                concept=concept,
            )
        else:
            cleaned = enforce_four_tier(
                raw,
                anchor_name=anchor_name,
                prerequisites=prereqs,
                unlocks=unlocks,
                citations=citations,
                concept=concept,
            )

        # Append catalog inventory table for graph_strong route when book keywords mentioned
        route = prepared.get("routing", {}).get("route")
        if route == "graph_strong":
            user_query = prepared.get("user_query") or normalized_query
            user_query_lower = user_query.lower()
            book_keywords = [
                'dbms', 'database', 'silberschatz', 'ramakrishnan', 'korth',
                'ostep', 'operating system', 'paging', 'segmentation',
                'dsa', 'data structure', 'algorithm', 'clrs', 'weiss',
                'buffer pool', 'virtual memory', 'file system',
                'silberschatz', 'korth', 'sudarshan', 'galvin', 'gane',
                # Additional keywords from shelf_keys in catalog_ods.format_catalog_reply
                'shelf', 'call number', 'call no', 'rack',
                'physical book', 'where is', 'available copies', 'availability', 'borrow',
                'database system concepts', 'operating system concepts',
                'page table', 'frame', 'tlb',
            ]
            if any(k in user_query_lower for k in book_keywords):
                cat_reply = format_catalog_reply(user_query)
                if cat_reply:
                    cleaned = cleaned.rstrip() + "\n\n" + cat_reply

        # Stream cleaned answer in small chunks for smooth UX
        for i in range(0, len(cleaned), 128):
            yield cleaned[i : i + 128]

        runtime = ollama_runtime_info()
        device = runtime.get("device") or "gpu"
        logs.append(
            {
                "step": "Synthesis",
                "status": "OK",
                "details": f"ollama_stream chars={len(raw)} cleaned={len(cleaned)} device={device}",
            }
        )
        prepared["text"] = cleaned
        prepared["generation"] = {
            "provider": "ollama",
            "source": "ollama_stream",
            "reason": f"model={_OLLAMA_MODEL} keep_alive={_OLLAMA_KEEP_ALIVE}",
            "model": _OLLAMA_MODEL,
            "device": device,
        }
    except Exception as exc:
        logger.error("Ollama stream failed: %s", exc)
        card = enforce_four_tier(
            _build_grounded_card(
                prepared.get("anchor_id") or "",
                anchor_name,
                prepared.get("graph_result") or {},
                prepared.get("normalized_query") or "",
            ),
            anchor_name=anchor_name,
            prerequisites=prereqs,
            unlocks=unlocks,
            citations=citations,
            concept=concept,
        )

        # Append catalog inventory table for graph_strong route when book keywords mentioned
        route = prepared.get("routing", {}).get("route")
        if route == "graph_strong":
            user_query = prepared.get("user_query") or normalized_query
            user_query_lower = user_query.lower()
            book_keywords = [
                'dbms', 'database', 'silberschatz', 'ramakrishnan', 'korth',
                'ostep', 'operating system', 'paging', 'segmentation',
                'dsa', 'data structure', 'algorithm', 'clrs', 'weiss',
                'buffer pool', 'virtual memory', 'file system',
                'silberschatz', 'korth', 'sudarshan', 'galvin', 'gane',
                # Additional keywords from shelf_keys in catalog_ods.format_catalog_reply
                'shelf', 'call number', 'call no', 'rack',
                'physical book', 'where is', 'available copies', 'availability', 'borrow',
                'database system concepts', 'operating system concepts',
                'page table', 'frame', 'tlb',
            ]
            if any(k in user_query_lower for k in book_keywords):
                cat_reply = format_catalog_reply(user_query)
                if cat_reply:
                    card = card.rstrip() + "\n\n" + cat_reply

        prepared["generation"] = {
            "provider": "grounded_fallback",
            "source": "ollama_timeout_or_error",
            "reason": str(exc)[:240],
            "model": _OLLAMA_MODEL,
            "device": (ollama_runtime_info().get("device") or "unknown"),
        }
        logs.append(
            {
                "step": "Synthesis",
                "status": "FALLBACK",
                "details": f"ollama_error={str(exc)[:160]}",
            }
        )
        # Stream fallback in chunks
        for i in range(0, len(card), 128):
            yield card[i : i + 128]
    except GeneratorExit:
        # Client aborted mid-stream (browser refresh / stop). Free the lock so
        # the next chat is not stuck on "GPU SLM in queue".
        _release_ollama()
        raise


def _build_grounded_card(
    anchor_id: str, anchor_name: str, graph_result: dict[str, Any], query: str
) -> str:
    """Build a grounded answer card from local graph when Ollama fails."""
    concept = st.CONCEPTS_DATA.get(anchor_id, {}) if anchor_id else {}
    summary = concept.get("summary") or concept.get("summary_short") or ""

    parts = [f"## {anchor_name or anchor_id}"]
    if summary:
        parts.append(summary)

    prereqs = graph_result.get("prerequisites") or []
    unlocks = graph_result.get("unlocks") or []
    if prereqs:
        parts.append("\n**Requires (Prerequisites):**")
        for p in prereqs[:3]:
            parts.append(f"- {p.get('name') or p.get('id', '')}: {p.get('summary', '')[:200]}")
    if unlocks:
        parts.append("\n**Unlocks (Downstream):**")
        for u in unlocks[:3]:
            parts.append(f"- {u.get('name') or u.get('id', '')}: {u.get('summary', '')[:200]}")

    chunks = graph_result.get("chunks") or []
    if chunks:
        parts.append("\n**Sources:**")
        for i, chunk in enumerate(chunks[:5], 1):
            doc = chunk.get("title") or chunk.get("doc_id", "")
            page = chunk.get("page_number", 1)
            parts.append(f"S{i}: {doc}, page {page}")

    return "\n".join(parts)
