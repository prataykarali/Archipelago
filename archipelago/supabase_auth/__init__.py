"""Supabase auth package — split from the former supabase_auth.py monolith.

Authentication is still enforced in production; the local file-backed user
directory remains a development-only fallback.
"""

from archipelago.supabase_auth.part01_verify import (
    VALID_ROLES,
    AuthPrincipal,
    _admin_headers,  # noqa: F401
    account_email,
    authenticate_request,
    get_service_role_key,
    is_auth_required,
    is_dev_auth_allowed,
    public_config,
)
from archipelago.supabase_auth.part02_local_store import (
    LOCAL_USERS_FILE,  # noqa: F401
    _ensure_local_users_file,  # noqa: F401
    _local_user_store_allowed,  # noqa: F401
    _read_local_users,  # noqa: F401
    _write_local_users,  # noqa: F401
)
from archipelago.supabase_auth.part03_manage_create import (
    create_managed_user,
    list_managed_users,
)
from archipelago.supabase_auth.part04_manage_update import (
    delete_managed_user,
    update_managed_user,
)

__all__ = [
    "VALID_ROLES",
    "AuthPrincipal",
    "account_email",
    "authenticate_request",
    "create_managed_user",
    "delete_managed_user",
    "get_service_role_key",
    "is_auth_required",
    "is_dev_auth_allowed",
    "list_managed_users",
    "public_config",
    "update_managed_user",
]
