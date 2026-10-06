"""Provision Supabase Auth accounts from an approved staff CSV.

This is a one-time, administrator-run tool. The input CSV is intentionally not
stored by Archipelago and must be deleted from the administrator workstation
after the import completes.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import re
import sys
from typing import Any

from dotenv import load_dotenv
import requests

ALLOWED_ROLES = frozenset({"student", "librarian", "administrator"})
REQUIRED_FIELDS = frozenset({"username", "role"})
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
STUDENT_ENROLLMENT_PATTERN = re.compile(r"^\d{14}$")
REQUEST_TIMEOUT_SECONDS = 20


def account_email(username: str, role: str) -> str:
    """Build the internal Auth email used for username/password sign-in."""
    return f"{username.lower()}@{role}.iem.archipelago.invalid"


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read and validate a provision CSV without printing password values."""
    with csv_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        fieldnames = frozenset(reader.fieldnames or [])
        missing = REQUIRED_FIELDS - fieldnames
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError("CSV contains no account rows.")
    for row in rows:
        username = row.get("username", "")
        role = row.get("role", "")
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError(f"Invalid username: {username!r}")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role for {username!r}: {role!r}")
        if role == "student" and not STUDENT_ENROLLMENT_PATTERN.fullmatch(username):
            raise ValueError(f"Student {username!r} must have a 14-digit enrollment number.")
    return rows


def api_headers(service_role_key: str) -> dict[str, str]:
    """Return server-only headers for the Supabase Admin API."""
    headers = {"apikey": service_role_key, "Content-Type": "application/json"}
    if not service_role_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {service_role_key}"
    return headers


def provision_account(
    base_url: str,
    service_role_key: str,
    row: dict[str, str],
    bootstrap_password: str,
) -> None:
    """Create one Auth account and assign its non-user-controlled application role."""
    username = row["username"]
    role = row["role"]
    payload: dict[str, Any] = {
        "email": account_email(username, role),
        "password": bootstrap_password,
        "email_confirm": True,
        "user_metadata": {
            "username": username,
            "display_name": row.get("display_name", ""),
        },
        "app_metadata": {"must_change_password": True},
    }
    response = requests.post(
        f"{base_url}/auth/v1/admin/users",
        headers=api_headers(service_role_key),
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"Could not create {username!r}: HTTP {response.status_code}")
    user_id = str(response.json().get("id", ""))
    if not user_id:
        raise RuntimeError(f"Supabase did not return an account ID for {username!r}.")

    role_response = requests.patch(
        f"{base_url}/rest/v1/profiles",
        params={"id": f"eq.{user_id}"},
        headers={**api_headers(service_role_key), "Prefer": "return=minimal"},
        json={"role": role},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if role_response.status_code not in {200, 204}:
        raise RuntimeError(
            f"Could not assign role to {username!r}: HTTP {role_response.status_code}"
        )


def main() -> int:
    """Provision accounts from a locally approved CSV file."""
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="CSV with username,role[,display_name]")
    args = parser.parse_args()

    base_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_role_key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    bootstrap_password = os.getenv("ARCHIPELAGO_BOOTSTRAP_PASSWORD", "")
    if not base_url or not service_role_key or not bootstrap_password:
        print(
            "SUPABASE_URL, SUPABASE_SECRET_KEY (or the legacy "
            "SUPABASE_SERVICE_ROLE_KEY), and "
            "ARCHIPELAGO_BOOTSTRAP_PASSWORD are required.",
            file=sys.stderr,
        )
        return 2

    rows = load_rows(args.csv_path)
    completed = 0
    for row in rows:
        provision_account(base_url, service_role_key, row, bootstrap_password)
        completed += 1
        print(f"Provisioned {row['role']} account for {row['username']}.")
    print(f"Provisioned {completed} account(s). Rotate the bootstrap password immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
