"""Multi-hop curriculum chains with book/page links."""
from __future__ import annotations

import hashlib
import kuzu

from archipelago.inference.graph_lock import graph_lock
from archipelago.inference import state as st
from archipelago.inference.aliases import _node_name, pdf_page_url, markdown_pdf_link
from archipelago.inference.neighborhood import get_concept_citations, is_plausible_prereq
from archipelago.inference.citations import _normalize_legacy_citation

def _hop_provenance(concept_id, citation_map=None):
    """Resolve doc/page/url for a hop from citation_map or Kuzu evidence."""
    evidence = None
    if citation_map and concept_id in citation_map and citation_map[concept_id]:
        evidence = citation_map[concept_id][0]
    if not evidence:
        cites = get_concept_citations(concept_id, limit=1)
        if cites:
            evidence = _normalize_legacy_citation(cites[0])
    if not evidence:
        return {"doc_id": None, "page_number": None, "url": "", "evidence_id": None}
    doc_id = evidence.get("doc_id")
    page = evidence.get("page_number")
    if isinstance(page, int) and page <= 0:
        page = None
    return {
        "doc_id": doc_id,
        "page_number": page if isinstance(page, int) else None,
        "url": pdf_page_url(doc_id, page if isinstance(page, int) else None),
        "evidence_id": evidence.get("evidence_id"),
    }


def find_curriculum_chains(concept_id, max_hops=3, citation_map=None, max_paths=4):
    """Find multi-hop prerequisite chains (2–3 hops max) along REQUIRES edges.

    Returns a list of path dicts::
        {
          "nodes": [{id, name, summary, hop, doc_id, page_number, url}, ...],
          "labels": ["LoRA", "Transformer", ...],  # root → … → deepest prereq
          "markdown": "A → [B](url#page=N) → …"
        }

    Direction: root concept REQUIRES prereq1 REQUIRES prereq2 … (learn deepest first).
    Uses in-memory st.CONCEPTS_DATA + Kuzu; fails soft to [].
    """
    max_hops = max(1, min(int(max_hops or 6), 6))
    root_id = str(concept_id or "").replace("'", "\\'")
    if not root_id:
        return []

    # Build adjacency from Kuzu: from_id REQUIRES to_id (to is prerequisite)
    adj = {}
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            # Collect all REQUIRES edges among concepts reachable within max_hops
            res = conn.execute(
                f"""
                MATCH (a:Concept {{id: '{root_id}'}})-[:REQUIRES*1..{max_hops}]->(b:Concept)
                RETURN DISTINCT b.id
                """
            )
            reachable = {root_id}
            while res.has_next():
                reachable.add(res.get_next()[0])
            # Fetch edges among root + reachable
            res = conn.execute("MATCH (a:Concept)-[:REQUIRES]->(b:Concept) RETURN a.id, b.id, b.name, b.summary")
            while res.has_next():
                a_id, b_id, b_name, b_sum = res.get_next()
                if a_id not in reachable and a_id != root_id:
                    continue
                if not is_plausible_prereq(a_id, b_id):
                    continue
                adj.setdefault(a_id, []).append({
                    "id": b_id,
                    "name": b_name,
                    "summary": b_sum or "",
                })
    except Exception as e:
        print(f"find_curriculum_chains graph error: {e}")
        # Fallback: use st.CONCEPTS_DATA prerequisites lists if present
        adj = {}
        node = st.CONCEPTS_DATA.get(concept_id) or st.CONCEPTS_DATA.get(root_id) or {}
        # Build id→name map for name-based prereq lists
        name_to_id = {}
        for cid, c in st.CONCEPTS_DATA.items():
            name_to_id[(c.get("label") or c.get("name") or "").lower()] = cid
        def prereq_ids_for(cid):
            c = st.CONCEPTS_DATA.get(cid) or {}
            out = []
            for p in c.get("prerequisites") or []:
                if isinstance(p, dict) and p.get("id"):
                    if is_plausible_prereq(cid, p["id"]):
                        out.append(p)
                elif isinstance(p, str):
                    pid = name_to_id.get(p.lower())
                    if pid and is_plausible_prereq(cid, pid):
                        pc = st.CONCEPTS_DATA.get(pid, {})
                        out.append({
                            "id": pid,
                            "name": pc.get("label") or pc.get("name") or p,
                            "summary": pc.get("summary") or "",
                        })
            return out
        # BFS expand adjacency via st.CONCEPTS_DATA only
        frontier = [concept_id]
        seen = {concept_id}
        for _ in range(max_hops):
            nxt = []
            for cid in frontier:
                kids = prereq_ids_for(cid)
                if kids:
                    adj[cid] = kids
                for k in kids:
                    kid = k["id"]
                    if kid not in seen:
                        seen.add(kid)
                        nxt.append(kid)
            frontier = nxt

    # DFS/BFS collect simple paths root → prereq → … depth 1..max_hops
    paths = []

    def walk(current_id, trail):
        if len(paths) >= max_paths:
            return
        children = adj.get(current_id) or []
        if not children:
            if len(trail) >= 2:  # at least root + one prereq
                paths.append(list(trail))
            return
        extended = False
        for child in children:
            cid = child["id"]
            if any(h["id"] == cid for h in trail):
                continue  # cycle
            if len(trail) >= max_hops + 1:
                continue
            hop = {
                "id": cid,
                "name": child.get("name") or cid,
                "summary": child.get("summary") or "",
                "hop": len(trail),  # 0=root, 1=first prereq, …
            }
            walk(cid, trail + [hop])
            extended = True
            if len(paths) >= max_paths:
                return
        if not extended and len(trail) >= 2:
            paths.append(list(trail))

    root_node = st.CONCEPTS_DATA.get(concept_id) or st.CONCEPTS_DATA.get(root_id) or {}
    root_hop = {
        "id": concept_id,
        "name": _node_name(root_node) if root_node else concept_id,
        "summary": (root_node.get("summary") or "") if root_node else "",
        "hop": 0,
    }
    walk(concept_id, [root_hop])

    # Enrich with provenance + markdown
    results = []
    for trail in paths[:max_paths]:
        nodes = []
        for hop in trail:
            prov = _hop_provenance(hop["id"], citation_map)
            node = {**hop, **prov}
            nodes.append(node)
        # Learning order: deepest prerequisite first → target last
        learn_order = list(reversed(nodes))
        labels = [n["name"] for n in learn_order]
        md_parts = []
        for n in learn_order:
            if n.get("url") and n.get("doc_id"):
                page = n.get("page_number")
                page_lbl = f"p.{page}" if page else "PDF"
                md_parts.append(markdown_pdf_link(f"{n['name']} ({page_lbl})", n["doc_id"], page))
            else:
                md_parts.append(n["name"])
        results.append({
            "nodes": nodes,
            "learn_order": learn_order,
            "labels": labels,
            "markdown": " → ".join(md_parts),
            "hops": max(0, len(nodes) - 1),
        })
    # Prefer longer (richer) chains first
    results.sort(key=lambda p: p["hops"], reverse=True)
    return results


def format_curriculum_paths_section(curriculum_paths):
    """Markdown section for curriculum chains with clickable page links.

    Prefer multi-hop paths; fall back to 1-hop with a quieter label so the UI
    does not advertise "multi-hop" spam for single edges.
    """
    if not curriculum_paths:
        return ""
    multi = [p for p in curriculum_paths if int(p.get("hops") or 0) >= 2]
    paths = multi[:3] if multi else curriculum_paths[:2]
    title = (
        "\n**Multi-hop curriculum path:**"
        if multi
        else "\n**Learning path (from graph prerequisites):**"
    )
    lines = [title]
    for i, path in enumerate(paths, 1):
        md = path.get("markdown") or " → ".join(path.get("labels") or [])
        hops = path.get("hops", 0)
        if multi:
            lines.append(f"{i}. {md}" + (f"  \n   _{hops} hop{'s' if hops != 1 else ''}_" if hops else ""))
        else:
            lines.append(f"{i}. {md}")
    lines.append("\n_Click a book link to open the PDF at the cited page._")
    return "\n".join(lines)


def find_roadmap_between(
    start_concept_id: str,
    target_concept_id: str,
    max_hops: int = 6,
    citation_map: dict | None = None,
) -> dict:
    """Find a directed learning roadmap from start_concept_id (X) to target_concept_id (Y) across 1 to max_hops.

    Learning progression flows:
    - From prerequisite to dependent (reverse REQUIRES).
    - From enabler to enabled (forward UNLOCKS).
    - Via RELATED bridges if strictly necessary.

    Returns:
        A dict with start_id, target_id, hops, steps, markdown, found.
    """
    max_hops = max(1, min(int(max_hops or 6), 6))
    start_id = str(start_concept_id or "").strip()
    target_id = str(target_concept_id or "").strip()

    if not start_id or not target_id:
        return {"found": False, "hops": 0, "steps": [], "markdown": "", "error": "Missing concept IDs"}

    if start_id == target_id:
        node = st.CONCEPTS_DATA.get(start_id) or {}
        prov = _hop_provenance(start_id, citation_map)
        step = {
            "hop": 0,
            "id": start_id,
            "name": _node_name(node) if node else start_id,
            "summary": (node.get("summary") or "").strip(),
            "difficulty": node.get("difficulty") or "intermediate",
            **prov,
        }
        return {
            "found": True,
            "hops": 0,
            "start_id": start_id,
            "start_name": step["name"],
            "target_id": target_id,
            "target_name": step["name"],
            "steps": [step],
            "markdown": f"**Baseline already met:** {step['name']} is your current starting point.",
        }

    # Build directed learning adjacency graph where edge (u -> v) means learning u unlocks or leads to v
    adj: dict[str, list[dict]] = {}

    # 1. Query KuzuDB for live edges
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            # b REQUIRES a => learning a enables b (a -> b)
            res = conn.execute(
                """
                MATCH (b:Concept)-[:REQUIRES]->(a:Concept)
                RETURN a.id, b.id
                """
            )
            while res.has_next():
                a_id, b_id = res.get_next()
                if is_plausible_prereq(b_id, a_id):
                    adj.setdefault(a_id, []).append({"id": b_id, "rel": "requires_rev"})

            # a UNLOCKS b => learning a enables b (a -> b)
            try:
                res_u = conn.execute("MATCH (a:Concept)-[:UNLOCKS]->(b:Concept) RETURN a.id, b.id")
                while res_u.has_next():
                    a_id, b_id = res_u.get_next()
                    adj.setdefault(a_id, []).append({"id": b_id, "rel": "unlocks"})
            except Exception:
                pass
    except Exception as e:
        print(f"Kuzu roadmap graph lookup error: {e}")

    # 2. Augment adjacency from in-memory st.CONCEPTS_DATA
    for cid, node in st.CONCEPTS_DATA.items():
        for p in node.get("prerequisites") or []:
            pid = p.get("id") if isinstance(p, dict) else str(p).lower().replace(" ", "_")
            if pid and pid in st.CONCEPTS_DATA and is_plausible_prereq(cid, pid):
                adj.setdefault(pid, []).append({"id": cid, "rel": "requires_rev"})
        for u in node.get("unlocks") or []:
            uid = u.get("id") if isinstance(u, dict) else str(u).lower().replace(" ", "_")
            if uid and uid in st.CONCEPTS_DATA:
                adj.setdefault(cid, []).append({"id": uid, "rel": "unlocks"})

    # BFS shortest path from start_id to target_id
    queue = [[start_id]]
    visited = {start_id}
    found_path = None

    while queue:
        path = queue.pop(0)
        curr = path[-1]
        if curr == target_id:
            found_path = path
            break
        if len(path) > max_hops:
            continue
        for neighbor in adj.get(curr, []):
            nid = neighbor["id"]
            if nid not in visited:
                visited.add(nid)
                queue.append(path + [nid])

    # If no strict forward path found, try reverse search (in case target was entered as prerequisite)
    if not found_path:
        rev_queue = [[target_id]]
        rev_visited = {target_id}
        while rev_queue:
            path = rev_queue.pop(0)
            curr = path[-1]
            if curr == start_id:
                found_path = list(reversed(path))
                break
            if len(path) > max_hops:
                continue
            for neighbor in adj.get(curr, []):
                nid = neighbor["id"]
                if nid not in rev_visited:
                    rev_visited.add(nid)
                    rev_queue.append(path + [nid])

    # If still not found, check if a multi-hop curriculum chain from target_id already includes start_id
    if not found_path:
        chains = find_curriculum_chains(target_id, max_hops=max_hops, citation_map=citation_map)
        for ch in chains:
            learn_order = ch.get("learn_order", [])
            ids = [n["id"] for n in learn_order]
            if start_id in ids:
                start_idx = ids.index(start_id)
                found_path = ids[start_idx:]
                break

    s_node = st.CONCEPTS_DATA.get(start_id) or {}
    t_node = st.CONCEPTS_DATA.get(target_id) or {}
    s_name = _node_name(s_node) if s_node else start_id
    t_name = _node_name(t_node) if t_node else target_id

    if not found_path:
        return {
            "found": False,
            "hops": 0,
            "start_id": start_id,
            "target_id": target_id,
            "start_name": s_name,
            "target_name": t_name,
            "steps": [],
            "markdown": f"No direct roadmap path found between **{s_name}** and **{t_name}** within {max_hops} hops.",
        }

    # Enrich path steps with provenance, summary, and difficulty
    steps = []
    for hop_idx, node_id in enumerate(found_path):
        node = st.CONCEPTS_DATA.get(node_id) or {}
        prov = _hop_provenance(node_id, citation_map)
        step = {
            "hop": hop_idx,
            "id": node_id,
            "name": _node_name(node) if node else node_id,
            "summary": (node.get("summary") or "").strip(),
            "difficulty": node.get("difficulty") or "intermediate",
            **prov,
        }
        steps.append(step)

    # Format Markdown representation
    md_parts = []
    for s in steps:
        if s.get("url") and s.get("doc_id"):
            page = s.get("page_number")
            page_lbl = f"p.{page}" if page else "PDF"
            md_parts.append(markdown_pdf_link(f"{s['name']} ({page_lbl})", s["doc_id"], page))
        else:
            md_parts.append(f"**{s['name']}**")

    hops_count = len(steps) - 1
    markdown_output = (
        f"### Personalized Learning Roadmap ({hops_count} hop{'s' if hops_count != 1 else ''})\n"
        + " → ".join(md_parts)
        + "\n\n"
    )
    for s in steps:
        difficulty_badge = f"`[{s['difficulty'].upper()}]`" if s.get("difficulty") else ""
        markdown_output += f"- **Step {s['hop'] + 1}: {s['name']}** {difficulty_badge}: {s['summary']}\n"

    return {
        "found": True,
        "hops": hops_count,
        "start_id": start_id,
        "start_name": steps[0]["name"],
        "target_id": target_id,
        "target_name": steps[-1]["name"],
        "steps": steps,
        "markdown": markdown_output.strip(),
    }


def generate_diagnostic_quiz(
    target_concept_id: str,
    num_questions: int = 5,
) -> dict:
    """Generate 5-6 multiple choice diagnostic questions (MCQs) testing prerequisites of target_concept_id.

    Assesses whether the student has the background needed for target_concept_id,
    identifying their highest mastered concept X to build a personalized roadmap X -> Y.
    """
    target_id = str(target_concept_id or "").strip().lower()
    target_node = st.CONCEPTS_DATA.get(target_id) or {}
    target_name = _node_name(target_node) if target_node else target_id

    # Gather prerequisite concepts (up to 6 hops away)
    prereq_chain = find_curriculum_chains(target_id, max_hops=6, max_paths=4)
    prereq_ids = []
    seen = {target_id}

    for chain in prereq_chain:
        for node in chain.get("nodes", []):
            nid = node.get("id")
            if nid and nid not in seen:
                seen.add(nid)
                prereq_ids.append(nid)

    # If we need more candidates, add related concepts or domain foundational concepts
    if len(prereq_ids) < num_questions:
        for r in target_node.get("related_to") or []:
            rid = r.get("concept") or r.get("id")
            if rid and rid in st.CONCEPTS_DATA and rid not in seen:
                seen.add(rid)
                prereq_ids.append(rid)

    if len(prereq_ids) < num_questions:
        target_tags = set(target_node.get("tags") or [])
        for cid, c in st.CONCEPTS_DATA.items():
            if cid not in seen and (c.get("summary") or len(c.get("summary", "")) > 20):
                if target_tags and target_tags.intersection(set(c.get("tags") or [])):
                    seen.add(cid)
                    prereq_ids.append(cid)
                    if len(prereq_ids) >= num_questions + 2:
                        break

    if len(prereq_ids) < num_questions:
        for cid, c in st.CONCEPTS_DATA.items():
            if cid not in seen and c.get("summary") and len(c.get("summary", "")) > 25:
                seen.add(cid)
                prereq_ids.append(cid)
                if len(prereq_ids) >= num_questions:
                    break

    def _diff_key(cid):
        diff = (st.CONCEPTS_DATA.get(cid, {}).get("difficulty") or "").lower()
        order = {"foundational": 0, "intermediate": 1, "advanced": 2, "expert": 3}
        return order.get(diff, 1)

    prereq_ids.sort(key=_diff_key)
    selected_cids = prereq_ids[:max(num_questions, 5)]

    distractor_pool = [
        (c.get("summary") or "").strip()
        for cid, c in st.CONCEPTS_DATA.items()
        if cid not in selected_cids and c.get("summary") and len(c.get("summary", "")) > 30
    ]

    questions = []
    choice_letters = ["A", "B", "C", "D"]

    for q_idx, cid in enumerate(selected_cids, 1):
        c_node = st.CONCEPTS_DATA.get(cid) or {}
        c_name = _node_name(c_node) if c_node else cid
        correct_summary = (c_node.get("summary") or f"A fundamental technique used in {c_name}.").strip()
        difficulty = c_node.get("difficulty") or "intermediate"

        # Deterministic distractor selection using hash
        h_val = int(hashlib.md5(f"{cid}_{q_idx}".encode()).hexdigest(), 16)
        distractors = []
        for d_offset in range(3):
            d_idx = (h_val + d_offset * 17) % max(1, len(distractor_pool))
            distractors.append(distractor_pool[d_idx] if distractor_pool else "Alternative machine learning method.")

        all_options = [correct_summary] + distractors[:3]
        perm_idx = h_val % 4
        shuffled = all_options[perm_idx:] + all_options[:perm_idx]
        correct_letter = choice_letters[shuffled.index(correct_summary)]
        options_dict = {choice_letters[i]: opt for i, opt in enumerate(shuffled)}

        questions.append({
            "q_index": q_idx,
            "concept_id": cid,
            "concept_name": c_name,
            "difficulty": difficulty,
            "question": f"Which of the following best describes the core role or definition of **{c_name}**?",
            "options": options_dict,
            "correct_option": correct_letter,
            "explanation": f"**{c_name}**: {correct_summary}",
        })

    return {
        "target_concept": {
            "id": target_id,
            "name": target_name,
            "summary": target_node.get("summary") or "",
        },
        "num_questions": len(questions),
        "questions": questions,
    }


def evaluate_quiz_and_route_roadmap(
    quiz_responses: dict,
    target_concept_id: str,
    quiz_data: dict | None = None,
    max_hops: int = 6,
) -> dict:
    """Evaluate student's quiz responses, determine highest mastered prerequisite X, and return roadmap X -> Y.

    Args:
        quiz_responses: dict mapping question index or concept_id -> chosen option letter (e.g. {"1": "A", "2": "C"}).
        target_concept_id: The ultimate learning goal Y.
        quiz_data: The quiz generated by generate_diagnostic_quiz (generated fresh if None).
        max_hops: Maximum roadmap hops (1 to 6).
    """
    if not quiz_data:
        quiz_data = generate_diagnostic_quiz(target_concept_id, num_questions=5)

    questions = quiz_data.get("questions", [])
    if not questions:
        return {"error": "Could not generate questions for target concept", "target_id": target_concept_id}

    mastered = []
    gaps = []
    score = 0

    for q in questions:
        q_idx_str = str(q["q_index"])
        cid = q["concept_id"]
        correct = q["correct_option"].upper().strip()
        user_ans = (
            quiz_responses.get(q_idx_str)
            or quiz_responses.get(q["q_index"])
            or quiz_responses.get(cid)
            or ""
        ).upper().strip()

        is_correct = user_ans == correct
        item = {
            "q_index": q["q_index"],
            "concept_id": cid,
            "concept_name": q["concept_name"],
            "difficulty": q["difficulty"],
            "user_answer": user_ans,
            "correct_answer": correct,
            "is_correct": is_correct,
            "explanation": q.get("explanation") or "",
        }
        if is_correct:
            score += 1
            mastered.append(item)
        else:
            gaps.append(item)

    total = len(questions)
    accuracy = score / total if total else 0.0

    if mastered:
        start_concept_id = mastered[-1]["concept_id"]
        start_concept_name = mastered[-1]["concept_name"]
    else:
        start_concept_id = questions[0]["concept_id"]
        start_concept_name = questions[0]["concept_name"]

    roadmap = find_roadmap_between(start_concept_id, target_concept_id, max_hops=max_hops)

    return {
        "target_concept": quiz_data["target_concept"],
        "score": f"{score}/{total}",
        "score_pct": round(accuracy * 100, 1),
        "mastered_count": score,
        "gap_count": total - score,
        "mastered_concepts": [m["concept_name"] for m in mastered],
        "gap_concepts": [g["concept_name"] for g in gaps],
        "baseline_concept": {
            "id": start_concept_id,
            "name": start_concept_name,
        },
        "roadmap": roadmap,
        "details": {
            "mastered": mastered,
            "gaps": gaps,
        },
    }
