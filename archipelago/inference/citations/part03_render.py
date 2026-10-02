"""Citation rendering: inline markers, deterministic brackets, anti-hallucination cleanse."""

from __future__ import annotations

import re as _re

from archipelago.inference import state as st
from archipelago.inference.aliases import page_view_markdown_link
from archipelago.inference.citations.part01_evidence import _page_display


def compile_narrative_recipe(query, target_concept, prereqs, unlocks, citations):
    target_name = target_concept.get("label", target_concept.get("name", ""))
    target_summary = target_concept.get("summary", "")

    prereqs_str = (
        "\n".join([f"   - {p['name']}: {p['summary']}" for p in prereqs])
        if prereqs
        else "   - None extracted"
    )
    unlocks_str = ", ".join([u["name"] for u in unlocks]) if unlocks else "None extracted"

    citations_str = ""
    if citations:
        for i, c in enumerate(citations[:3], 1):
            passage = c.get("text_passage") or ""
            passage = str(passage).strip()
            citations_str += (
                f"Citation {i}:\n"
                f"- Document: {c['doc_id']} (Page: {c['page_number']}, Section: {c['section_title']})\n"
                f'- Text Passage: "{passage}"\n\n'
            )
    else:
        citations_str = "No specific source citations found in the database.\n"

    recipe = (
        f"USER QUERY:\n"
        f"{query}\n\n"
        f"STRUCTURED TOPOLOGY (Narrative Recipe):\n"
        f"1. Upstream Prerequisites:\n"
        f"{prereqs_str}\n\n"
        f"2. Target Concept:\n"
        f"   - {target_name}: {target_summary}\n\n"
        f"3. Downstream Applications (Unlocks):\n"
        f"   - {unlocks_str}\n\n"
        f"TEXTUAL CITATIONS:\n"
        f"{citations_str}"
        f"INSTRUCTION:\n"
        f"You are the Generator model for the Archipelago knowledge system. Synthesize the user query, structured topology (Prerequisite -> Target -> Unlock), and textual citations into a coherent, fluid, and natural explanation. Do NOT output a JSON list of concepts. Instead, write a conversational and academic response explaining the relationship, using direct references to the concepts and citations above."
    )
    return recipe


def validate_citations(model_output, evidence_ids):
    """Check that model output cites only supplied evidence IDs.

    Returns a ``(is_valid, offending_ids)`` tuple: ``is_valid`` is True when
    every ``[S<n>:`` citation bracket found in ``model_output`` names an ID
    from ``evidence_ids``; ``offending_ids`` lists the hallucinated IDs in
    numeric order (empty when valid).
    """
    supplied = set(evidence_ids or [])
    found = set(st.CITATION_ID_PATTERN.findall(model_output or ""))
    offending = sorted(found - supplied, key=lambda eid: int(eid[1:]))
    return (not offending, offending)


def _cite_with_link(name, evidence_list):
    """Citation brackets plus markdown PDF deep-links for ALL evidence records."""
    if not evidence_list:
        return ""
    parts = []
    for ev in evidence_list:
        evidence_id = ev.get("evidence_id") or "S?"
        document = ev.get("doc_id") or "Unknown document"
        page_disp_text = _page_display(ev)
        page_suffix = f", {page_disp_text}" if page_disp_text else ""
        label = f"[{evidence_id}: {name} | {document}{page_suffix}]"
        doc_id = ev.get("doc_id")
        page = ev.get("page_number")
        if doc_id:
            link_text = page_disp_text or "source"
            link = page_view_markdown_link(
                link_text, doc_id, page if isinstance(page, int) else None, highlight=name
            )
            parts.append(f"{label} ({link})")
        else:
            parts.append(label)
    return " " + " · ".join(parts)


def _citation_marker(evidence_list, bare_markers=False):
    """Bare ' [S#]' markers for the generator contract (expanded post-hoc)."""
    if not bare_markers:
        return ""
    if not evidence_list:
        return ""
    markers = []
    for ev in evidence_list:
        eid = ev.get("evidence_id")
        if eid:
            markers.append(f"[{eid}]")
    return (" " + " ".join(markers)) if markers else ""


def render_citation_from_payload(payload):
    """Deterministically render one payload as the full inline citation.

    This is the ONLY place a bracket shown to the user is built at synthesis
    time — the generator never writes doc names or page numbers itself.
    """
    eid = payload.get("evidence_id") or "S?"
    topic = payload.get("topic") or ""
    doc_id = payload.get("doc_id") or "Unknown document"
    printed = payload.get("printed_page")
    page_number = payload.get("page_number")
    if printed is not None:
        page_disp = f"p.{printed}"
    elif isinstance(page_number, int) and page_number > 0:
        page_disp = f"PDF p.{page_number}"
    else:
        page_disp = ""
    page_suffix = f", {page_disp}" if page_disp else ""
    base = f"[{eid}: {topic} | {doc_id}{page_suffix}]"
    url = payload.get("url")
    if not url and doc_id:
        from urllib.parse import quote

        url = f"/api/page-view?doc_id={quote(doc_id, safe='')}"
        if isinstance(page_number, int) and page_number > 0:
            url += f"&page={page_number}"
        if topic:
            url += f"&highlight={quote(topic, safe='')}"
        if isinstance(page_number, int) and page_number > 0:
            url += f"#page={page_number}"

    if url and page_disp:
        return f"{base} ([{page_disp}]({url}))"
    return base


_MARKER_WITH_TAIL_RE = None  # compiled lazily in cleanse_model_citations


def cleanse_model_citations(text, citation_payloads):
    """Post-generation provenance pass (the anti-hallucination 'filler').

    The generator is only allowed bare ``[S1]`` markers. This pass:
      1. normalizes any ``[S1: invented stuff]`` back to ``[S1]``;
      2. strips markers whose ID has no real evidence payload;
      3. drops markers whose surrounding sentence never mentions the concept
         that evidence belongs to (misattached citations);
      4. expands surviving markers into the full deterministic bracket +
         PDF deep-link rendered from graph provenance;
      5. if nothing survives inline, appends a Sources footer so the reply is
         never shown without verifiable provenance.

    Returns the cleansed text. Never invents pages, docs, or IDs.
    """
    if not text:
        return text
    payloads = [p for p in (citation_payloads or []) if p.get("evidence_id")]
    by_id = {p["evidence_id"]: p for p in payloads}

    # 1. Normalize model-embellished brackets to bare markers.
    text = _re.sub(r"\[\s*(S\d+)\s*:[^\]]*\]", r"[\1]", text)
    # Also collapse comma-run markers like [S1, S2] into [S1] [S2].
    text = _re.sub(
        r"\[\s*(S\d+(?:\s*,\s*S\d+)+)\s*\]",
        lambda m: " ".join(f"[{x.strip()}]" for x in m.group(1).split(",")),
        text,
    )

    def _topic_in_sentence(sentence, topic):
        words = [w for w in _re.split(r"[^a-z0-9]+", (topic or "").lower()) if len(w) >= 3]
        if not words:
            return True
        s = sentence.lower()
        return any(w in s for w in words)

    out = []
    last = 0
    seen_inline = 0
    for m in _re.finditer(r"\[\s*(S\d+)\s*\]", text):
        out.append(text[last : m.start()])
        last = m.end()
        payload = by_id.get(m.group(1))
        if payload is None:
            continue  # invented ID → strip silently
        # 3. Sentence check: from the previous sentence boundary to the marker.
        prefix = text[: m.start()]
        boundary = max(prefix.rfind(". "), prefix.rfind("\n"), prefix.rfind("* "))
        sentence = prefix[boundary + 1 :]
        if not _topic_in_sentence(sentence, payload.get("topic")):
            continue  # misattached → drop the marker, keep the prose
        out.append(" " + render_citation_from_payload(payload))
        seen_inline += 1
    out.append(text[last:])
    cleansed = _re.sub(r"[ \t]+([.,;:!?])", r"\1", "".join(out))
    cleansed = _re.sub(r"[ \t]{2,}", " ", cleansed)

    # 5. Provenance guarantee: no inline citation survived → Sources footer.
    if seen_inline == 0 and payloads:
        lines = ["", "**Sources:**"]
        for p in payloads[:4]:
            lines.append(f"- {render_citation_from_payload(p)}")
        cleansed = cleansed.rstrip() + "\n" + "\n".join(lines)
    return cleansed
