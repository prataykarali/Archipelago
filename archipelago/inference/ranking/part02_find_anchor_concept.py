"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import re
from thefuzz import fuzz
from archipelago.inference import state as st
from archipelago.inference.aliases import (
    extract_acronym, generate_aliases, _core_concept_bonus, _clean_query_words,
)
from . import _deps as _rt  # noqa: F401


def find_anchor_concept(query):
    """Return ``(concept_id, confidence)`` for a defensible strong anchor.

    Strong hits need high cosine *and* non-trivial lexical fit so vague queries
    do not pin onto an unrelated high-dim embedding neighbor.
    """
    ranked = _rt.rank_concepts(query, top_k=5)
    if not ranked:
        return None, 0.0

    try:
        from archipelago.inference.llm_gateway import gateway_chat
        
        candidate_lines = []
        for cand in ranked:
            lbl = cand.get("label") or cand.get("name") or cand["id"]
            summary = cand.get("summary") or ""
            candidate_lines.append(f"- ID: '{cand['id']}' | Label: '{lbl}' | Summary: '{summary}'")
        candidates_str = "\n".join(candidate_lines)

        system_prompt = (
            "You are a precise concept-matching system.\n"
            "Given a user query and a list of candidate concepts, identify which concept ID "
            "best matches the user query. You must only choose a concept ID from the list "
            "if it is a clear, direct, and correct match.\n"
            "If there is a match, reply ONLY with the matched concept's ID (e.g. 'low_rank_adaptation').\n"
            "If none of the concepts in the list matches the query, reply ONLY with 'None'.\n"
            "Do not explain, do not add introductory text, just output the raw ID or 'None'."
        )
        user_content = f"User Query: {query}\n\nCandidate Concepts:\n{candidates_str}\n\nAnswer:"

        llm_response = gateway_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            purpose="routing",
            temperature=0.0,
            max_tokens=30,
            timeout=10,
        ) or ""
        cleaned_response = llm_response.strip().strip("'\"`").strip()
        
        if cleaned_response.lower() == "none":
            return None, 0.0

        for cand in ranked:
            if cleaned_response == cand["id"] or cleaned_response.lower() == cand["id"].lower():
                cos = float(cand.get("cos") or 0.0)
                lexical = float(cand.get("lexical") or 0.0)
                alias_boost = float(cand.get("alias_boost") or 0.0)
                core_boost = float(cand.get("core_boost") or 0.0)
                # LLM confirmation + surface evidence → same confidence scale
                # as the heuristic path, so downstream gates behave identically.
                if alias_boost >= 0.25 or core_boost >= 0.35:
                    return cand["id"], max(cos, lexical, 0.9)
                return cand["id"], max(cos, lexical)
    except Exception as e:
        print(f"Ollama call failed or unavailable during find_anchor_concept: {e}")

    for cand in ranked:
        cos = float(cand.get("cos") or 0.0)
        blended = float(cand.get("blended") or 0.0)
        lexical = float(cand.get("lexical") or 0.0)
        alias_boost = float(cand.get("alias_boost") or 0.0)
        core_boost = float(cand.get("core_boost") or 0.0)
        # Session 2: alias/acronym or core-concept hit → strong anchor
        if alias_boost >= 0.25 or core_boost >= 0.35:
            print(
                f"Anchor Match (alias/core): {cand['id']} "
                f"(alias={alias_boost:.2f}, core={core_boost:.2f}, blended={blended:.4f})"
            )
            return cand["id"], max(cos, lexical, 0.9)
        # Pure high cosine + some label/summary fit
        if cos >= st.SEMANTIC_ANCHOR_THRESHOLD and lexical >= 0.22:
            print(
                f"Anchor Match (strong): {cand['id']} "
                f"(cos: {cos:.4f}, lex: {lexical:.4f}, blended: {blended:.4f})"
            )
            return cand["id"], cos
        # Very high cosine alone
        if cos >= st.SEMANTIC_ANCHOR_THRESHOLD + 0.12:
            print(f"Anchor Match (very high cos): {cand['id']} (cos: {cos:.4f})")
            return cand["id"], cos
        # Strong lexical when embeddings offline / weak
        if lexical >= 0.72 and (cos >= st.DOMAIN_SOFT_THRESHOLD or not st.use_embeddings):
            print(f"Anchor Match (lexical-strong): {cand['id']} (lex: {lexical:.4f})")
            return cand["id"], max(cos, lexical)

    best = ranked[0]
    print(
        f"No strong anchor; top={best['id']} cos={float(best['cos']):.4f} "
        f"lex={float(best.get('lexical') or 0):.4f} "
        f"(strong>={st.SEMANTIC_ANCHOR_THRESHOLD}, soft>={st.DOMAIN_SOFT_THRESHOLD})"
    )
    return None, float(best.get("cos") or 0.0)


def _has_surface_concept_hit(ranked: list, query: str) -> bool:
    """True when top ranked concepts share a label/alias/acronym with the query."""
    if not ranked:
        return False
    ql = (query or "").lower()
    norm = _rt.normalize_user_query(query).lower()
    q_tokens = _clean_query_words(ql) | _clean_query_words(norm)
    for r in ranked[:5]:
        if float(r.get("alias_boost") or 0) >= 0.12:
            return True
        if float(r.get("core_boost") or 0) >= 0.30:
            return True
        if float(r.get("lexical") or 0) >= 0.45:
            return True
        label = (r.get("label") or r.get("name") or "").lower()
        cid = (r.get("id") or "").lower().replace("_", " ")
        for tok in q_tokens:
            if len(tok) >= 3 and (tok in label or tok in cid):
                return True
        concept = st.CONCEPTS_DATA.get(r.get("id") or "", {})
        aliases = concept.get("aliases") or generate_aliases(concept)
        for a in aliases:
            al = (a or "").lower()
            if len(al) < 2:
                continue
            if al in ql or al in norm:
                return True
            if any(t == al or t == al + "s" or (t.endswith("s") and t[:-1] == al) for t in q_tokens):
                return True
    return False


def _has_strong_graph_evidence(ranked: list) -> bool:
    """True when the graph itself holds something clearly related to the query.

    Stricter than _has_surface_concept_hit: a shared generic token (e.g. the
    word "matrix" in a movie question) is NOT enough — we require an alias or
    acronym hit, a core-concept mapping, or high lexical/embedding similarity.
    This is the graph-grounded scope signal that replaces keyword-list vetoes.
    """
    for r in (ranked or [])[:5]:
        if float(r.get("alias_boost") or 0.0) >= 0.26:
            return True
        if float(r.get("core_boost") or 0.0) >= 0.35:
            return True
        if float(r.get("lexical") or 0.0) >= 0.60:
            return True
        if st.use_embeddings and float(r.get("cos") or 0.0) >= 0.62:
            return True
    return False


def _select_soft_anchor(ranked, query):
    """Pick the best soft anchor from ranked neighbors (embed + label + id fit).

    Session 2: prefer core concept IDs / short labels when the query is an
    acronym or short alias (LoRA → low_rank_adaptation, not family variants).
    """
    if not ranked:
        return None
    q = (query or "").lower()
    best, best_s = None, -1.0
    for r in ranked:
        cos = float(r.get("cos") or 0.0)
        lexical = float(r.get("lexical") or 0.0)
        id_lex = fuzz.token_set_ratio(q, (r.get("id") or "").replace("_", " ")) / 100.0
        label = (r.get("label") or "").lower()
        cid = r.get("id") or ""
        token_hit = 0.0
        for tw in _clean_query_words(q):
            if len(tw) >= 3 and tw in label.replace("-", " "):
                token_hit = max(token_hit, 0.22)
        core = float(r.get("core_boost") or 0.0) + float(r.get("alias_boost") or 0.0)
        if not core:
            concept = st.CONCEPTS_DATA.get(cid, {})
            core = _core_concept_bonus(query, cid, r.get("label") or "", generate_aliases(concept))
        # Prefer shorter labels when query is a short token (acronym)
        length_adj = 0.0
        q_core = re.sub(
            r"^(what is|what's|whats|explain|tell me about)\s+",
            "",
            q,
            flags=re.I,
        ).strip(" ?!.")
        if len(q_core) <= 6 and q_core.isalpha():
            words = len(label.split())
            if words <= 3:
                length_adj += 0.15
            elif words >= 6:
                length_adj -= 0.20
        score = cos * 0.40 + lexical * 0.28 + id_lex * 0.12 + token_hit + core * 0.55 + length_adj
        # Tie-break: already-ranked blended if present
        score += 0.05 * float(r.get("blended") or 0.0)
        if score > best_s:
            best_s = score
            best = r
    return best
