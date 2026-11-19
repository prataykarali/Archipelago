#!/usr/bin/env python3
"""CLI entrypoint for the S5-C3 local-only human annotation workbench.

Subcommands:
    serve     Launch the strictly local (127.0.0.1) offline browser UI.
    status    Print overall and per-query completion counts + provenance status.
    validate  Validate a private annotation session against S5-C3 protocol rules.
    backup    Create a timestamped private backup + SHA-256 sidecar.
    export    Validate and export completed judgments to JSON, CSV, and SHA-256 manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from annotation_workbench import (  # noqa: E402
    ExportValidationError,
    assert_loopback_host,
    create_app,
    create_timestamped_backup,
    export_submission,
    load_blinded_pool,
    load_or_create_session,
    validate_session,
)
from annotation_workbench.constants import (  # noqa: E402
    ALLOWED_HOST,
    DEFAULT_BACKUP_DIR,
    DEFAULT_POOL_JSON,
    DEFAULT_PORT,
    DEFAULT_SESSION_FILE,
    DEFAULT_SUBMISSIONS_DIR,
)

EXIT_OK = 0
EXIT_VALIDATION_FAILED = 2


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Attach shared pool/session/private-path arguments to a subcommand."""
    parser.add_argument(
        "--pool",
        type=Path,
        default=DEFAULT_POOL_JSON,
        help="Path to frozen retrieval_query_pool_blinded.json",
    )
    parser.add_argument(
        "--passage-source",
        type=Path,
        default=None,
        help="Optional explicit read-only passage source (.md workbook, .json, or Kuzu DB)",
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=DEFAULT_SESSION_FILE,
        help="Private Git-ignored session JSON path",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help="Private Git-ignored directory for timestamped backups",
    )


def _cmd_serve(args: argparse.Namespace) -> int:
    """Start the local-only 127.0.0.1 Flask UI."""
    host = assert_loopback_host(args.host)
    pool = load_blinded_pool(
        pool_path=args.pool, passage_source=args.passage_source
    )
    app = create_app(
        pool=pool,
        session_path=args.session,
        backup_dir=args.backup_dir,
        submissions_dir=args.output_dir,
    )
    print(
        f"S5-C3 Local Human Annotation Workbench running at http://{host}:{args.port}/ "
        f"(pairs={len(pool.pairs)}, session={args.session})"
    )
    app.run(host=host, port=args.port, debug=False, use_reloader=False)
    return EXIT_OK


def _cmd_status(args: argparse.Namespace) -> int:
    """Print JSON summary of completion counts and provenance status."""
    pool = load_blinded_pool(
        pool_path=args.pool, passage_source=args.passage_source
    )
    session = load_or_create_session(pool, args.session)
    report = validate_session(pool, session, require_all_complete=False)
    summary = {
        "session_path": str(args.session),
        "pool_sha256": pool.pool_sha256,
        "total_pairs": report.total_pairs,
        "completed_pairs": report.completed_pairs,
        "graded_pairs": report.graded_pairs,
        "flagged_pairs": report.flagged_pairs,
        "invalid_pairs": report.invalid_pairs,
        "remaining_pairs": report.remaining_pairs,
        "provenance_valid": report.provenance_valid,
        "provenance_errors": list(report.provenance_errors),
        "review_completion_status": report.review_completion_status,
        "per_query": list(report.per_query),
    }
    print(json.dumps(summary, indent=2))
    return EXIT_OK


def _cmd_validate(args: argparse.Namespace) -> int:
    """Validate session judgments, verbatim quotes, passage hashes, and provenance."""
    pool = load_blinded_pool(
        pool_path=args.pool, passage_source=args.passage_source
    )
    session = load_or_create_session(pool, args.session)
    report = validate_session(
        pool, session, require_all_complete=not args.allow_partial
    )
    print(json.dumps(report.to_dict(), indent=2))
    return EXIT_OK if report.valid_for_export else EXIT_VALIDATION_FAILED


def _cmd_backup(args: argparse.Namespace) -> int:
    """Create a timestamped private backup and print its SHA-256."""
    pool = load_blinded_pool(
        pool_path=args.pool, passage_source=args.passage_source
    )
    session = load_or_create_session(pool, args.session)
    backup_path, digest = create_timestamped_backup(
        session, backup_dir=args.backup_dir, prefix=args.session.stem
    )
    print(
        json.dumps(
            {
                "backup_path": str(backup_path),
                "backup_sha256": digest,
            },
            indent=2,
        )
    )
    return EXIT_OK


def _cmd_export(args: argparse.Namespace) -> int:
    """Validate and export completed judgments to JSON, CSV, and SHA-256 manifest."""
    pool = load_blinded_pool(
        pool_path=args.pool, passage_source=args.passage_source
    )
    session = load_or_create_session(pool, args.session)
    try:
        result = export_submission(
            pool,
            session,
            output_dir=args.output_dir,
            backup_dir=args.backup_dir,
            filename_prefix=args.prefix,
            allow_partial=args.allow_partial,
        )
    except ExportValidationError as exc:
        print(
            json.dumps(
                {"error": str(exc), "validation": exc.report.to_dict()},
                indent=2,
            ),
            file=sys.stderr,
        )
        return EXIT_VALIDATION_FAILED

    print(
        json.dumps(
            {
                "json_path": str(result.json_path),
                "json_sha256": result.json_sha256,
                "csv_path": str(result.csv_path),
                "csv_sha256": result.csv_sha256,
                "manifest_path": str(result.manifest_path),
                "manifest_sha256": result.manifest_sha256,
                "backup_path": str(result.backup_path),
                "backup_sha256": result.backup_sha256,
                "exported_at_utc": result.exported_at_utc,
            },
            indent=2,
        )
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Archipelago S5-C3 Local-Only Human Annotation Workbench"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_serve = subparsers.add_parser("serve", help="Run local 127.0.0.1 browser UI")
    _add_common_args(p_serve)
    p_serve.add_argument(
        "--host",
        default=ALLOWED_HOST,
        help="Must be 127.0.0.1 (non-loopback hosts are rejected)",
    )
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local port")
    p_serve.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_SUBMISSIONS_DIR,
        help="Private Git-ignored directory for exported submissions",
    )
    p_serve.set_defaults(func=_cmd_serve)

    p_status = subparsers.add_parser("status", help="Show completion and provenance status")
    _add_common_args(p_status)
    p_status.set_defaults(func=_cmd_status)

    p_validate = subparsers.add_parser("validate", help="Validate session against S5-C3 rules")
    _add_common_args(p_validate)
    p_validate.add_argument(
        "--allow-partial",
        action="store_true",
        help="Validate started pairs and provenance without requiring all 254 pairs",
    )
    p_validate.set_defaults(func=_cmd_validate)

    p_backup = subparsers.add_parser("backup", help="Create timestamped private backup")
    _add_common_args(p_backup)
    p_backup.set_defaults(func=_cmd_backup)

    p_export = subparsers.add_parser("export", help="Validate and export JSON/CSV + SHA-256")
    _add_common_args(p_export)
    p_export.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_SUBMISSIONS_DIR,
        help="Private Git-ignored directory for exported submissions",
    )
    p_export.add_argument(
        "--prefix",
        default=None,
        help="Optional filename prefix for exported files",
    )
    p_export.add_argument(
        "--allow-partial",
        action="store_true",
        help="Export started valid pairs as IN_PROGRESS (still requires signed provenance)",
    )
    p_export.set_defaults(func=_cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI main entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
