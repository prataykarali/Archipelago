"""Artifact Fetcher.

Downloads permitted PDFs, validates magic bytes, computes SHA-256, and writes immutable artifacts.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
from pathlib import Path
import socket
from typing import Any
from urllib.parse import urlparse
import urllib.request

logger = logging.getLogger("archipelago.scholarly.fetcher")

DEFAULT_STORAGE_ROOT = Path(
    os.getenv("ARCHIPELAGO_RESEARCH_ARTIFACT_ROOT", "data/artifacts/papers")
)
MAX_REDIRECTS = 3


def _public_https_url(url: str) -> bool:
    """Reject local/private network targets before fetching a source-supplied PDF."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    return bool(addresses) and all(
        ipaddress.ip_address(address[4][0]).is_global for address in addresses
    )


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not _public_https_url(newurl):
            raise ValueError("PDF redirect points to an untrusted network address")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ArtifactFetcher:
    """Downloads and verifies scientific document artifacts."""

    def __init__(self, storage_root: Path = DEFAULT_STORAGE_ROOT, max_size_mb: int = 40):
        self.storage_root = storage_root
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Archipelago-Fetcher/1.0"}

    def fetch_pdf(self, url: str, paper_id: str) -> dict[str, Any] | None:
        """Fetch PDF, verify %PDF- magic bytes, and return immutable artifact record."""
        if not _public_https_url(url):
            logger.warning("Rejected untrusted PDF address")
            return None
        req = urllib.request.Request(url, headers=self.headers)
        try:
            opener = urllib.request.build_opener(_SafeRedirects())
            with opener.open(req, timeout=25) as resp:
                content = resp.read(self.max_size_bytes + 1)
                if len(content) > self.max_size_bytes:
                    logger.warning(
                        "PDF at %s exceeded maximum allowed size (%d MB)",
                        urlparse(url).hostname,
                        self.max_size_bytes // (1024 * 1024),
                    )
                    return None

                # Verify PDF magic bytes
                if not content.startswith(b"%PDF-"):
                    logger.warning("Artifact from %s is not a PDF", urlparse(url).hostname)
                    return None

                sha256 = hashlib.sha256(content).hexdigest()
                dest_dir = self.storage_root / paper_id / "pdf"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / f"{sha256}.pdf"

                with open(dest_path, "wb") as f:
                    f.write(content)

                return {
                    "artifact_type": "pdf",
                    "file_path": str(dest_path),
                    "sha256": sha256,
                    "byte_size": len(content),
                    "source_url": url,
                    "mime_type": "application/pdf",
                }
        except Exception as e:
            logger.warning("Failed to fetch PDF from %s: %s", urlparse(url).hostname, e)
            return None
