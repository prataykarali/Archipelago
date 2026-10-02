"""Contract type 5: live OKF projection for an uploaded paper.

``INGEST_RE`` existed in the pattern module but was never referenced by the
router, so every "analyse this uploaded PDF" prompt fell through to the
out-of-domain kill switch or a book lookup.  This module is the missing half:
it reads the librarian ingestion job store and projects what that upload actually
contributed to the OKF graph.

The projection is *read-only*.  Ingestion itself is asynchronous and lives in
:mod:`ingestion_worker`; this never triggers extraction, never mutates the graph,
and never claims a node the pipeline did not emit.  When no upload has completed,
it says so and points at the upload route — an honest "nothing ingested yet" is
the only correct answer, because inventing a node list would be the exact
fabrication the rest of the engine is built to avoid.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .constants import HERE

logger = logging.getLogger(__name__)

#: Job store location, relative to the package parent (``host_inference/../jobs``).
#: Overridable so a hosted deployment can mount the job store on a volume.
JOBS_DIR_ENV = "ARCHIPELAGO_JOBS_DIR"
JOBS_RELPATH = Path("jobs") / "jobs.json"

#: Job states that mean "there is something to report".
SETTLED_STATUSES = frozenset({"COMPLETE", "FAILED", "CANCELLED"})

#: Cap on projected nodes, so one large upload cannot flood the chat payload.
MAX_PROJECTED_NODES = 12

#: Cap on the OKF edges drawn between projected nodes.
MAX_PROJECTED_EDGES = 24

NO_UPLOAD_MESSAGE = (
    "**No completed upload is on record.** I can analyse a paper only after the "
    "librarian ingestion pipeline has extracted its OKF nodes, and no job has "
    "reached that stage yet.\n\n"
    "Upload the PDF on the librarian ingest page, then ask me again — I will "
    "project the extracted concept nodes and their prerequisite edges here, with "
    "page-level provenance."
)


def jobs_index_path(base_dir: Path | str | None = None) -> Path:
    """Absolute path of the ingestion job index."""
    import os

    if base_dir is not None:
        return Path(base_dir) / JOBS_RELPATH
    override = os.environ.get(JOBS_DIR_ENV, "").strip()
    if override:
        return Path(override) / JOBS_RELPATH
    return HERE.parent / JOBS_RELPATH


def load_jobs(base_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Every ingestion job record, newest first. Missing store means none."""
    path = jobs_index_path(base_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable ingestion job index %s: %s", path, exc)
        return []
    if not isinstance(raw, dict):
        return []
    records = [row for row in raw.values() if isinstance(row, dict)]
    records.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return records


def latest_job(base_dir: Path | str | None = None) -> dict[str, Any] | None:
    """Most recently updated job, or ``None`` when the store is empty."""
    records = load_jobs(base_dir)
    return records[0] if records else None


def _projected_nodes(job: dict[str, Any], graph, limit: int) -> list[str]:
    """Concept ids this upload contributed, in the graph, capped at ``limit``.

    Only ids present in the loaded graph are returned: the job record can name a
    node the exported cache has since dropped, and rendering a dangling node
    would draw an edge to nothing.
    """
    result = job.get("result")
    result = result if isinstance(result, dict) else {}
    raw_ids = result.get("new_node_ids")
    if not isinstance(raw_ids, list):
        raw_ids = []
    ordered: list[str] = []
    for cid in raw_ids:
        text = str(cid or "").strip()
        if text and text in graph.nodes and text not in ordered:
            ordered.append(text)
    return ordered[:limit]


def _projected_edges(node_ids: list[str], graph) -> list[dict[str, str]]:
    """Prerequisite edges among the projected nodes (and to the wider graph).

    Direction follows the pedagogy: prerequisite ➔ dependent, so the UI's
    ``REQUIRES ➔ UNLOCKS`` arrow reads left to right in study order.
    """
    projected = set(node_ids)
    edges: list[dict[str, str]] = []
    for cid in node_ids:
        for prereq in graph.prereqs(cid, 1):
            if prereq in projected or prereq not in graph.nodes:
                continue
            if prereq in graph.unlocks(cid, 1):
                continue
            edge = {"source": prereq, "target": cid, "relation": "REQUIRES"}
            if edge not in edges:
                edges.append(edge)
            if len(edges) >= MAX_PROJECTED_EDGES:
                return edges
    return edges


def ingestion_reply(query: str, graph) -> tuple[str, dict[str, Any]]:
    """Grounded ingestion reply plus the OKF projection payload.

    Returns the reply text and a payload fragment carrying ``okf_projection``:
    the extracted concept nodes with their prerequisite edges, and the provenance
    of the upload they came from.
    """
    job = latest_job()
    if job is None or str(job.get("status")) not in SETTLED_STATUSES:
        # Same key set as every other branch, so a consumer never has to probe
        # for ``nodes`` before reading it.
        return NO_UPLOAD_MESSAGE, {
            "ingestion": {
                "state": "no_upload", "source": "", "job_id": "",
                "graph_version": None, "doc_id": "", "pages": [],
                "nodes": [], "edges": [],
            }
        }

    source = str(job.get("source_filename") or "the uploaded document")
    status = str(job.get("status"))
    result = job.get("result")
    result = result if isinstance(result, dict) else {}

    if status != "COMPLETE":
        detail = str(job.get("error") or "The job did not complete.")
        text = (
            f"**{source}** was ingested with status `{status}`.\n\n"
            f"{detail}\n\n"
            "No OKF nodes were committed to the graph, so I cannot ground a "
            "synthesis on this paper yet. Ask the librarian to re-run the "
            "ingestion, or upload a text-layer PDF if the extraction was empty."
        )
        return text, {
            "ingestion": {
                "state": status.lower(),
                "source": source,
                "job_id": str(job.get("job_id") or ""),
                "graph_version": job.get("graph_version"),
                "doc_id": source,
                "pages": [],
                "error": detail,
                "nodes": [],
                "edges": [],
            }
        }

    node_ids = _projected_nodes(job, graph, MAX_PROJECTED_NODES)
    edges = _projected_edges(node_ids, graph)
    pages = result.get("source_pages")
    pages = sorted(int(p) for p in pages) if isinstance(pages, list) else []

    if not node_ids:
        text = (
            f"**{source}** completed ingestion, but the extraction committed no "
            "new concept nodes to the OKF graph. The paper is stored and "
            "registered in the inventory, but there is nothing for me to ground a "
            "synthesis on. Check the extraction log for this job before asking "
            "me to analyse it."
        )
        return text, {
            "ingestion": {
                "state": "no_nodes",
                "source": source,
                "job_id": str(job.get("job_id") or ""),
                "graph_version": job.get("graph_version"),
                "doc_id": source,
                "pages": [],
                "nodes": [],
                "edges": [],
            }
        }

    lines = [
        f"**{source}** completed ingestion and contributed "
        f"{len(node_ids)} OKF concept node(s) to the graph.",
        "",
        "**OKF projection.** "
        + " ➔ ".join(graph.label(cid) for cid in node_ids[:6])
        + (" …" if len(node_ids) > 6 else ""),
    ]
    if pages:
        shown = ", ".join(str(p) for p in pages[:8])
        lines.extend(["", f"**Extracted page provenance.** pages {shown}"])
    doc_id = str((result.get("merge") or {}).get("uploading_doc_id") or source)
    lines.extend(["", f"**Source document.** {doc_id}"])
    return "\n".join(lines), {
        "ingestion": {
            "state": "complete",
            "source": source,
            "job_id": str(job.get("job_id") or ""),
            "graph_version": job.get("graph_version"),
            "doc_id": doc_id,
            "pages": pages,
            "nodes": node_ids,
            "edges": edges,
        }
    }


__all__ = [
    "JOBS_DIR_ENV",
    "JOBS_RELPATH",
    "MAX_PROJECTED_EDGES",
    "MAX_PROJECTED_NODES",
    "NO_UPLOAD_MESSAGE",
    "ingestion_reply",
    "jobs_index_path",
    "latest_job",
    "load_jobs",
]
