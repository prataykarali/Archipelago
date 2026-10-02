"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from . import _deps as _rt  # noqa: F401


class LibQwenConceptExtractor:
    """Extracts pedagogical concepts and prerequisites conforming to the 8-key OKF contract."""

    def __init__(
        self,
        model_name: str = _rt.DEFAULT_MODEL,
        host: str = "http://localhost:11434",
    ):
        self.model_name = model_name
        self.host = host
        self.client = _rt.ollama.Client(host=self.host) if _rt.OLLAMA_AVAILABLE else None

    def extract_from_chunk(
        self,
        text: str,
        book_title: str = "",
        page_number: int = 1,
        domain: str = "",
    ) -> list[dict]:
        """Extract structured concepts conforming to the 8-key contract from chunk."""
        if _rt.is_negative_sample(text):
            _rt.logger.debug("Dropped negative boilerplate sample (page %d)", page_number)
            return []

        if not self.client:
            _rt.logger.warning("Ollama client unavailable, returning empty concept list")
            return []

        prompt = (
            "You are an OKF extraction engine for the Archipelago knowledge graph.\n"
            "From the TEXT below, extract 1-5 teachable CONCEPTS as a JSON array.\n\n"
            "Each object MUST have exactly these keys: concept_name, concept_type, difficulty, summary, prerequisites, unlocks, related_to, tags.\n"
            "Do not extract celebrities, authors as concepts, or evaluation boilerplate.\n\n"
            f"SOURCE: '{book_title}' (Domain: {domain}, Page {page_number})\n"
            "TEXT:\n"
            f"{text[:2500]}"
        )

        try:
            resp = self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                think=False,
                options={"temperature": 0.1, "num_predict": 1200},
            )
            raw = resp.message.content
            parsed = _rt.clean_json_payload(raw)
            concepts = []

            for c in parsed.get("concepts", []):
                raw_name = (c.get("concept_name") or c.get("name") or "").strip()
                name = _rt.canonicalize_concept_name(raw_name)
                defn = (c.get("summary") or c.get("definition") or "").strip()

                ctype = (c.get("concept_type") or "definition").lower().strip()
                if ctype not in ("core", "technique", "definition", "algorithm", "theorem"):
                    ctype = "definition"

                diff = (c.get("difficulty") or "intermediate").lower().strip()
                if diff not in ("foundational", "intermediate", "advanced"):
                    diff = "intermediate"

                if not name or len(name) < 3 or len(defn) < 15:
                    continue

                # Filter out generic chapter headers
                if any(h in name.lower() for h in ["chapter", "section", "summary", "exercise", "introduction", "table of"]):
                    continue

                cid = _rt.canonical_concept_id(name)

                # Prerequisites (self-loops eliminated, canonicalized)
                raw_prereqs = c.get("prerequisites") or []
                prereqs = []
                for p in raw_prereqs:
                    p_name = p.get("name") if isinstance(p, dict) else str(p)
                    canon_p = _rt.canonicalize_concept_name(p_name)
                    if canon_p and len(canon_p) >= 3 and _rt.canonical_concept_id(canon_p) != cid:
                        if canon_p not in prereqs:
                            prereqs.append(canon_p)

                # Unlocks (self-loops eliminated, canonicalized)
                raw_unlocks = c.get("unlocks") or []
                unlocks = []
                for u in raw_unlocks:
                    u_name = u.get("name") if isinstance(u, dict) else str(u)
                    canon_u = _rt.canonicalize_concept_name(u_name)
                    if canon_u and len(canon_u) >= 3 and _rt.canonical_concept_id(canon_u) != cid:
                        if canon_u not in unlocks:
                            unlocks.append(canon_u)

                # Related_to (self-loops eliminated, canonicalized)
                raw_related = c.get("related_to") or []
                related_to = []
                for r in raw_related:
                    if isinstance(r, dict):
                        r_target = _rt.canonicalize_concept_name(r.get("concept") or r.get("name") or "")
                        r_rel = (r.get("relation") or "uses").lower().strip()
                    else:
                        r_target = _rt.canonicalize_concept_name(str(r))
                        r_rel = "uses"
                    if r_target and len(r_target) >= 3 and _rt.canonical_concept_id(r_target) != cid:
                        related_to.append({"concept": r_target, "relation": r_rel})

                # Tags
                tags = [
                    str(t).lower().strip().replace(" ", "-")
                    for t in c.get("tags") or []
                    if isinstance(t, str) and len(t.strip()) >= 2
                ]

                concepts.append({
                    "id": cid,
                    "concept_name": name,
                    "name": name,
                    "concept_type": ctype,
                    "difficulty": diff,
                    "summary": defn,
                    "definition": defn,
                    "prerequisites": prereqs,
                    "unlocks": unlocks,
                    "related_to": related_to,
                    "tags": tags,
                    "domain": domain,
                    "source_book": book_title,
                    "page_number": page_number,
                })

            return concepts

        except Exception as exc:
            _rt.logger.warning("Extraction error with lib-qwen on page %d: %s", page_number, exc)
            return []

    def extract_from_text(
        self,
        text: str,
        doc_id: str = "",
        page_number: int = 1,
        book_title: str = "",
        domain: str = "Computer Science",
    ) -> list[dict]:
        """Extract structured concepts from text (convenience alias for extract_from_chunk)."""
        return self.extract_from_chunk(
            text=text,
            book_title=book_title,
            page_number=page_number,
            domain=domain,
        )

    def second_pass_relation_resolver(
        self,
        extracted_concepts: list[dict],
    ) -> list[dict]:
        """
        Validate and resolve relationship integrity:
        1. Eliminate reciprocal dependency cycles (A -> B and B -> A) across prerequisites and unlocks.
        2. Remove self-loops.
        3. Harmonize prerequisite IDs against canonical concept registry.
        """
        name_to_id = {c["name"].lower(): c["id"] for c in extracted_concepts}
        resolved = []
        directed_prereq_edges = set()
        directed_unlock_edges = set()

        for c in extracted_concepts:
            cid = c["id"]
            c_name = c["name"]

            # 1. Prerequisite edges
            valid_prereqs = []
            for p_item in c.get("prerequisites", []):
                p_name = p_item["name"] if isinstance(p_item, dict) else str(p_item)
                p_name_canon = _rt.canonicalize_concept_name(p_name)
                p_id = name_to_id.get(p_name_canon.lower()) or _rt.canonical_concept_id(p_name_canon)

                if p_id == cid:
                    continue  # Self-loop

                # Check reciprocal cycle: (p_id, cid) already asserted as prerequisite
                if (p_id, cid) in directed_prereq_edges:
                    _rt.logger.debug("Discarded reciprocal prerequisite: %s -> %s", cid, p_id)
                    continue

                directed_prereq_edges.add((cid, p_id))
                valid_prereqs.append({"id": p_id, "name": p_name_canon})

            # 2. Unlock edges
            valid_unlocks = []
            for u_item in c.get("unlocks", []):
                u_name = u_item["name"] if isinstance(u_item, dict) else str(u_item)
                u_name_canon = _rt.canonicalize_concept_name(u_name)
                u_id = name_to_id.get(u_name_canon.lower()) or _rt.canonical_concept_id(u_name_canon)

                if u_id == cid:
                    continue  # Self-loop

                # If u_id already requires cid, cid unlocking u_id is consistent.
                # But if u_id unlocks cid, that is a reciprocal cycle.
                if (u_id, cid) in directed_unlock_edges:
                    _rt.logger.debug("Discarded reciprocal unlock: %s -> %s", cid, u_id)
                    continue

                directed_unlock_edges.add((cid, u_id))
                valid_unlocks.append({"id": u_id, "name": u_name_canon})

            c_copy = dict(c)
            c_copy["prerequisites"] = valid_prereqs
            c_copy["unlocks"] = valid_unlocks
            resolved.append(c_copy)

        return resolved
