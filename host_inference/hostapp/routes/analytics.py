"""S6 Library Analytics, Librarian Workspace, and S4 Review Compatibility Routes."""

from __future__ import annotations

from functools import lru_cache
import os
import time
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from flask.typing import ResponseReturnValue
import requests

from archipelago.scholarly.intelligence.analytics import (
    audit_sources,
    build_analytics_summary,
    fetch_events,
    record_event,
)
from archipelago.scholarly.intelligence.storage import hosted_store

from ..config import ELEVATED_ROLES, LIBRARIAN_ROLES, UI
from ..context import AppContext
from ..koha_bridge import load_koha_snapshot

BUCKET = "archipelago-cache"
S4_SNAPSHOT_OBJECT = "s4_academic_automation_snapshot.json"
RECORDS_PATH = "/rest/v1/archipelago_librarian_records"
RECORD_TYPES = frozenset({"catalog", "circulation", "orders", "fines"})
STORE_TIMEOUT_SECONDS = 12
CACHE_BUCKET_SECONDS = 120
MAX_TEXT_LENGTH = 2000
MAX_KEY_LENGTH = 120
MAX_QUANTITY = 1_000_000
MAX_AMOUNT = 10_000_000
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_UNAVAILABLE = 503


def _supabase_conn() -> tuple[str, dict[str, str]] | None:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    ).strip()
    if not url or not key:
        return None
    return url, {"apikey": key, "Authorization": f"Bearer {key}"}


def _list_staff_records(record_type: str) -> list[dict[str, Any]]:
    conn = _supabase_conn()
    if not conn or record_type not in RECORD_TYPES:
        return []
    url, headers = conn
    try:
        resp = requests.get(
            url + RECORDS_PATH,
            params={
                "record_type": f"eq.{record_type}",
                "select": "*",
                "order": "updated_at.desc",
                "limit": "200",
            },
            headers=headers,
            timeout=STORE_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows if isinstance(rows, list) else []
    except (requests.RequestException, ValueError):
        return []


def _save_staff_record(record_type: str, data: object, actor: str) -> dict[str, Any]:
    if record_type not in RECORD_TYPES or not isinstance(data, dict):
        raise ValueError("invalid_record")
    key = data.get("record_key")
    if not isinstance(key, str) or not 1 <= len(key.strip()) <= MAX_KEY_LENGTH:
        raise ValueError("invalid_record_key")
    row: dict[str, Any] = {
        "record_type": record_type,
        "record_key": key.strip(),
        "updated_by": actor,
    }
    for field in ("title", "status", "shelf", "note", "source_url"):
        value = data.get(field, "")
        if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"invalid_{field}")
        row[field] = value.strip()
    if row["source_url"] and not str(row["source_url"]).startswith("https://"):
        raise ValueError("source_url_must_be_https")
    for field, limit in (("quantity", MAX_QUANTITY), ("amount", MAX_AMOUNT)):
        value = data.get(field)
        if value in (None, ""):
            row[field] = None
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= limit
        ):
            raise ValueError(f"invalid_{field}")
        else:
            row[field] = value
    conn = _supabase_conn()
    if not conn:
        raise RuntimeError("shared_storage_unconfigured")
    url, headers = conn
    resp = requests.post(
        url + RECORDS_PATH,
        params={"on_conflict": "record_type,record_key"},
        json=row,
        headers={**headers, "Prefer": "resolution=merge-duplicates,return=representation"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    saved = resp.json()[0]
    return dict(saved)


@lru_cache(maxsize=2)
def _load_s4_snapshot(_bucket: int) -> dict[str, Any] | None:
    conn = _supabase_conn()
    if not conn:
        return None
    url, headers = conn
    try:
        resp = requests.get(
            f"{url}/storage/v1/object/{BUCKET}/{S4_SNAPSHOT_OBJECT}",
            headers=headers,
            timeout=STORE_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except (requests.RequestException, ValueError):
        return None


def _all_staff_records() -> dict[str, list[dict[str, Any]]]:
    return {rtype: _list_staff_records(rtype) for rtype in RECORD_TYPES}


def register(app: Flask, ctx: AppContext) -> None:
    """Register S6 analytics, librarian workspace, and S4 review routes on ``app``."""

    def _require_role(
        roles: frozenset[str], reject_dev_token: bool = False
    ) -> tuple[dict[str, Any] | None, ResponseReturnValue | None]:
        principal = getattr(request, "archipelago_principal", None)
        if principal is None:
            principal, error = ctx.auth.principal()
            if principal is None or not principal.get("id"):
                return None, (
                    jsonify({"error": "unauthorized", "detail": error}),
                    HTTP_UNAUTHORIZED,
                )
        auth_header = request.headers.get("Authorization", "")
        if reject_dev_token and "local-dev-token" in auth_header:
            return None, (
                jsonify({"error": "forbidden", "detail": "Verified librarian session required"}),
                HTTP_FORBIDDEN,
            )
        if principal.get("role") not in roles:
            return None, (jsonify({"error": "forbidden"}), HTTP_FORBIDDEN)
        return principal, None

    @app.get("/analytics")
    @app.get("/librarian/analytics")
    def analytics_page() -> ResponseReturnValue:
        return send_from_directory(UI, "analytics.html")

    @app.get("/academic/graph")
    def academic_graph_page() -> ResponseReturnValue:
        return send_from_directory(UI, "academic_graph.html")

    @app.get("/academic-automation")
    @app.get("/academic-automation.html")
    def academic_automation_page() -> ResponseReturnValue:
        return send_from_directory(UI, "academic_automation.html")

    @app.get("/librarian")
    @app.get("/librarian/<section>")
    def librarian_workspace_page(section: str = "overview") -> ResponseReturnValue:
        if section == "analytics":
            return send_from_directory(UI, "analytics.html")
        if section not in {"overview", *RECORD_TYPES}:
            return jsonify({"error": "not_found"}), HTTP_NOT_FOUND
        return send_from_directory(UI, "librarian.html")

    @app.get("/api/library/koha")
    def library_koha_api() -> ResponseReturnValue:
        snapshot = load_koha_snapshot()
        if snapshot is None:
            return jsonify({"error": "export_not_available"}), HTTP_NOT_FOUND
        return jsonify(snapshot), HTTP_OK

    @app.route("/api/librarian/<record_type>", methods=["GET", "POST"])
    def librarian_records_api(record_type: str) -> ResponseReturnValue:
        if record_type not in RECORD_TYPES:
            return jsonify({"error": "not_found"}), HTTP_NOT_FOUND
        required = LIBRARIAN_ROLES if request.method == "POST" else ELEVATED_ROLES
        principal, err = _require_role(required)
        if err is not None or principal is None:
            return err  # type: ignore[return-value]
        if request.method == "GET":
            return jsonify(
                {"records": _list_staff_records(record_type), "source": "archipelago_staff"}
            ), HTTP_OK
        try:
            saved = _save_staff_record(
                record_type, request.get_json(silent=True), str(principal["id"])
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), HTTP_BAD_REQUEST
        except (requests.RequestException, RuntimeError, KeyError, IndexError):
            return jsonify({"error": "storage_unavailable"}), HTTP_UNAVAILABLE
        return jsonify({"record": saved, "source": "archipelago_staff"}), HTTP_OK

    @app.get("/api/analytics/sources")
    def analytics_sources_api() -> ResponseReturnValue:
        _principal, err = _require_role(ELEVATED_ROLES)
        if err is not None:
            return err
        include_demo = request.args.get("include_demo", "").strip().lower() in {"1", "true", "yes"}
        try:
            events, _audit = fetch_events(hosted_store(), is_demo=include_demo)
        except (RuntimeError, ValueError, requests.RequestException):
            events = []
        sources = audit_sources(load_koha_snapshot(), _all_staff_records(), events)
        return jsonify({"sources": sources, "demo_isolated": not include_demo}), HTTP_OK

    @app.get("/api/analytics/summary")
    def analytics_summary_api() -> ResponseReturnValue:
        _principal, err = _require_role(ELEVATED_ROLES)
        if err is not None:
            return err
        include_demo = request.args.get("include_demo", "").strip().lower() in {"1", "true", "yes"}
        source_id = request.args.get("source_id", "").strip() or None
        from_ts = request.args.get("from", "").strip() or None
        to_ts = request.args.get("to", "").strip() or None
        tz_name = request.args.get("tz", "").strip() or None
        try:
            events, audit_log = fetch_events(
                hosted_store(),
                is_demo=include_demo,
                source_id=source_id,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            summary = build_analytics_summary(
                koha_snapshot=load_koha_snapshot(),
                staff_records=_all_staff_records(),
                events=events,
                audit_log=audit_log,
                tz_name=tz_name,
                include_demo=include_demo,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), HTTP_BAD_REQUEST
        except (RuntimeError, requests.RequestException):
            return jsonify({"error": "analytics_storage_unavailable"}), HTTP_UNAVAILABLE
        return jsonify(summary), HTTP_OK

    @app.post("/api/analytics/events")
    def analytics_record_event_api() -> ResponseReturnValue:
        principal, err = _require_role(LIBRARIAN_ROLES)
        if err is not None or principal is None:
            return err  # type: ignore[return-value]
        try:
            result = record_event(
                hosted_store(), request.get_json(silent=True), str(principal["id"])
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), HTTP_BAD_REQUEST
        except (RuntimeError, requests.RequestException):
            return jsonify({"error": "analytics_storage_unavailable"}), HTTP_UNAVAILABLE
        status = HTTP_CREATED if result.get("inserted") else HTTP_OK
        return jsonify(result), status

    @app.get("/api/academic-automation/status")
    def academic_automation_status_api() -> ResponseReturnValue:
        _principal, err = _require_role(ELEVATED_ROLES)
        if err is not None:
            return err
        snap = _load_s4_snapshot(int(time.time() // CACHE_BUCKET_SECONDS))
        if not snap or not isinstance(snap.get("dashboard"), dict):
            return jsonify(
                {"configured": False, "message": "Academic synchronization has not run."}
            )
        return jsonify({"configured": True, **snap["dashboard"], "gpu": snap.get("gpu")}), HTTP_OK

    @app.get("/api/academic-automation/review/<job_id>")
    def academic_automation_review_api(job_id: str) -> ResponseReturnValue:
        _principal, err = _require_role(LIBRARIAN_ROLES, reject_dev_token=True)
        if err is not None:
            return err
        snap = _load_s4_snapshot(int(time.time() // CACHE_BUCKET_SECONDS))
        reviews = snap.get("reviews") if isinstance(snap, dict) else None
        packet = reviews.get(job_id) if isinstance(reviews, dict) else None
        if not isinstance(packet, dict):
            return jsonify(
                {"error": "review_unavailable", "detail": "Review-ready job not found"}
            ), HTTP_NOT_FOUND
        return jsonify(packet), HTTP_OK

    @app.post("/api/academic-automation/review/<job_id>/decision")
    def academic_automation_decision_api(job_id: str) -> ResponseReturnValue:
        principal, err = _require_role(LIBRARIAN_ROLES, reject_dev_token=True)
        if err is not None or principal is None:
            return err  # type: ignore[return-value]
        snap = _load_s4_snapshot(int(time.time() // CACHE_BUCKET_SECONDS))
        reviews = snap.get("reviews") if isinstance(snap, dict) else None
        packet = reviews.get(job_id) if isinstance(reviews, dict) else None
        if not isinstance(packet, dict):
            return jsonify(
                {"error": "invalid_review", "detail": "Review-ready job not found"}
            ), HTTP_BAD_REQUEST
        payload = request.get_json(silent=True) or {}
        decision = str(payload.get("decision") or "").strip()
        digest = str(payload.get("review_digest") or "").strip()
        note = str(payload.get("note") or "").strip()
        if decision not in {"approve", "reject"}:
            return jsonify(
                {"error": "invalid_review", "detail": "Decision must be approve or reject"}
            ), HTTP_BAD_REQUEST
        if packet.get("status") != "review_ready" or digest != packet.get("review_digest"):
            return jsonify(
                {
                    "error": "invalid_review",
                    "detail": "Review changed; reload the exact staging evidence",
                }
            ), HTTP_BAD_REQUEST
        if decision == "reject" and not note:
            return jsonify(
                {"error": "invalid_review", "detail": "A rejection needs a reason"}
            ), HTTP_BAD_REQUEST
        return jsonify(
            {
                "error": "workstation_required",
                "detail": "Staging publication and immutable Kùzu graph sign-off must be executed on the local library workstation.",
                "publication_status": "BLOCKED",
            }
        ), HTTP_CONFLICT
