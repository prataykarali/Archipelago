"""Rights and Open-Access Resolver.

Determines legal access route and permissions for scholarly artifacts.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

OPEN_LICENSE_MARKERS = ("creativecommons.org/licenses/", "creativecommons.org/publicdomain/")
TRUSTED_PREPRINT_HOSTS = frozenset({"arxiv.org", "export.arxiv.org"})


class RightsResolver:
    """Enforces institutional rights and open-access compliance."""

    def resolve_access(
        self,
        is_open_access: bool | None,
        license_str: str | None,
        pdf_url: str | None,
    ) -> dict[str, Any]:
        """Determine access basis and permissions."""
        if not pdf_url:
            return {
                "decision": "metadata_only",
                "can_fetch_fulltext": False,
                "reason": "no_pdf_url",
            }

        parsed = urlparse(pdf_url)
        if parsed.scheme != "https" or not parsed.hostname:
            return {
                "decision": "metadata_only",
                "can_fetch_fulltext": False,
                "reason": "untrusted_pdf_url",
            }

        host = parsed.hostname.lower()
        if host in TRUSTED_PREPRINT_HOSTS and parsed.path.startswith("/pdf/"):
            return {
                "decision": "store_and_process",
                "can_fetch_fulltext": True,
                "license": license_str,
                "redistribution_allowed": False,
                "reason": "arxiv_paper_access",
            }

        if (
            is_open_access is True
            and license_str
            and any(marker in license_str.lower() for marker in OPEN_LICENSE_MARKERS)
        ):
            return {
                "decision": "store_and_process",
                "can_fetch_fulltext": True,
                "license": license_str,
                "redistribution_allowed": False,
                "reason": "explicit_open_license",
            }

        return {
            "decision": "metadata_only",
            "can_fetch_fulltext": False,
            "license": license_str,
            "reason": "rights_not_verified",
        }
