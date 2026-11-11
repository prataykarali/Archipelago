from __future__ import annotations

from collections.abc import Mapping, Sequence
import re


def is_math_concept(name: str) -> bool:
    """Helper to detect typical mathematical/statistical terms."""
    if not name:
        return False
    keywords = [
        r"\blinear\s+regression\b",
        r"\bmatrix\b",
        r"\bvector\b",
        r"\bcalculus\b",
        r"\bgradient\b",
        r"\bprobability\b",
        r"\bstatistics\b",
        r"\blinear\s+algebra\b",
        r"\bleast\s+squares\b",
        r"\beigenvalue\b",
        r"\bsvd\b",
        r"\bsingular\s+value\b",
        r"\boptimization\b",
        r"\bderivative\b",
        r"\bintegral\b",
        r"\balgebra\b",
    ]
    pattern = "|".join(keywords)
    return bool(re.search(pattern, name, re.IGNORECASE))


def enforce_dag_relations(
    relations_list: Sequence[object], concepts_dict: Mapping[str, object] | Sequence[object]
) -> list[object]:
    """
    Detect if any mathematical/statistical concept is designated as an unlock
    for an advanced/expert level concept and reverse the direction.
    """
    diff_lookup: dict[str, str] = {}
    if isinstance(concepts_dict, Mapping):
        for k, v in concepts_dict.items():
            if isinstance(v, Mapping):
                difficulty = v.get("difficulty") or v.get("concept_difficulty")
                diff_lookup[k.lower()] = (
                    difficulty if isinstance(difficulty, str) else "intermediate"
                )
            elif isinstance(v, str):
                diff_lookup[k.lower()] = v
    elif isinstance(concepts_dict, Sequence):
        for c in concepts_dict:
            if isinstance(c, Mapping) and isinstance(c.get("concept_name"), str):
                name = c["concept_name"]
                difficulty = c.get("difficulty")
                diff_lookup[name.lower()] = (
                    difficulty if isinstance(difficulty, str) else "intermediate"
                )

    def get_diff(name: object) -> str:
        if not isinstance(name, str) or not name:
            return "intermediate"
        return diff_lookup.get(name.lower(), "intermediate")

    def is_advanced(name: object) -> bool:
        diff = get_diff(name)
        return diff.lower() in ("advanced", "expert")

    def is_math_value(value: object) -> bool:
        return isinstance(value, str) and is_math_concept(value)

    modified_relations: list[object] = []
    for rel in relations_list:
        if isinstance(rel, dict):
            r: dict[str, object] = dict(rel)

            src_key = None
            for k in ["source", "from_name", "from", "concept_a", "from_id"]:
                if k in r:
                    src_key = k
                    break

            tgt_key = None
            for k in ["target", "to_name", "to", "concept_b", "to_id", "concept"]:
                if k in r:
                    tgt_key = k
                    break

            rel_key = None
            for k in ["relation", "relation_type", "edge_type"]:
                if k in r:
                    rel_key = k
                    break

            if src_key and tgt_key:
                src_val = r[src_key]
                tgt_val = r[tgt_key]
                rel_val = r.get(rel_key, "") if rel_key else ""

                # Case 1: Advanced non-math concept unlocks math concept
                if (
                    is_math_value(tgt_val)
                    and not is_math_value(src_val)
                    and is_advanced(src_val)
                    and str(rel_val).lower() in ("unlocks", "enables")
                ):
                    # Reverse so that math concept is a prerequisite
                    if rel_key:
                        r[rel_key] = "requires"
                    r[src_key] = tgt_val
                    r[tgt_key] = src_val

                # Case 2: Math concept is unlocked by Advanced concept (requires form reversed)
                elif (
                    is_math_value(src_val)
                    and not is_math_value(tgt_val)
                    and is_advanced(tgt_val)
                    and str(rel_val).lower() in ("requires", "prerequisite")
                ):
                    # Swap source and target to correct the direction
                    r[src_key] = tgt_val
                    r[tgt_key] = src_val

            modified_relations.append(r)
        elif isinstance(rel, (list, tuple)) and len(rel) >= 3:
            row = list(rel)
            src_val, tgt_val, rel_val = row[0], row[1], row[2]
            if (
                is_math_value(tgt_val)
                and not is_math_value(src_val)
                and is_advanced(src_val)
                and str(rel_val).lower() in ("unlocks", "enables")
            ) or (
                is_math_value(src_val)
                and not is_math_value(tgt_val)
                and is_advanced(tgt_val)
                and str(rel_val).lower() in ("requires", "prerequisite")
            ):
                row[0], row[1] = tgt_val, src_val

            modified_relations.append(tuple(row) if isinstance(rel, tuple) else row)
        else:
            modified_relations.append(rel)
    return modified_relations
