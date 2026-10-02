"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from . import _deps as _rt  # noqa: F401


def build_validated_edges(concepts: list, chunks: list, model_name: str = None) -> list:
    """Build and validate relationships from concepts against chunks using alias-aware matching."""
    from okf.alias_index import build_alias_index, resolve_concept_name

    concept_raw_names = []
    concept_diffs = {}
    for c in concepts:
        if isinstance(c, dict):
            name = c.get("concept_name") or c.get("name")
            if name:
                name_str = str(name).strip()
                concept_raw_names.append(name_str)
                concept_diffs[name_str.lower()] = c.get("difficulty", "intermediate")
        elif isinstance(c, str):
            concept_raw_names.append(c.strip())
            concept_diffs[c.strip().lower()] = "intermediate"

    alias_index = build_alias_index(concept_raw_names)
    canonical_concept_names = {
        resolve_concept_name(name, alias_index).lower().strip() for name in concept_raw_names
    }

    edges = []
    seen_edges = set()  # (from_lower, to_lower, edge_type)

    def add_edge(from_name, to_name, edge_type, relation, source):
        from_canon = resolve_concept_name(from_name, alias_index)
        to_canon = resolve_concept_name(to_name, alias_index)
        
        fl = from_canon.lower().strip()
        tl = to_canon.lower().strip()
        if fl == tl:
            return
        key = (fl, tl, edge_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({
            "from_name": from_canon,
            "to_name": to_canon,
            "relation": relation,
            "edge_type": edge_type,
            "source": source
        })

    for c in concepts:
        if not isinstance(c, dict):
            continue
        raw_name = c.get("concept_name", "").strip()
        name = resolve_concept_name(raw_name, alias_index)
        if not name or name.lower().strip() not in canonical_concept_names:
            continue

        doc_id = c.get("doc_id", "")
        chunk_id = c.get("chunk_id", "")
        default_source = f"{doc_id}:{chunk_id}"
        rel_prov = c.get("relation_provenance") or {}

        # Prerequisites
        for p in c.get("prerequisites", []):
            if not isinstance(p, str) or not p.strip():
                continue
            p = p.strip()
            p_canon = resolve_concept_name(p, alias_index)
            if p_canon.lower().strip() not in canonical_concept_names:
                continue

            rel_dict = {"source": name, "target": p_canon}
            if not _rt.validate_relation(rel_dict, chunks, alias_index):
                continue

            diff_a = concept_diffs.get(name.lower(), "intermediate")
            diff_b = concept_diffs.get(p_canon.lower(), "intermediate")
            obj_a = {"concept_name": name, "difficulty": diff_a}
            obj_b = {"concept_name": p_canon, "difficulty": diff_b}
            dir_first, dir_second = _rt.infer_prerequisite_direction(obj_a, obj_b, chunks)

            src = rel_prov.get(f"prereq:{p.lower()}", default_source)
            if dir_first.lower() == p_canon.lower():
                add_edge(name, p_canon, "REQUIRES", "requires", src)
            else:
                add_edge(p_canon, name, "REQUIRES", "requires", src)

        # Unlocks
        for u in c.get("unlocks", []):
            if not isinstance(u, str) or not u.strip():
                continue
            u = u.strip()
            u_canon = resolve_concept_name(u, alias_index)
            if u_canon.lower().strip() not in canonical_concept_names:
                continue

            rel_dict = {"source": name, "target": u_canon}
            if not _rt.validate_relation(rel_dict, chunks, alias_index):
                continue

            diff_a = concept_diffs.get(name.lower(), "intermediate")
            diff_b = concept_diffs.get(u_canon.lower(), "intermediate")
            obj_a = {"concept_name": name, "difficulty": diff_a}
            obj_b = {"concept_name": u_canon, "difficulty": diff_b}
            dir_first, dir_second = _rt.infer_prerequisite_direction(obj_a, obj_b, chunks)

            src = rel_prov.get(f"unlock:{u.lower()}", default_source)
            if dir_first.lower() == name.lower():
                add_edge(name, u_canon, "UNLOCKS", "enables", src)
            else:
                add_edge(u_canon, name, "UNLOCKS", "enables", src)

        # Related
        for rel in c.get("related_to", []):
            if not isinstance(rel, dict):
                continue
            target = rel.get("concept", "").strip()
            if not target:
                continue
            target_canon = resolve_concept_name(target, alias_index)
            if target_canon.lower().strip() not in canonical_concept_names:
                continue

            rel_dict = {"source": name, "target": target_canon}
            if not _rt.validate_relation(rel_dict, chunks, alias_index):
                continue

            rel_type = rel.get("relation", "related")
            src = rel_prov.get(f"related:{target.lower()}", default_source)

            if name.lower() < target_canon.lower():
                add_edge(name, target_canon, "RELATED", rel_type, src)
            else:
                add_edge(target_canon, name, "RELATED", rel_type, src)

    return edges
