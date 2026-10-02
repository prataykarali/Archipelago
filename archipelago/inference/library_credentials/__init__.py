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

from .part01_env import (  # noqa: F401
    _env,
    E_RESOURCE_CREDENTIALS,
    _RESOURCE_ALIASES,
    lookup_credential,
    _SECRET_FIELD_NAMES,
    _redacted,
    format_credential_for_response,
    _CREDENTIALS_KEYWORDS,
    _RESOURCE_NAME_PATTERN,
)
from .part02_detect_credentials_query import (  # noqa: F401
    detect_credentials_query,
)

__all__ = ["_env", "E_RESOURCE_CREDENTIALS", "_RESOURCE_ALIASES", "lookup_credential", "_SECRET_FIELD_NAMES", "_redacted", "format_credential_for_response", "_CREDENTIALS_KEYWORDS", "_RESOURCE_NAME_PATTERN", "detect_credentials_query"]
