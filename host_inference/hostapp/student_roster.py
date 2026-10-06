"""Validate and provision approved student enrollment CSVs without retaining rows."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
import io
import os
import re

import requests
from supabase_service_headers import service_headers

ENROLLMENT = re.compile(r"^[0-9]{14}$")
MAX_IMPORT_ROWS = 100
MAX_DISPLAY_NAME = 160
MAX_ROSTER_BYTES = 1024 * 1024
REQUEST_TIMEOUT = 15
SUPABASE_EMAIL_DOMAIN = "student.iem.archipelago.invalid"


def parse_roster(raw: bytes) -> list[dict[str, str]]:
    """Parse a UTF-8 CSV with enrollment and optional display name columns."""
    if len(raw) > MAX_ROSTER_BYTES:
        raise ValueError("Student roster exceeds the 1 MB limit.")
    try:
        source = io.StringIO(raw.decode("utf-8-sig", errors="strict"), newline="")
        reader = csv.DictReader(source)
        headers = {str(name or "").strip().lower(): name for name in reader.fieldnames or []}
        enrollment_col = (
            headers.get("enrollment") or headers.get("enrollment_number") or headers.get("username")
        )
        if enrollment_col is None:
            raise ValueError("CSV needs an enrollment column.")
        name_col = headers.get("display_name") or headers.get("name")
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for line_no, row in enumerate(reader, start=2):
            if len(rows) >= MAX_IMPORT_ROWS:
                raise ValueError(f"Import at most {MAX_IMPORT_ROWS} students at a time.")
            enrollment = str(row.get(enrollment_col) or "").strip()
            if not ENROLLMENT.fullmatch(enrollment):
                raise ValueError(f"Line {line_no}: enrollment must be 14 digits.")
            if enrollment in seen:
                raise ValueError(f"Line {line_no}: duplicate enrollment in this CSV.")
            name = str(row.get(name_col) or "").strip() if name_col else ""
            if (
                len(name) > MAX_DISPLAY_NAME
                or any(ord(char) < 32 for char in name)
                or name.lstrip().startswith(("=", "+", "-", "@"))
            ):
                raise ValueError(f"Line {line_no}: invalid display name.")
            seen.add(enrollment)
            rows.append({"username": enrollment, "display_name": name})
    except UnicodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc
    except csv.Error as exc:
        raise ValueError("CSV could not be parsed.") from exc
    if not rows:
        raise ValueError("CSV has no student records.")
    return rows


def service_config() -> tuple[str, str, str]:
    """Read the server-only Supabase key and initial password from environment."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    password = os.getenv("ARCHIPELAGO_BOOTSTRAP_PASSWORD", "")
    if not url or not key or not password:
        raise RuntimeError("Student provisioning is not configured.")
    return url, key, password


def _headers(key: str) -> dict[str, str]:
    return service_headers(key, json_body=True)


def import_permission(url: str, key: str, principal: dict, source_label: str) -> str | None:
    """Return a current librarian grant ID, or None if approval is absent."""
    if principal.get("role") == "administrator":
        return ""
    if principal.get("role") != "librarian" or not source_label:
        return None
    response = requests.get(
        f"{url}/rest/v1/credential_import_permissions",
        params={
            "select": "id",
            "librarian_id": f"eq.{principal['user_id']}",
            "source_label": f"eq.{source_label}",
            "expires_at": f"gt.{datetime.now(UTC).isoformat()}",
            "revoked_at": "is.null",
            "limit": "1",
        },
        headers=_headers(key),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    rows = response.json()
    return str(rows[0]["id"]) if isinstance(rows, list) and rows else None


def existing_students(url: str, key: str, rows: list[dict[str, str]]) -> set[str]:
    """Find existing usernames in one server-authorized query for idempotency."""
    usernames = ",".join(row["username"] for row in rows)
    response = requests.get(
        f"{url}/rest/v1/profiles",
        params={"select": "username", "username": f"in.({usernames})"},
        headers=_headers(key),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    found = response.json()
    if not isinstance(found, list):
        raise RuntimeError("Unexpected profile lookup result.")
    return {str(item["username"]) for item in found}


def provision_students(
    url: str, key: str, password: str, rows: list[dict[str, str]], existing: set[str]
) -> tuple[int, int]:
    """Create missing accounts; each retry safely skips previously created rows."""
    created = 0
    failed = 0
    for row in rows:
        username = row["username"]
        if username in existing:
            continue
        try:
            response = requests.post(
                f"{url}/auth/v1/admin/users",
                headers=_headers(key),
                json={
                    "email": f"{username}@{SUPABASE_EMAIL_DOMAIN}",
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"username": username, "display_name": row["display_name"]},
                    "app_metadata": {"must_change_password": True},
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException:
            failed += 1
            continue
        if response.status_code in {200, 201}:
            created += 1
        else:
            failed += 1
    return created, failed


def audit_import(
    url: str,
    key: str,
    principal: dict,
    permission_id: str,
    filename: str,
    raw: bytes,
    received: int,
    created: int,
    rejected: int,
) -> None:
    """Store counts and a file fingerprint; never store student rows or passwords."""
    record = {
        "permission_id": permission_id or None,
        "librarian_id": principal["user_id"],
        "source_filename": filename,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "records_received": received,
        "records_created": created,
        "records_rejected": rejected,
    }
    response = requests.post(
        f"{url}/rest/v1/credential_import_audits",
        headers={**_headers(key), "Prefer": "return=minimal"},
        json=record,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
