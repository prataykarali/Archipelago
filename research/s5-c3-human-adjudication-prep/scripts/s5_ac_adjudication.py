"""CLI entrypoint for S5-C3 Independent A/C Comparison and Human Adjudication.

Supports:
- `validate-submission`: Validate a complete REV_A or REV_C submission against the frozen pool.
- `compare`: Validate BOTH REV_A and REV_C, compute inter-human agreement, and emit a blank
  structured human adjudication worksheet (refuses if either reviewer is missing/invalid).
- `validate-adjudication`: Validate a completed human adjudication worksheet for every A/C disagreement.
- `assemble-gold`: Assemble final `s5d1_adjudicated_gold_ac_v2` JSON ONLY when all checks pass
  and explicit human adjudication + negative-control + investigator sign-off are supplied.
- `validate-gold`: Validate an A/C v2 gold-label JSON file against schema and semantic gates.
- `serve-ui`: Launch the offline local `127.0.0.1`-only human adjudication browser UI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ac_adjudication.comparison import (  # noqa: E402
    assemble_gold_v2,
    build_blank_adjudication_worksheet,
    render_adjudication_worksheet_markdown,
)
from ac_adjudication.constants import (  # noqa: E402
    DEFAULT_AC_V2_SCHEMA,
    DEFAULT_FROZEN_POOL,
    DEFAULT_UI_PORT,
    LOOPBACK_HOST,
    ROLE_REV_A,
    ROLE_REV_C,
)
from ac_adjudication.pool_index import load_frozen_pool, sha256_bytes, sha256_file  # noqa: E402
from ac_adjudication.server import run_local_adjudication_server  # noqa: E402
from ac_adjudication.validation import (  # noqa: E402
    ACValidationError,
    validate_adjudication_worksheet,
    validate_gold_v2_payload,
    validate_reviewer_submission,
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ACValidationError(f"Required input file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_with_sha(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    digest = sha256_bytes(rendered)
    path.write_bytes(rendered)
    sha_path = path.with_suffix(path.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def _cmd_validate_submission(args: argparse.Namespace) -> int:
    pool = load_frozen_pool(args.pool)
    payload = _read_json(args.submission)
    indexed = validate_reviewer_submission(payload, pool, expected_role=args.role)
    print(
        json.dumps(
            {
                "status": "OK",
                "reviewer_role": args.role,
                "validated_pairs": len(indexed),
                "submission_sha256": sha256_file(args.submission),
            },
            indent=2,
        )
    )
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    pool = load_frozen_pool(args.pool)
    rev_a_payload = _read_json(args.rev_a)
    rev_c_payload = _read_json(args.rev_c)
    worksheet = build_blank_adjudication_worksheet(
        rev_a_payload,
        rev_c_payload,
        pool,
        rev_a_sha256=sha256_file(args.rev_a),
        rev_c_sha256=sha256_file(args.rev_c),
    )
    digest = _write_json_with_sha(args.output_worksheet, worksheet)
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(
            render_adjudication_worksheet_markdown(worksheet),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": "OK",
                "worksheet_path": str(args.output_worksheet),
                "worksheet_sha256": digest,
                "disagreements_count": worksheet["disagreements_count"],
                "inter_annotator_agreement": worksheet["inter_annotator_agreement"],
            },
            indent=2,
        )
    )
    return 0


def _cmd_validate_adjudication(args: argparse.Namespace) -> int:
    pool = load_frozen_pool(args.pool)
    rev_a = validate_reviewer_submission(_read_json(args.rev_a), pool, expected_role=ROLE_REV_A)
    rev_c = validate_reviewer_submission(_read_json(args.rev_c), pool, expected_role=ROLE_REV_C)
    expected_pairs = [
        pid
        for pid in pool.ordered_pair_ids
        if int(rev_a[pid]["relevance_grade"]) != int(rev_c[pid]["relevance_grade"])
    ]
    resolved = validate_adjudication_worksheet(_read_json(args.worksheet), expected_pairs, pool)
    print(
        json.dumps(
            {
                "status": "OK",
                "validated_disagreements": len(resolved),
                "worksheet_sha256": sha256_file(args.worksheet),
            },
            indent=2,
        )
    )
    return 0


def _cmd_assemble_gold(args: argparse.Namespace) -> int:
    pool = load_frozen_pool(args.pool)
    gold = assemble_gold_v2(
        rev_a_payload=_read_json(args.rev_a),
        rev_c_payload=_read_json(args.rev_c),
        worksheet_payload=_read_json(args.worksheet),
        neg_controls_payload=_read_json(args.neg_controls),
        investigator_signoff_payload=_read_json(args.investigator_signoff),
        pool=pool,
        rev_a_sha256=sha256_file(args.rev_a),
        rev_c_sha256=sha256_file(args.rev_c),
        worksheet_sha256=sha256_file(args.worksheet),
        schema_path=args.schema,
    )
    digest = _write_json_with_sha(args.output, gold)
    print(
        json.dumps(
            {
                "status": "OK",
                "gold_output_path": str(args.output),
                "gold_sha256": digest,
                "schema_version": gold["schema_version"],
                "judgments_count": len(gold["judgments"]),
            },
            indent=2,
        )
    )
    return 0


def _cmd_validate_gold(args: argparse.Namespace) -> int:
    pool = load_frozen_pool(args.pool)
    payload = _read_json(args.gold)
    validate_gold_v2_payload(payload, pool, schema_path=args.schema)
    print(
        json.dumps(
            {
                "status": "OK",
                "schema_version": payload["schema_version"],
                "gold_sha256": sha256_file(args.gold),
                "judgments_count": len(payload["judgments"]),
            },
            indent=2,
        )
    )
    return 0


def _cmd_serve_ui(args: argparse.Namespace) -> int:
    if not args.worksheet.exists():
        raise ACValidationError(f"Adjudication worksheet not found: {args.worksheet}")
    pool = load_frozen_pool(args.pool)
    run_local_adjudication_server(args.worksheet, pool, host=LOOPBACK_HOST, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for S5-C3 A/C comparison and adjudication."""
    parser = argparse.ArgumentParser(
        description="S5-C3 Independent A/C Comparison, Human Adjudication, and Gold v2 Assembly."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_val_sub = sub.add_parser("validate-submission", help="Validate REV_A or REV_C submission.")
    p_val_sub.add_argument("--submission", type=Path, required=True)
    p_val_sub.add_argument("--role", choices=[ROLE_REV_A, ROLE_REV_C], required=True)
    p_val_sub.add_argument("--pool", type=Path, default=DEFAULT_FROZEN_POOL)
    p_val_sub.set_defaults(func=_cmd_validate_submission)

    p_cmp = sub.add_parser("compare", help="Compare REV_A vs REV_C and emit blank worksheet.")
    p_cmp.add_argument("--rev-a", type=Path, required=True)
    p_cmp.add_argument("--rev-c", type=Path, required=True)
    p_cmp.add_argument("--output-worksheet", type=Path, required=True)
    p_cmp.add_argument("--output-markdown", type=Path, default=None)
    p_cmp.add_argument("--pool", type=Path, default=DEFAULT_FROZEN_POOL)
    p_cmp.set_defaults(func=_cmd_compare)

    p_val_adj = sub.add_parser("validate-adjudication", help="Validate completed A/C worksheet.")
    p_val_adj.add_argument("--worksheet", type=Path, required=True)
    p_val_adj.add_argument("--rev-a", type=Path, required=True)
    p_val_adj.add_argument("--rev-c", type=Path, required=True)
    p_val_adj.add_argument("--pool", type=Path, default=DEFAULT_FROZEN_POOL)
    p_val_adj.set_defaults(func=_cmd_validate_adjudication)

    p_asm = sub.add_parser("assemble-gold", help="Assemble validated A/C v2 gold JSON.")
    p_asm.add_argument("--rev-a", type=Path, required=True)
    p_asm.add_argument("--rev-c", type=Path, required=True)
    p_asm.add_argument("--worksheet", type=Path, required=True)
    p_asm.add_argument("--neg-controls", type=Path, required=True)
    p_asm.add_argument("--investigator-signoff", type=Path, required=True)
    p_asm.add_argument("--output", type=Path, required=True)
    p_asm.add_argument("--pool", type=Path, default=DEFAULT_FROZEN_POOL)
    p_asm.add_argument("--schema", type=Path, default=DEFAULT_AC_V2_SCHEMA)
    p_asm.set_defaults(func=_cmd_assemble_gold)

    p_val_gold = sub.add_parser("validate-gold", help="Validate an A/C v2 gold JSON file.")
    p_val_gold.add_argument("--gold", type=Path, required=True)
    p_val_gold.add_argument("--pool", type=Path, default=DEFAULT_FROZEN_POOL)
    p_val_gold.add_argument("--schema", type=Path, default=DEFAULT_AC_V2_SCHEMA)
    p_val_gold.set_defaults(func=_cmd_validate_gold)

    p_ui = sub.add_parser("serve-ui", help="Start offline 127.0.0.1-only human adjudication UI.")
    p_ui.add_argument("--worksheet", type=Path, required=True)
    p_ui.add_argument("--pool", type=Path, default=DEFAULT_FROZEN_POOL)
    p_ui.add_argument("--port", type=int, default=DEFAULT_UI_PORT)
    p_ui.set_defaults(func=_cmd_serve_ui)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint returning exit code 0 on success and 2 on validation errors."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ACValidationError as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
