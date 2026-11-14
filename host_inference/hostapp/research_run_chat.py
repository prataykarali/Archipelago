"""Answer research-collection questions in Chat from a stored S5 snapshot.

Deterministic and evidence-bound: every answer is rendered from the owner's
persisted run (papers, author observations, graph). Missing facts are stated
as unavailable, never guessed. Academic chat is untouched unless the message
is clearly about a research collection.
"""

from __future__ import annotations

import re
from typing import Any

FIND = re.compile(
    r"\b(?:find|search|collect|get|look up)\b(?:\s+(?P<count>\d{1,3}))?"
    r"(?:\s+(?P<pre_topic>[a-z0-9][a-z0-9\s\-]{2,80}?))?\s+(?:research\s+)?(?:papers?|publications?|studies)\b"
    r"(?:\s+(?:on|about|for|regarding)\s+(?P<topic>.+))?",
    re.I,
)
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": -1}
COLLECTION = re.compile(
    r"\b(collected|these (works|papers)|this (research )?collection|that paper|the (first|second|third|"
    r"fourth|fifth|last) paper|that author|the author|authors?|h-index|i10|journals?|conferences?|"
    r"venues?|citation relationships?|cit(?:es|ations?)|methods?|datasets?|export|excel|workbook|"
    r"new papers|monitor|monitoring)\b",
    re.I,
)
RESEARCH_WORDS = re.compile(
    r"\b(papers?|authors?|h-index|i10|journals?|conferences?|venues?|abstracts?|"
    r"collection|collected|monitoring|research methods?|citation relationships?|datasets?)\b",
    re.I,
)
EXPORT = re.compile(r"\b(export|excel|xlsx|workbook|spreadsheet|download)\b", re.I)
NEW_PAPERS = re.compile(r"\b(new|newly|since)\b.*\b(papers?|monitor|monitoring|run|update|check)", re.I)


def is_research_request(query: str, has_run: bool) -> bool:
    """Research chat only handles paper discovery or follow-ups on a stored run."""
    if FIND.search(query):
        return True
    return has_run and bool(COLLECTION.search(query)) and bool(RESEARCH_WORDS.search(query))


def _link(paper: dict[str, Any]) -> str:
    doi = paper.get("doi")
    return f"https://doi.org/{doi}" if doi else (paper.get("url") or "no link available")


def _ref(index: int, paper: dict[str, Any]) -> str:
    return f"[{index}]"


def _paper_by_reference(query: str, papers: list[dict[str, Any]], history_text: str) -> int | None:
    for word, number in ORDINALS.items():
        if re.search(rf"\b{word}\s+(paper|work|one)\b", query, re.I):
            return (
                len(papers) - 1 if number == -1 else number - 1 if number <= len(papers) else None
            )
    match = re.search(r"\b(?:paper|work)\s+(?:#|number\s+)?(\d{1,3})\b", query, re.I)
    if match and 1 <= int(match.group(1)) <= len(papers):
        return int(match.group(1)) - 1
    found = re.findall(r"\[(\d{1,3})\]", history_text)
    if found and int(found[-1]) <= len(papers):
        return int(found[-1]) - 1
    return None


def _author_in_history(run: dict[str, Any], history_text: str) -> tuple[dict[str, Any], int] | None:
    """Last author name mentioned in conversation, with the paper index it came from."""
    best: tuple[int, dict[str, Any], int] | None = None
    for pidx, paper in enumerate(run["papers"]):
        for author in paper["authors"]:
            name = author["name"]
            at = history_text.rfind(name)
            if at >= 0 and (best is None or at > best[0]):
                best = (at, {"author": author, "paper": paper}, pidx)
    return (best[1], best[2]) if best else None


def _observation(run: dict[str, Any], paper: dict[str, Any], author_index: int) -> dict | None:
    ids = (paper.get("source_metadata") or {}).get("author_openalex_ids") or []
    short = (
        ids[author_index].rsplit("/", 1)[-1]
        if author_index < len(ids) and ids[author_index]
        else None
    )
    return next((o for o in run.get("author_observations", []) if o["id"] == short), None)


def _list(run: dict[str, Any]) -> str:
    lines = [
        f"This collection for “{run['options']['topic']}” has {len(run['papers'])} papers "
        f"(requested up to {run['options']['top_k']}; order: {run.get('ordering')}, not a quality ranking)."
    ]
    for i, p in enumerate(run["papers"], 1):
        authors = ", ".join(a["name"] for a in p["authors"][:6]) or "authors unavailable"
        if len(p["authors"]) > 6:
            authors += f" and {len(p['authors']) - 6} more"
        lines.append(
            f"[{i}] {p['title']} — {authors} — {p.get('year') or 'year unavailable'} — {_link(p)}"
        )
    return "\n".join(lines)


def _answer(
    query: str, run: dict[str, Any], history_text: str, run_id: str, new_papers: str
) -> str:
    papers = run["papers"]
    if not papers:
        return "The stored collection contains no papers that matched the topic, so there is nothing to report."
    if EXPORT.search(query):
        return (
            f"Download the single nine-sheet workbook for this collection: "
            f"/api/research/intelligence/runs/{run_id}/xlsx ({len(papers)} papers)."
        )
    if NEW_PAPERS.search(query):
        return new_papers
    if re.search(
        r"\bh-?index|i10|citation count of (that|the) author|author metrics?", query, re.I
    ):
        hit = _author_in_history(run, history_text)
        if hit is None:
            idx = _paper_by_reference(query, papers, history_text)
            paper = papers[idx or 0]
            hit = (
                ({"author": paper["authors"][0], "paper": paper}, idx or 0)
                if paper["authors"]
                else None
            )
        if hit is None:
            return "No author is identified for that paper in the stored metadata."
        info, _ = hit
        paper, author = info["paper"], info["author"]
        index = paper["authors"].index(author)
        obs = _observation(run, paper, index)
        metrics = (obs or {}).get("metrics")
        if not metrics or metrics.get("h_index") is None:
            reason = (
                "no provider-linked author ID"
                if obs is None
                else "the provider returned no h-index"
            )
            return (
                f"The h-index for {author['name']} is not available in this snapshot ({reason}). "
                "I will not estimate it, and authors are not matched by name alone."
            )
        i10 = metrics.get("i10_index")
        return (
            f"{obs['name']} — h-index {metrics['h_index']}, i10-index {'N/A' if i10 is None else i10}, "
            f"{metrics.get('publication_count')} indexed works, {metrics.get('citation_count')} citations. "
            f"Source: {obs['provider']} at {obs['retrieved_at']} (coverage may be incomplete)."
        )
    if re.search(r"\bwho (authored|wrote)|authors? of\b", query, re.I) and not re.search(
        r"\ball\b.*\bpapers\b", query, re.I
    ):
        idx = _paper_by_reference(query, papers, history_text)
        idx = 0 if idx is None else idx
        p = papers[idx]
        names = "; ".join(
            a["name"] + (f" ({', '.join(a['institutions'][:1])})" if a.get("institutions") else "")
            for a in p["authors"]
        )
        return f"[{idx + 1}] {p['title']} was authored by {names or 'authors not listed by providers'}. Source: {_link(p)}"
    if re.search(r"\b(journals?|conferences?|venues?|published)\b", query, re.I):
        lines = ["Venues in this collection (from provider metadata; no impact metrics assumed):"]
        for i, p in enumerate(papers, 1):
            d = p.get("venue_details") or {}
            extra = ", ".join(x for x in (d.get("type"), d.get("publisher")) if x)
            lines.append(
                f"[{i}] {p.get('venue') or 'venue unavailable'}{f' ({extra})' if extra else ''}"
            )
        return "\n".join(lines)
    if re.search(r"\b(citation relationships?|cite|cites|cited|citations between)\b", query, re.I):
        from archipelago.scholarly.intelligence.graph import build_graph

        edges = [e for e in build_graph(run)["edges"] if e["type"] == "CITES"]
        order = {"paper:" + p["paper_id"]: i for i, p in enumerate(papers, 1)}
        if not edges:
            counts = sum(len(p.get("references") or []) for p in papers)
            return (
                "No provider-verified citation links exist between papers in this collection. "
                f"The papers list {counts} reference IDs in total, but none point at another paper here."
            )
        return "Provider-verified citations within the collection:\n" + "\n".join(
            f"[{order[e['source']]}] cites [{order[e['target']]}] (source: {e['provider']})"
            for e in edges
        )
    if re.search(r"\b(methods?|datasets?|metrics?|techniques?)\b", query, re.I):
        lines = ["Methods, datasets and metrics found literally in abstracts:"]
        for i, p in enumerate(papers, 1):

            def names(key: str, p: dict[str, Any] = p) -> str:
                return ", ".join(
                    x["name"] if isinstance(x, dict) else str(x) for x in p.get(key) or []
                )

            found = [
                f"{label}: {names(key)}"
                for label, key in (
                    ("methods", "methods"),
                    ("datasets", "datasets"),
                    ("metrics", "evaluation_metrics"),
                )
                if names(key)
            ]
            lines.append(
                f"[{i}] {'; '.join(found) if found else 'none stated in the available abstract'}"
            )
        return "\n".join(lines)
    return _list(run)


def research_chat_reply(
    query: str, history: list[dict[str, Any]] | None, owner: str, store: Any, run_id: str | None
) -> dict[str, Any] | None:
    """Return a chat reply dict, or None to leave the message to normal chat."""
    runs = store.list_runs(owner)
    history_text = "\n".join(
        str(m.get("content", "")) for m in history or [] if isinstance(m, dict)
    )
    run = store.get_run(run_id, owner) if run_id else None
    if run is None and runs:
        hist_matches = re.findall(r"This collection for “([^”]+)” has (\d+) papers", history_text)
        if hist_matches:
            target_topic, target_count = hist_matches[-1][0].casefold(), int(hist_matches[-1][1])
            for candidate in runs:
                if candidate["topic"].casefold() == target_topic:
                    loaded = store.get_run(candidate["run_id"], owner)
                    if loaded and len(loaded.get("papers", [])) == target_count:
                        run_id, run = candidate["run_id"], loaded
                        break
        if run is None:
            run_id = runs[0]["run_id"]
            run = store.get_run(run_id, owner)
    find = FIND.search(query)
    if not is_research_request(query, run is not None):
        return None
    raw_topic = (find.group("topic") or find.group("pre_topic") or "").strip() if find else ""
    if raw_topic and raw_topic.casefold() not in {"the", "some", "these", "all", "collected", "my"}:
        topic = re.sub(r"[?.!]+$", "", raw_topic)
        req_k = int(find.group("count")) if find and find.group("count") and int(find.group("count")) in {10, 20, 50, 100} else 20
        norm = topic.casefold().rstrip("s")
        for candidate in runs:
            if norm in candidate["topic"].casefold().rstrip("s"):
                loaded = store.get_run(candidate["run_id"], owner)
                if loaded and loaded.get("options", {}).get("top_k") == req_k and loaded.get("papers"):
                    return {"text": _list(loaded), "run_id": candidate["run_id"], "run": loaded}
        from archipelago.scholarly.intelligence.search import discover

        try:
            fresh = discover({"topic": topic, "top_k": req_k})
        except ValueError:
            return {"text": "That topic is not a valid research search.", "run_id": run_id}
        if not any(s["status"] in {"live", "live_empty"} for s in fresh["sources"]):
            return {
                "text": "Scholarly providers are unavailable right now, so no papers were collected.",
                "run_id": run_id,
            }
        run_id = store.save_run(owner, fresh)
        return {"text": _list(fresh), "run_id": run_id, "run": fresh}
    if run is None:
        return {
            "text": "There is no saved research collection yet. Ask me to find papers on a topic first.",
            "run_id": None,
        }
    new_papers = "No monitoring run has been recorded for this collection yet."
    try:
        events = [e for e in store.list_events(owner) if e["kind"] in {"newly_indexed_paper"}]
        monitors = store.list_monitors(owner)
        if events:
            new_papers = "New papers since monitoring began:\n" + "\n".join(
                f"• {e['payload'].get('title') or e['subject_id']} ({e['created_at']})"
                for e in events[:10]
            )
        elif any(m.get("last_success_at") for m in monitors):
            new_papers = "The last monitoring run completed and found no new papers."
    except (KeyError, TypeError):
        pass
    return {
        "text": _answer(query, run, history_text, run_id or "", new_papers),
        "run_id": run_id,
    }
