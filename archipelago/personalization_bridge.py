"""Use the same private diagnostic protocol in both local inference entrypoints.

The standalone distribution keeps its dependency-light implementation under
host_inference. The local workstation reuses it rather than maintaining another
grading/session engine.
"""
from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path
import sys

from flask import current_app

_HOST = Path(__file__).resolve().parents[1] / "host_inference"
if str(_HOST) not in sys.path:
    sys.path.insert(0, str(_HOST))



class LocalLearningGraph:
    """Project the local concept registry's actual prerequisites for the shared engine."""

    def __init__(self, concepts: dict) -> None:
        self.nodes = {
            cid: {**node, "id": cid, "label": node.get("label") or node.get("name") or cid}
            for cid, node in concepts.items() if isinstance(node, dict)
        }
        self.out: dict[str, list] = defaultdict(list)
        self.inn: dict[str, list] = defaultdict(list)
        edges = set()
        for cid, node in self.nodes.items():
            for field, relation in (
                ("prerequisites", "REQUIRES"), ("unlocks", "UNLOCKS"),
                ("contrasts_with", "contrasts_with"), ("variant_of", "variant_of"),
                ("improves_on", "improves_on"),
            ):
                for value in node.get(field) or []:
                    other = value.get("id") if isinstance(value, dict) else value
                    if other in self.nodes:
                        edges.add((cid, relation, other))
        for source, relation, target in sorted(edges):
            self.out[source].append((relation, target))
            self.inn[target].append((relation, source))

    def label(self, cid: str) -> str:
        return self.nodes[cid]["label"]

    def rank(self, query: str, top_k: int = 5) -> list:
        """Only used for diagnostic distractors, never as an inference ranker."""
        words = set(query.lower().split())
        return sorted(
            [(len(words & set(self.label(cid).lower().split())), cid) for cid in self.nodes],
            reverse=True,
        )[:top_k]

    def cite_record(self, cid: str, query: str = "") -> dict:
        from urllib.parse import quote

        sources = self.nodes[cid].get("sources") or []
        source = next((s for s in sources if isinstance(s, dict) and s.get("doc_id")), {})
        doc = source.get("doc_id", "")
        page = source.get("page_number")
        return {
            "doc_id": doc, "page_number": page,
            "url": f"/read?doc={quote(doc, safe='')}&page={page}" if doc and page else "",
        }

    def citation(self, cid: str) -> str:
        source = self.cite_record(cid)
        return f"{source['doc_id']}, page {source['page_number']}" if source["url"] else "No indexed source page."


def diagnostic_response(concepts: dict, *, start: bool):
    """Delegate within the caller's Flask context and browser-owned session."""
    from hostapp.quiz_store import QuizStore
    from hostapp.routes.diagnostics import start_response, step_response

    store = current_app.extensions.get("private_learning_store")
    if store is None:
        path = Path(os.getenv(
            "ARCHIPELAGO_QUIZ_DB", str(_HOST / "cache" / "local_quiz_sessions.sqlite3"),
        ))
        store = QuizStore(path)
        current_app.extensions["private_learning_store"] = store
    graph = LocalLearningGraph(concepts)
    return start_response(graph, store) if start else step_response(graph, store)


def memory_response():
    """Expose owner deletion controls through the local protocol as well."""
    from hostapp.learning_memory import LearningMemory
    from hostapp.routes.learning_settings import settings_response

    path = Path(os.getenv("ARCHIPELAGO_QUIZ_DB", str(_HOST / "cache" / "local_quiz_sessions.sqlite3")))
    return settings_response(LearningMemory(path.with_name("learning_memory.sqlite3")))
