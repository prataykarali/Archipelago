"""Authentication, RBAC multi-role gating, and institutional e-resource credentials."""
from __future__ import annotations

from archipelago.auth import (
    AUTH_REQUIRED,
    is_librarian_request,
    load_user,
    require_admin,
    require_auth,
    require_librarian,
    require_student_or_open,
)
from archipelago.inference.eresource_credentials import (
    clear_credential_cache,
    format_credential_for_response,
    get_credential,
    load_credentials,
)

__all__ = [
    "AUTH_REQUIRED",
    "clear_credential_cache",
    "format_credential_for_response",
    "get_credential",
    "is_librarian_request",
    "load_credentials",
    "load_user",
    "require_admin",
    "require_auth",
    "require_librarian",
    "require_student_or_open",
]
