"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from pathlib import Path
from flask import jsonify, send_from_directory, request, redirect
import kuzu
from ingestion_worker import job_store, get_worker, graph_lock
from archipelago.auth import require_librarian, librarian_token_expected
from archipelago.inference import state as st


@st.app.route("/api/documents", methods=["GET"])
def list_graph_documents():
    """List documents currently in the live knowledge graph."""
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            from okf.graph.delete_document import list_documents
            docs = list_documents(conn)
        return jsonify({"documents": docs, "count": len(docs)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@st.app.route("/api/documents/<path:doc_id>", methods=["DELETE"])
@require_librarian
def delete_graph_document(doc_id):
    """Librarian-only: delete a document and unmerge its contribution from the live graph.

    Removes: Document, Chunks, MENTIONS, edges whose provenance is this doc,
    and orphan concepts that no longer have mentions or structural edges.

    Shared concepts used by other documents are retained.

    Query params:
      remove_pdf=1  — also delete the file under pdfs/ when present
    """
    remove_pdf = str(request.args.get("remove_pdf") or "").lower() in (
        "1", "true", "yes", "on",
    )
    try:
        from okf.graph.delete_document import delete_document_end_to_end

        with graph_lock.write_lock():
            stats = delete_document_end_to_end(
                st.db,
                doc_id,
                base_dir=Path(st.BASE_DIR),
                okf_results_path=Path(st.BASE_DIR) / "okf_results.json",
                remove_pdf=remove_pdf,
                pdf_dir=Path(st.PDF_DIR),
            )
            # Reload inference handles + concept cache
            try:
                st.reload_db()
            except Exception as e:
                stats["reload_warning"] = str(e)
            try:
                from archipelago.inference.embeddings import build_concept_embeddings
                build_concept_embeddings()
                stats["embeddings_rebuilt"] = True
            except Exception as e:
                stats["embeddings_warning"] = str(e)

        return jsonify({"status": "deleted", **stats}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@st.app.route("/api/manual/concept", methods=["POST", "OPTIONS"])
@require_librarian
def manual_add_concept():
    """Librarian-only: insert a new concept node into KuzuDB and regenerate artifacts.

    Expected JSON body::

        {
          "name":         "Agentic System",      # required
          "concept_type": "architecture",        # required
          "difficulty":   "advanced",            # required
          "summary":      "An AI system that…", # optional
          "tags":         ["agents", "llm"]      # optional list[str]
        }
    """
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(force=True, silent=True) or {}
    name         = (data.get("name") or "").strip()
    concept_type = (data.get("concept_type") or "").strip()
    difficulty   = (data.get("difficulty") or "").strip()
    summary      = (data.get("summary") or "").strip()
    tags         = [t.strip() for t in (data.get("tags") or []) if t.strip()]

    if not name:
        return jsonify({"error": "Field 'name' is required."}), 400
    if not concept_type:
        return jsonify({"error": "Field 'concept_type' is required."}), 400
    if not difficulty:
        return jsonify({"error": "Field 'difficulty' is required."}), 400

    # Derive a slug-style ID
    concept_id = name.lower().replace(" ", "_").replace("-", "_")

    try:
        from okf.graph.ingest import ensure_concept
        from okf.graph.export import export_graph
        from okf.exports import write_all_artifacts as _waa

        with graph_lock.write_lock():
            conn = kuzu.Connection(st.db)
            ensure_concept(conn, concept_id, name, concept_type, difficulty, summary, tags)
            try:
                from okf.exports import build_visual_graph, build_graph_rag_index
                base_dir = Path(st.BASE_DIR)
                graph_export = export_graph(conn)
                graph_export["visualization"] = build_visual_graph([], graph_export)
                graph_export["graph_rag_index"] = build_graph_rag_index([], graph_export)
                _waa(graph_export, [], st.db, base_dir=base_dir)
                try:
                    st.reload_db()
                except Exception:
                    pass
            except Exception as export_err:
                return jsonify({
                    "concept_id": concept_id,
                    "name": name,
                    "warning": f"Concept stored but artifact export failed: {export_err}",
                }), 201

        return jsonify({"concept_id": concept_id, "name": name, "status": "created"}), 201

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@st.app.route("/api/manual/edge", methods=["POST", "OPTIONS"])
@require_librarian
def manual_add_edge():
    """Librarian-only: add a directed relationship between two existing concept nodes.

    Expected JSON body::

        {
          "from_concept": "Retrieval-Augmented Generation",  # required
          "to_concept":   "Agentic System",                  # required
          "relation":     "enables"                          # required
        }

    ``relation`` must be one of: requires | enables | uses | extends |
    part_of | contrasts_with | evaluated_by
    """
    if request.method == "OPTIONS":
        return "", 204

    VALID_RELATIONS = {
        "requires", "enables", "uses", "extends",
        "part_of", "contrasts_with", "evaluated_by",
    }

    data         = request.get_json(force=True, silent=True) or {}
    from_concept = (data.get("from_concept") or "").strip()
    to_concept   = (data.get("to_concept") or "").strip()
    relation     = (data.get("relation") or "").strip().lower()

    if not from_concept:
        return jsonify({"error": "Field 'from_concept' is required."}), 400
    if not to_concept:
        return jsonify({"error": "Field 'to_concept' is required."}), 400
    if relation not in VALID_RELATIONS:
        return jsonify({"error": f"'relation' must be one of: {sorted(VALID_RELATIONS)}"}), 400

    def _id(name: str) -> str:
        return name.lower().replace(" ", "_").replace("-", "_")

    from_id = _id(from_concept)
    to_id   = _id(to_concept)

    try:
        from okf.graph.ingest import create_edge
        from okf.util import create_concept_id
        from okf.graph.export import export_graph
        from okf.exports import write_all_artifacts as _waa

        # Prefer canonical IDs when names differ from slug form
        from_id = create_concept_id(from_concept) or from_id
        to_id = create_concept_id(to_concept) or to_id

        with graph_lock.write_lock():
            conn = kuzu.Connection(st.db)

            # Verify both concepts exist (by id, then fuzzy name)
            for cid, label in [(from_id, from_concept), (to_id, to_concept)]:
                safe = cid.replace("'", "\\'")
                res = conn.execute(
                    f"MATCH (c:Concept {{id: '{safe}'}}) RETURN c.id LIMIT 1"
                )
                if not res.has_next():
                    # try match by name
                    safe_name = label.replace("'", "\\'")
                    res2 = conn.execute(
                        f"MATCH (c:Concept) WHERE c.name = '{safe_name}' RETURN c.id LIMIT 1"
                    )
                    if not res2.has_next():
                        return jsonify({
                            "error": f"Concept not found: '{label}' (id: '{cid}'). Add it first."
                        }), 404
                    resolved = res2.get_next()[0]
                    if cid == from_id:
                        from_id = resolved
                    else:
                        to_id = resolved

            try:
                create_edge(conn, from_id, to_id, relation, source="manual:librarian")
            except ValueError as ve:
                return jsonify({"error": str(ve)}), 409

            try:
                from okf.exports import build_visual_graph, build_graph_rag_index
                base_dir = Path(st.BASE_DIR)
                graph_export = export_graph(conn)
                graph_export["visualization"] = build_visual_graph([], graph_export)
                graph_export["graph_rag_index"] = build_graph_rag_index([], graph_export)
                _waa(graph_export, [], st.db, base_dir=base_dir)
                try:
                    st.reload_db()
                except Exception:
                    pass
            except Exception as export_err:
                return jsonify({
                    "from": from_concept, "to": to_concept, "relation": relation,
                    "warning": f"Edge stored but artifact export failed: {export_err}",
                }), 201

        return jsonify({
            "from": from_concept, "to": to_concept,
            "relation": relation, "status": "created",
        }), 201

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
