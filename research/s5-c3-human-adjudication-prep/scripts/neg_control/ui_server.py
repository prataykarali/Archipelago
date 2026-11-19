"""Strictly 127.0.0.1-only offline local HTTP server for negative-control verification."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from .constants import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_UI_PORT,
    LOCALHOST_BIND,
    MAX_HTTP_BODY_BYTES,
    SEARCH_MODE_SUBSTRING,
)
from .corpus import CorpusEligibilityError, CorpusIndex
from .schema import (
    add_evidence_citation,
    export_markdown_report,
    record_search_log,
    save_worksheet,
)
from .ui_html import UI_HTML_TEMPLATE
from .validator import validate_worksheet


class NegativeControlAppState:
    """Thread-safe state container for the offline local negative-control UI."""

    def __init__(
        self,
        *,
        corpus: CorpusIndex,
        worksheet: dict[str, Any],
        worksheet_path: Path,
        backup_dir: Path | None = None,
        export_md_path: Path | None = None,
    ) -> None:
        self.corpus = corpus
        self.worksheet = worksheet
        self.worksheet_path = worksheet_path
        self.backup_dir = backup_dir
        self.export_md_path = (
            export_md_path
            if export_md_path is not None
            else worksheet_path.with_name(f"{worksheet_path.stem}_EXPORT.md")
        )
        self.lock = threading.Lock()


def _make_handler(app_state: NegativeControlAppState) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to app_state."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return None

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, html: str) -> None:
            raw = html.encode("utf-8")
            self.send_response(int(HTTPStatus.OK))
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read_json_body(self) -> dict[str, Any]:
            content_len = int(self.headers.get("Content-Length", "0"))
            if content_len <= 0 or content_len > MAX_HTTP_BODY_BYTES:
                raise ValueError(f"Invalid request body size: {content_len}")
            raw = self.rfile.read(content_len)
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("JSON body must be an object.")
            return parsed

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if parsed.path == "/":
                self._send_html(UI_HTML_TEMPLATE)
                return

            if parsed.path == "/api/state":
                with app_state.lock:
                    expected_qids = app_state.worksheet.get("expected_query_ids") or [
                        q["query_id"] for q in app_state.worksheet.get("queries", [])
                    ]
                    report = validate_worksheet(
                        app_state.worksheet,
                        app_state.corpus,
                        expected_query_ids=expected_qids,
                    )
                    self._send_json(
                        {
                            "worksheet": app_state.worksheet,
                            "documents": app_state.corpus.list_documents(),
                            "validation": report.to_dict(),
                        }
                    )
                return

            if parsed.path == "/api/documents":
                self._send_json({"documents": app_state.corpus.list_documents()})
                return

            if parsed.path == "/api/document":
                doc_id = (params.get("doc_id") or [""])[0]
                try:
                    passages = app_state.corpus.get_document_passages(doc_id)
                except CorpusEligibilityError as exc:
                    self._send_json({"error": str(exc), "status": exc.status}, HTTPStatus.FORBIDDEN)
                    return
                self._send_json({"passages": [p.to_metadata_dict() for p in passages]})
                return

            if parsed.path == "/api/passage":
                passage_id = (params.get("passage_id") or [""])[0]
                try:
                    passage = app_state.corpus.inspect_passage(passage_id)
                except CorpusEligibilityError as exc:
                    self._send_json({"error": str(exc), "status": exc.status}, HTTPStatus.FORBIDDEN)
                    return
                self._send_json({"passage": passage.to_metadata_dict()})
                return

            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                body = self._read_json_body()
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            if parsed.path == "/api/search":
                try:
                    result = app_state.corpus.search(
                        str(body.get("query") or ""),
                        mode=str(body.get("mode") or SEARCH_MODE_SUBSTRING),
                        doc_id=body.get("doc_id") or None,
                        limit=int(body.get("limit") or DEFAULT_SEARCH_LIMIT),
                    )
                    query_id = body.get("query_id")
                    if query_id:
                        with app_state.lock:
                            record_search_log(app_state.worksheet, str(query_id), result)
                except CorpusEligibilityError as exc:
                    self._send_json({"error": str(exc), "status": exc.status}, HTTPStatus.FORBIDDEN)
                    return
                except (ValueError, KeyError) as exc:
                    self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                    return
                self._send_json({"result": result.to_dict()})
                return

            if parsed.path == "/api/evidence":
                try:
                    with app_state.lock:
                        citation = add_evidence_citation(
                            app_state.worksheet,
                            app_state.corpus,
                            query_id=str(body.get("query_id") or ""),
                            passage_id=str(body.get("passage_id") or ""),
                            verbatim_excerpt=str(body.get("verbatim_excerpt") or ""),
                            search_query_used=str(body.get("search_query_used") or ""),
                            note=str(body.get("note") or ""),
                        )
                        self._send_json({"citation": citation, "worksheet": app_state.worksheet})
                except CorpusEligibilityError as exc:
                    self._send_json({"error": str(exc), "status": exc.status}, HTTPStatus.FORBIDDEN)
                except (ValueError, KeyError) as exc:
                    self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            if parsed.path == "/api/validate":
                ws = body.get("worksheet")
                if not isinstance(ws, dict):
                    self._send_json({"error": "Missing worksheet object."}, HTTPStatus.BAD_REQUEST)
                    return
                expected_qids = ws.get("expected_query_ids") or [
                    q["query_id"] for q in ws.get("queries", [])
                ]
                report = validate_worksheet(ws, app_state.corpus, expected_query_ids=expected_qids)
                self._send_json({"validation": report.to_dict()})
                return

            if parsed.path == "/api/save":
                ws = body.get("worksheet")
                if not isinstance(ws, dict):
                    self._send_json({"error": "Missing worksheet object."}, HTTPStatus.BAD_REQUEST)
                    return
                with app_state.lock:
                    app_state.worksheet = ws
                    manifest = save_worksheet(
                        app_state.worksheet,
                        app_state.worksheet_path,
                        backup_dir=app_state.backup_dir,
                    )
                    expected_qids = app_state.worksheet.get("expected_query_ids") or [
                        q["query_id"] for q in app_state.worksheet.get("queries", [])
                    ]
                    report = validate_worksheet(
                        app_state.worksheet,
                        app_state.corpus,
                        expected_query_ids=expected_qids,
                    )
                    self._send_json(
                        {
                            "manifest": manifest,
                            "worksheet": app_state.worksheet,
                            "validation": report.to_dict(),
                        }
                    )
                return

            if parsed.path == "/api/export":
                ws = body.get("worksheet")
                if not isinstance(ws, dict):
                    self._send_json({"error": "Missing worksheet object."}, HTTPStatus.BAD_REQUEST)
                    return
                with app_state.lock:
                    app_state.worksheet = ws
                    save_worksheet(
                        app_state.worksheet,
                        app_state.worksheet_path,
                        backup_dir=app_state.backup_dir,
                    )
                    export_info = export_markdown_report(
                        app_state.worksheet,
                        app_state.export_md_path,
                    )
                    self._send_json({"export": export_info})
                return

            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    return Handler


def create_local_server(
    app_state: NegativeControlAppState,
    *,
    host: str = LOCALHOST_BIND,
    port: int = DEFAULT_UI_PORT,
) -> ThreadingHTTPServer:
    """Create a strictly 127.0.0.1-only ThreadingHTTPServer."""
    if host != LOCALHOST_BIND:
        raise ValueError(
            f"Refusing to bind negative-control UI to non-loopback host '{host}'. "
            f"Only '{LOCALHOST_BIND}' is permitted."
        )
    handler_cls = _make_handler(app_state)
    return ThreadingHTTPServer((LOCALHOST_BIND, port), handler_cls)
