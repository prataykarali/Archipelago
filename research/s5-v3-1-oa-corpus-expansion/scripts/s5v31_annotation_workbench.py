"""CLI for the S5-v3.1 versioned blinded human annotation workbench."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from annotation_v31.constants import (
    DEFAULT_BIND_HOST,
    DEFAULT_BIND_PORT,
    DEFAULT_CORPUS_V31_JSONL,
    DOMAIN_GROUP_ALL,
)
from annotation_v31.server import create_local_server
from annotation_v31.store import (
    AnnotationSession,
    load_blinded_pool,
    load_corpus_passages,
    validate_human_submission,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="S5-v3.1 blinded human annotation workbench CLI."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd in ("init", "status", "judge", "sign", "validate", "serve"):
        p = sub.add_parser(cmd)
        p.add_argument("--pool", type=Path, required=True)
        p.add_argument(
            "--corpus", type=Path, default=Path(DEFAULT_CORPUS_V31_JSONL)
        )
        p.add_argument("--submission", type=Path, required=True)
        if cmd in ("init", "status", "judge", "sign", "serve"):
            p.add_argument("--reviewer-id", type=str, required=True)
            p.add_argument(
                "--domain-group", type=str, default=DOMAIN_GROUP_ALL
            )
        if cmd == "judge":
            p.add_argument("--pair-id", type=str, required=True)
            p.add_argument("--grade", type=int, required=True)
            p.add_argument("--quotation", type=str, default="")
            p.add_argument("--notes", type=str, default="")
        if cmd == "sign":
            p.add_argument("--signer", type=str, required=True)
            p.add_argument("--prior-exposure", type=str, default="NONE")
        if cmd == "serve":
            p.add_argument("--host", type=str, default=DEFAULT_BIND_HOST)
            p.add_argument("--port", type=int, default=DEFAULT_BIND_PORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run S5-v3.1 annotation workbench CLI command."""
    args = _parse_args(argv)

    if args.command == "validate":
        pool = load_blinded_pool(args.pool)
        corpus = load_corpus_passages(args.corpus)
        sub = json.loads(args.submission.read_text(encoding="utf-8"))
        errors = validate_human_submission(sub, pool, corpus)
        print(
            json.dumps(
                {"valid": len(errors) == 0, "error_count": len(errors), "errors": errors},
                indent=2,
            )
        )
        return 0 if not errors else 1

    session = AnnotationSession(
        pool_path=args.pool,
        corpus_jsonl=args.corpus,
        submission_path=args.submission,
        reviewer_id=args.reviewer_id,
        domain_group=args.domain_group,
    )

    if args.command in ("init", "status"):
        print(
            json.dumps(
                {
                    "pool_id": session.pool["pool_id"],
                    "assigned_pairs": len(session.assigned_pairs),
                    "judged_pairs": len(session.state["judgments"]),
                    "signed": session.state["reviewer_provenance"][
                        "human_attestation_signed"
                    ],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "judge":
        entry = session.record_judgment(
            pair_id=args.pair_id,
            grade=args.grade,
            supporting_quotation=args.quotation,
            notes=args.notes,
        )
        print(json.dumps({"recorded": entry}, indent=2))
        return 0

    if args.command == "sign":
        digest = session.sign_and_finalize(
            attestation_signer=args.signer,
            prior_exposure_disclosure=args.prior_exposure,
        )
        print(json.dumps({"signed": True, "submission_sha256": digest}, indent=2))
        return 0

    server = create_local_server(session, host=args.host, port=args.port)
    print(f"Serving S5-v3.1 workbench on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
