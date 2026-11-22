"""Local-only (127.0.0.1) HTTP server for S5-v3.1 blinded human annotation."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .constants import DEFAULT_BIND_HOST, DEFAULT_BIND_PORT, LOOPBACK_HOSTS
from .store import AnnotationSession

_MINIMAL_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>S5-v3.1 Blinded Annotation Workbench</title></head>
<body>
<h1>S5-v3.1 Blinded Human Annotation Workbench (Local Only)</h1>
<p>Strictly blinded: zero system IDs, ranks, scores, or AI hints.</p>
<p>Use <code>GET /api/state</code>, <code>POST /api/judge</code>, and
<code>POST /api/sign</code>.</p>
</body>
</html>
"""


def _make_handler(session: AnnotationSession) -> type[BaseHTTPRequestHandler]:
    class WorkbenchHandler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/":
                body = _MINIMAL_HTML.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/api/state":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "pool_id": session.pool["pool_id"],
                        "assigned_pair_count": len(session.assigned_pairs),
                        "judged_count": len(session.state["judgments"]),
                        "reviewer_provenance": session.state[
                            "reviewer_provenance"
                        ],
                    },
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad_json"})
                return

            if self.path == "/api/judge":
                try:
                    entry = session.record_judgment(
                        pair_id=str(body["pair_id"]),
                        grade=int(body["grade"]),
                        supporting_quotation=str(
                            body.get("supporting_quotation", "")
                        ),
                        notes=str(body.get("notes", "")),
                    )
                except (KeyError, ValueError) as exc:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST, {"error": str(exc)}
                    )
                    return
                self._send_json(HTTPStatus.OK, {"recorded": entry})
                return

            if self.path == "/api/sign":
                try:
                    digest = session.sign_and_finalize(
                        attestation_signer=str(body["attestation_signer"]),
                        prior_exposure_disclosure=str(
                            body["prior_exposure_disclosure"]
                        ),
                    )
                except (KeyError, ValueError) as exc:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST, {"error": str(exc)}
                    )
                    return
                self._send_json(
                    HTTPStatus.OK, {"signed": True, "submission_sha256": digest}
                )
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    return WorkbenchHandler


def create_local_server(
    session: AnnotationSession,
    host: str = DEFAULT_BIND_HOST,
    port: int = DEFAULT_BIND_PORT,
) -> ThreadingHTTPServer:
    """Create a strictly loopback-only HTTP server for local annotation."""
    if host not in LOOPBACK_HOSTS:
        msg = (
            f"Refusing to bind non-loopback host '{host}'; "
            f"allowed: {sorted(LOOPBACK_HOSTS)}."
        )
        raise ValueError(msg)
    return ThreadingHTTPServer((host, port), _make_handler(session))
