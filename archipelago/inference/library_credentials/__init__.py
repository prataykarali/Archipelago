"""Library e-resource metadata (SCH-2).

Student-facing library chat must NEVER see plaintext passwords, passkeys,
institutional emails tied to credentials, or personal subscriber addresses.
This module therefore exposes:

* ``E_RESOURCE_CREDENTIALS`` — portal metadata keyed by resource. All
  human-secret fields (``password``, ``passkey``, ``passkey_alt``,
  ``username``, ``registration_number``, ``credential_id`` for identifiable
  emails) are either omitted or read from env vars with empty-string
  defaults. Staff-side tooling may override via ``ARCHIPELAGO_ERESOURCE_JSON``
  or ``ARCHIPELAGO_ERESOURCE_<KEY>_<FIELD>`` env vars; the chat UI never
  receives raw dicts — only :func:`format_credential_for_response` output.
* :func:`format_credential_for_response` — always redacts secret-shaped
  values, regardless of whether they were loaded from env.

Do NOT reintroduce plaintext passwords here. The pilot demo must not leak
portal passwords to students. Librarians sharing credentials in person is
a staff-side process, not a chat snippet."""

from __future__ import annotations

import os  # noqa: F401
import re  # noqa: F401
from typing import Any  # noqa: F401

from .part01_env import (
    _CREDENTIALS_KEYWORDS,
    _RESOURCE_ALIASES,
    _RESOURCE_NAME_PATTERN,
    _SECRET_FIELD_NAMES,
    E_RESOURCE_CREDENTIALS,
    _env,
    _redacted,
    format_credential_for_response,
    lookup_credential,
)
from .part02_detect_credentials_query import (
    detect_credentials_query,
)

__all__ = [
    "E_RESOURCE_CREDENTIALS",
    "_CREDENTIALS_KEYWORDS",
    "_RESOURCE_ALIASES",
    "_RESOURCE_NAME_PATTERN",
    "_SECRET_FIELD_NAMES",
    "_env",
    "_redacted",
    "detect_credentials_query",
    "format_credential_for_response",
    "lookup_credential",
]
