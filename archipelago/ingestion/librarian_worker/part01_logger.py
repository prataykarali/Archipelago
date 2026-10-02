"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional
from . import _deps as _rt  # noqa: F401


logger = logging.getLogger("archipelago.ingestion.librarian_worker")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "okf_graph.json").exists() or (parent / "pyproject.toml").exists():
            return parent
    return here.parents[2]


BASE_DIR = _repo_root()


STAGING_DB_PATH = BASE_DIR / "okf_graph_staging.db"


PROD_DB_PATH = BASE_DIR / "okf_graph.db"


DATA_FILE = BASE_DIR / "okf_graph.json"


INFERENCE_RELOAD_URL = os.environ.get(
    "ARCHIPELAGO_INFERENCE_RELOAD_URL",
    "http://127.0.0.1:5151/api/internal/reload-graph",
)


JOBS_DIR = BASE_DIR / "jobs" / "librarian"


UPLOADS_DIR = BASE_DIR / "data" / "uploads"


@dataclass
class LibrarianJob:
    job_id: str
    title: str
    author: str
    isbn: str
    domain: str
    filename: str
    file_path: str
    status: str = "queued"
    stage: str = "QUEUED"
    chunks_processed: int = 0
    concepts_extracted: int = 0
    dag_status: str = "pending"
    error: Optional[str] = None
    hf_remote_path: Optional[str] = None
    staged_entities: dict[str, Any] = field(default_factory=lambda: {
        "documents": [],
        "chunks": [],
        "concepts": [],
        "edges": [],
    })
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    auto_publish: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
