#!/usr/bin/env python3
"""CLI entrypoint for S5-C3 Negative-Control Human Verification (Module 4).

Strictly restricted to the frozen eligible corpus (`s5a_eval_corpus_v1`).
NEVER auto-classifies answerability or auto-signs human provenance attestations.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]
for _p in (str(_SCRIPT_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from neg_control.constants import (  # noqa: E402
    DEFAULT_AUDIT_JSON,
    DEFAULT_BACKUP_DIR,
    DEFAULT_CORPUS_MANIFEST_JSON,
    DEFAULT_DB_PATH,
    DEFAULT_EXPORT_MD_PATH,
    DEFAULT_PROVENANCE_REGISTRY_JSON,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_UI_PORT,
    DEFAULT_WORKSHEET_PATH,
    LOCALHOST_BIND,
    NEGATIVE_CONTROL_QUERY_IDS,
    SEARCH_MODE_SUBSTRING,
    VALID_SEARCH_MODES,
)
from neg_control.corpus import CorpusEligibilityError, CorpusIndex  # noqa: E402
from neg_control.schema import (  # noqa: E402
    create_blank_worksheet,
    export_markdown_report,
    load_worksheet,
    record_search_log,
    save_worksheet,
)
from neg_control.ui_server import NegativeControlAppState, create_local_server  # noqa: E402
from neg_control.validator import validate_worksheet  # noqa: E402


def _add_corpus_args(parser: argparse.ArgumentParser) -> None:
    """Attach shared frozen-corpus loading arguments to a subparser."""
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to canonical Kuzu okf_graph.db (used when --corpus-json is omitted).",
    )
    parser.add_argument(
        "--corpus-json",
        type=Path,
        default=None,
        help="Path to a frozen corpus JSON snapshot or synthetic fixture.",
    )
    parser.add_argument(
        "--manifest-json",
        type=Path,
        default=DEFAULT_CORPUS_MANIFEST_JSON,
        help="Path to frozen corpus manifest JSON (documents allowlist).",
    )
    parser.add_argument(
        "--no-manifest-filter",
        action="store_true",
        help="Disable manifest document allowlist (for synthetic fixtures).",
    )
    parser.add_argument(
        "--provenance-registry",
        type=Path,
        default=DEFAULT_PROVENANCE_REGISTRY_JSON,
        help="Path to s5b2_1_corpus_provenance_registry.json.",
    )
    parser.add_argument(
        "--skip-frozen-hash-check",
        action="store_true",
        help="Skip canonical 713-passage SHA-256 check (for synthetic fixtures only).",
    )


def _load_corpus(args: argparse.Namespace) -> CorpusIndex:
    """Load CorpusIndex from --corpus-json or Kuzu --db-path."""
    manifest_path = None if args.no_manifest_filter else args.manifest_json
    prov_path = args.provenance_registry if args.provenance_registry.exists() else None

    if args.corpus_json is not None:
        return CorpusIndex.from_json(
            args.corpus_json,
            manifest_path=manifest_path,
            provenance_registry_path=prov_path,
        )
    return CorpusIndex.from_kuzu(
        args.db_path,
        manifest_path=manifest_path,
        provenance_registry_path=prov_path,
        verify_frozen_hash=not args.skip_frozen_hash_check,
    )


def _cmd_init(args: argparse.Namespace) -> int:
    corpus = _load_corpus(args)
    audit_data: dict[str, Any] | None = None
    if args.audit_json is not None and args.audit_json.exists():
        audit_data = json.loads(args.audit_json.read_text(encoding="utf-8"))
    worksheet = create_blank_worksheet(
        corpus,
        audit_data=audit_data,
        is_synthetic=bool(args.synthetic),
    )
    manifest = save_worksheet(worksheet, args.output, backup_dir=args.backup_dir)
    print(json.dumps(manifest, indent=2))
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    corpus = _load_corpus(args)
    result = corpus.search(
        args.query,
        mode=args.mode,
        doc_id=args.doc_id,
        limit=args.limit,
    )
    if args.worksheet is not None and args.query_id is not None:
        ws = load_worksheet(args.worksheet)
        record_search_log(ws, args.query_id, result)
        save_worksheet(ws, args.worksheet, backup_dir=args.backup_dir)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    corpus = _load_corpus(args)
    if args.list_docs:
        print(
            json.dumps(
                {
                    "corpus_version": corpus.corpus_version,
                    "corpus_sha256": corpus.corpus_sha256,
                    "document_count": corpus.document_count,
                    "passage_count": corpus.passage_count,
                    "documents": corpus.list_documents(),
                },
                indent=2,
            )
        )
        return 0

    if args.doc_id:
        passages = corpus.get_document_passages(args.doc_id)
        print(
            json.dumps(
                {
                    "doc_id": args.doc_id,
                    "passage_count": len(passages),
                    "passages": [p.to_metadata_dict() for p in passages],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.passage_id:
        passage = corpus.inspect_passage(args.passage_id)
        print(json.dumps(passage.to_metadata_dict(), indent=2, ensure_ascii=False))
        return 0

    raise ValueError("Provide --list-docs, --doc-id, or --passage-id.")


def _cmd_validate(args: argparse.Namespace) -> int:
    corpus = _load_corpus(args)
    worksheet = load_worksheet(args.worksheet)
    expected_qids: Sequence[str] = (
        tuple(args.expected_query_id)
        if args.expected_query_id
        else tuple(worksheet.get("expected_query_ids") or NEGATIVE_CONTROL_QUERY_IDS)
    )
    report = validate_worksheet(worksheet, corpus, expected_query_ids=expected_qids)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.valid else 1


def _cmd_export(args: argparse.Namespace) -> int:
    corpus = _load_corpus(args)
    worksheet = load_worksheet(args.worksheet)
    manifest = save_worksheet(worksheet, args.worksheet, backup_dir=args.backup_dir)
    export_info = export_markdown_report(worksheet, args.output_md)
    report = validate_worksheet(
        worksheet,
        corpus,
        expected_query_ids=tuple(worksheet.get("expected_query_ids") or NEGATIVE_CONTROL_QUERY_IDS),
    )
    print(
        json.dumps(
            {
                "save_manifest": manifest,
                "markdown_export": export_info,
                "validation_valid": report.valid,
                "ready_for_d1": report.ready_for_d1,
            },
            indent=2,
        )
    )
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    corpus = _load_corpus(args)
    if args.worksheet.exists():
        worksheet = load_worksheet(args.worksheet)
    else:
        audit_data: dict[str, Any] | None = None
        if args.audit_json is not None and args.audit_json.exists():
            audit_data = json.loads(args.audit_json.read_text(encoding="utf-8"))
        worksheet = create_blank_worksheet(
            corpus,
            audit_data=audit_data,
            is_synthetic=bool(args.synthetic),
        )
        save_worksheet(worksheet, args.worksheet, backup_dir=args.backup_dir)

    state = NegativeControlAppState(
        corpus=corpus,
        worksheet=worksheet,
        worksheet_path=args.worksheet,
        backup_dir=args.backup_dir,
        export_md_path=args.output_md,
    )
    server = create_local_server(state, host=args.host, port=args.port)
    print(
        f"S5-C3 Negative-Control Verification UI listening on http://{args.host}:{args.port}/ "
        f"(offline 127.0.0.1 only; worksheet: {args.worksheet})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down local verification server.")
    finally:
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "S5-C3 Negative-Control Human Verification CLI & Offline 127.0.0.1 UI "
            "(strictly restricted to frozen eligible corpus)."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize a blank private verification worksheet.")
    _add_corpus_args(p_init)
    p_init.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    p_init.add_argument("--output", type=Path, default=DEFAULT_WORKSHEET_PATH)
    p_init.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    p_init.add_argument("--synthetic", action="store_true", help="Mark worksheet as SYNTHETIC.")
    p_init.set_defaults(func=_cmd_init)

    p_search = sub.add_parser("search", help="Search strictly within the frozen eligible corpus.")
    _add_corpus_args(p_search)
    p_search.add_argument("--query", required=True, help="Search string / tokens / regex.")
    p_search.add_argument(
        "--mode",
        default=SEARCH_MODE_SUBSTRING,
        choices=sorted(VALID_SEARCH_MODES),
    )
    p_search.add_argument("--doc-id", default=None, help="Optional eligible doc_id filter.")
    p_search.add_argument("--limit", type=int, default=DEFAULT_SEARCH_LIMIT)
    p_search.add_argument("--worksheet", type=Path, default=None)
    p_search.add_argument("--query-id", default=None)
    p_search.add_argument("--backup-dir", type=Path, default=None)
    p_search.set_defaults(func=_cmd_search)

    p_inspect = sub.add_parser("inspect", help="Inspect eligible corpus documents or passages.")
    _add_corpus_args(p_inspect)
    p_inspect.add_argument("--list-docs", action="store_true")
    p_inspect.add_argument("--doc-id", default=None)
    p_inspect.add_argument("--passage-id", default=None)
    p_inspect.set_defaults(func=_cmd_inspect)

    p_val = sub.add_parser("validate", help="Validate a verification worksheet JSON.")
    _add_corpus_args(p_val)
    p_val.add_argument("--worksheet", type=Path, required=True)
    p_val.add_argument("--expected-query-id", action="append", default=[])
    p_val.set_defaults(func=_cmd_validate)

    p_exp = sub.add_parser("export", help="Backup, hash, and export worksheet to Markdown.")
    _add_corpus_args(p_exp)
    p_exp.add_argument("--worksheet", type=Path, required=True)
    p_exp.add_argument("--output-md", type=Path, default=DEFAULT_EXPORT_MD_PATH)
    p_exp.add_argument("--backup-dir", type=Path, default=None)
    p_exp.set_defaults(func=_cmd_export)

    p_serve = sub.add_parser("serve", help="Launch offline 127.0.0.1-only local browser UI.")
    _add_corpus_args(p_serve)
    p_serve.add_argument("--worksheet", type=Path, default=DEFAULT_WORKSHEET_PATH)
    p_serve.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    p_serve.add_argument("--backup-dir", type=Path, default=None)
    p_serve.add_argument("--output-md", type=Path, default=DEFAULT_EXPORT_MD_PATH)
    p_serve.add_argument("--host", default=LOCALHOST_BIND)
    p_serve.add_argument("--port", type=int, default=DEFAULT_UI_PORT)
    p_serve.add_argument("--synthetic", action="store_true")
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the S5-C3 negative-control verifier CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (CorpusEligibilityError, FileNotFoundError, ValueError, KeyError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
