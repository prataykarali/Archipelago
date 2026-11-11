"""Normalize graph edges from gold and extracted payloads."""

from __future__ import annotations

from typing import Any


def _extract_edges(input_data: Any) -> set[tuple[str, str]]:
    edges = set()
    if isinstance(input_data, dict):
        if "edges" in input_data:
            for e in input_data["edges"]:
                # Support export schema (from_name/to_name) and gold files (source/target).
                src = e.get("from_name") or e.get("from_id") or e.get("source") or e.get("from")
                dst = e.get("to_name") or e.get("to_id") or e.get("target") or e.get("to")
                etype = str(e.get("edge_type") or e.get("type") or "").upper()
                if src and dst:
                    src_l = str(src).strip().lower()
                    dst_l = str(dst).strip().lower()
                    if etype == "REQUIRES":
                        # Gold files encode requires as source→target (learner path).
                        # Export edges use from_name REQUIRES to_name with inverted dependency storage elsewhere.
                        if e.get("source") or e.get("target"):
                            edges.add((src_l, dst_l))
                        else:
                            edges.add((dst_l, src_l))
                    elif etype == "UNLOCKS":
                        edges.add((src_l, dst_l))
                    else:
                        edges.add((min(src_l, dst_l), max(src_l, dst_l)))
        else:
            for _cid, c in input_data.items():
                if isinstance(c, dict):
                    name = c.get("name") or c.get("concept_name")
                    if name:
                        name_l = name.strip().lower()
                        for p in c.get("prerequisites", []):
                            edges.add((p.strip().lower(), name_l))
                        for u in c.get("unlocks", []):
                            edges.add((name_l, u.strip().lower()))
                        for r in c.get("related", []):
                            if isinstance(r, dict) and r.get("concept"):
                                rc = r["concept"].strip().lower()
                                edges.add((min(name_l, rc), max(name_l, rc)))
    elif isinstance(input_data, list):
        if (
            input_data
            and isinstance(input_data[0], dict)
            and (
                "from_name" in input_data[0]
                or "source" in input_data[0]
                or "from_id" in input_data[0]
                or "from" in input_data[0]
            )
        ):
            for e in input_data:
                src = e.get("source") or e.get("from_name") or e.get("from_id") or e.get("from")
                dst = e.get("target") or e.get("to_name") or e.get("to_id") or e.get("to")
                etype = str(e.get("edge_type") or e.get("type") or "").upper()
                if src and dst:
                    src_l = src.strip().lower()
                    dst_l = dst.strip().lower()
                    if etype in ("REQUIRES", "requires"):
                        if "from_name" in e:
                            edges.add((dst_l, src_l))
                        else:
                            edges.add((src_l, dst_l))
                    elif etype in ("UNLOCKS", "unlocks"):
                        edges.add((src_l, dst_l))
                    else:
                        edges.add((min(src_l, dst_l), max(src_l, dst_l)))
        else:
            for c in input_data:
                if isinstance(c, dict):
                    if "concepts" in c:
                        for sub_c in c["concepts"]:
                            name = sub_c.get("concept_name")
                            if name:
                                name_l = name.strip().lower()
                                for p in sub_c.get("prerequisites", []):
                                    edges.add((p.strip().lower(), name_l))
                                for u in sub_c.get("unlocks", []):
                                    edges.add((name_l, u.strip().lower()))
                                for r in sub_c.get("related_to", []):
                                    if isinstance(r, dict) and r.get("concept"):
                                        rc = r["concept"].strip().lower()
                                        edges.add((min(name_l, rc), max(name_l, rc)))
                    else:
                        name = c.get("concept_name") or c.get("name")
                        if name:
                            name_l = name.strip().lower()
                            for p in c.get("prerequisites", []):
                                edges.add((p.strip().lower(), name_l))
                            for u in c.get("unlocks", []):
                                edges.add((name_l, u.strip().lower()))
                            for r in c.get("related_to", []):
                                if isinstance(r, dict) and r.get("concept"):
                                    rc = r["concept"].strip().lower()
                                    edges.add((min(name_l, rc), max(name_l, rc)))
    return edges
