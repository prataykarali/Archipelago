"""Runtime engine state for the production REST API (router, retriever, assembler)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from flask import Flask

from archipelago.core.prompt_assembly import PromptPayloadAssembler
from archipelago.core.retrieval import TwoPassHybridRetriever
from archipelago.core.router import QueryRouter
from archipelago.core.synthesis_service import SynthesisService

logger = logging.getLogger("archipelago.api")

# Local development loads the ignored repository .env file. Deployed hosts
# provide the same values through their managed environment instead.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
PDF_DIR = BASE_DIR / "pdfs"
DATA_FILE = BASE_DIR / "okf_graph.json"
DB_PATH = str(BASE_DIR / "okf_graph.db")

DEFAULT_SYNTHESIS_MODEL = "qwen/qwen3.8-max:free"
DEFAULT_INGESTION_MODEL = "lib-qwen:latest"
DEFAULT_RUNTIME = "production_docker"
DEFAULT_ANCHOR = "low_rank_adaptation"
DEFAULT_DIFFICULTY = "intermediate"
DEFAULT_SHELF_LOCATION = "Main Library Stack A"
DEFAULT_AVAILABLE_COPIES = 1
DOCUMENT_LIST_LIMIT = 50
CATALOG_SEARCH_LIMIT = 5
TOPIC_SUGGEST_LIMIT = 5
EVIDENCE_CHUNK_LIMIT = 3
MAX_UPSTREAM_HOPS = 2
MAX_DOWNSTREAM_HOPS = 2
MAX_TOPIC_SUGGEST_FALLBACK = 3
DEFAULT_MCQ_TOTAL = 3
DEFAULT_MCQ_CORRECT = 2
DEFAULT_MCQ_SCORE = 0.5

_PUBLIC_AUTH_PATHS = frozenset({"/api/readiness", "/api/auth/config"})
_LIBRARIAN_OR_ADMIN_PATHS = frozenset({
    "/api/upload",
    "/api/users",
    # Procurement signals: what students asked for that the library does not
    # hold, and what could be bought to fix it. Never student-facing.
    "/api/librarian/demand-digest",
    "/api/librarian/acquisition-plan",
})
_LIBRARIAN_OR_ADMIN_ROLES = frozenset({"librarian", "administrator"})
_UPLOAD_ALLOWED_SUFFIXES = (".pdf", ".md", ".markdown", ".txt")

app = Flask(__name__)

# Global instances initialized lazily or on startup
_router: Optional[QueryRouter] = None
_retriever: Optional[TwoPassHybridRetriever] = None
_assembler: Optional[PromptPayloadAssembler] = None
_synthesis: Optional[SynthesisService] = None
_concepts_data: Dict[str, Any] = {}
_kuzu_conn: Optional[Any] = None


def get_kuzu_connection() -> Optional[Any]:
    """Obtain or reuse KùzuDB connection safely."""
    global _kuzu_conn
    if _kuzu_conn is not None:
        return _kuzu_conn
    try:
        import kuzu

        db = kuzu.Database(DB_PATH, read_only=True)
        _kuzu_conn = kuzu.Connection(db)
        logger.info("Connected to KùzuDB at %s (read_only=True)", DB_PATH)
        return _kuzu_conn
    except Exception as exc:
        logger.info(
            "Kùzu DB direct handle unavailable (%s); relying on in-memory concepts index.", exc
        )
        _kuzu_conn = None
        return None


def ensure_pdf_dir() -> None:
    """Create the PDF staging directory if it is missing."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)


def load_concepts_data() -> int:
    """Load the concept index from the graph export; returns the concept count.

    Merges both halves of the export.  ``visualization.nodes`` holds the
    automatically extracted AI/ML nodes; the sibling ``concepts`` block holds the
    hand-curated *textbook* concepts — third normal form, LoRA, BERT, attention,
    RAG.  Loading only the first meant "Explain third normal form" had no anchor,
    scored below the similarity floor, and was deflected as out-of-scope: the
    entire database-and-PEFT curriculum the response contract is written around
    was invisible to this stack.  The hosted engine has always merged them.
    """
    if not DATA_FILE.is_file():
        return 0
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        logger.warning("Failed loading %s: %s", DATA_FILE.name, exc)
        return 0

    nodes = raw.get("visualization", {}).get("nodes", []) or raw.get("nodes", [])
    for node in nodes:
        cid = node.get("id", "")
        if cid:
            _concepts_data[cid] = node

    for cid, concept in (raw.get("concepts") or {}).items():
        if not cid or not isinstance(concept, dict) or cid in _concepts_data:
            continue
        merged = dict(concept)
        merged.setdefault("id", cid)
        merged.setdefault("label", merged.get("name") or cid)
        merged.setdefault("name", merged.get("label") or cid)
        _concepts_data[cid] = merged

    return len(_concepts_data)


def init_engine() -> None:
    """Initialize all runtime components."""
    global _router, _retriever, _assembler, _synthesis

    ensure_pdf_dir()

    # 1. Load concepts data from JSON
    count = load_concepts_data()
    if count:
        logger.info("Loaded %d concepts from %s", count, DATA_FILE.name)

    # 2. Initialize Core Modules
    conn = get_kuzu_connection()
    _router = QueryRouter()
    _retriever = TwoPassHybridRetriever(kuzu_conn=conn, concepts_data=_concepts_data)
    _assembler = PromptPayloadAssembler()
    _synthesis = SynthesisService()


def ensure_engine() -> None:
    """Initialize the engine once if any component is missing."""
    if not _router or not _retriever or not _assembler or not _synthesis:
        init_engine()


def concept_node(concept_id: str) -> dict[str, Any]:
    """Return one concept node, defaulting to an empty dict."""
    return _concepts_data.get(concept_id, {})


def concept_name(concept_id: str, node: dict[str, Any] | None = None) -> str:
    """Human-readable name for a concept id."""
    info = node if node is not None else concept_node(concept_id)
    return info.get("name") or info.get("label") or concept_id
