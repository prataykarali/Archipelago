"""Checkpointed open-access source acquisition and local baseline cache resolver.

Downloads only license-gate-approved OA sources to a gitignored data directory
using atomic temporary files and size caps. Reuses pinned local HF cache files
for the baseline corpus_v2_d10_3025 documents without mutating them.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import requests

from archipelago.corpus.catalog import PARENT_HF_REVISION, SourceFormat, SourceSpec
from archipelago.corpus.extractors import sha256_file

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_SECONDS = 60
STREAM_CHUNK_BYTES = 64 * 1024
MAX_SOURCE_FILE_BYTES = 80 * 1024 * 1024
HTTP_OK_MAX = 299
DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Archipelago-D14-OER-Pipeline/1.0"
DEFAULT_HF_CACHE_SNAPSHOT = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "datasets--Prataykarali--Library_books"
    / "snapshots"
    / PARENT_HF_REVISION
)


@dataclass(frozen=True)
class AcquiredSource:
    """Resolved local files and checksums for one authorized source."""

    source_id: str
    local_paths: tuple[Path, ...]
    primary_sha256: str
    total_bytes: int
    acquired_ok: bool
    status: str  # "reused_baseline_cache" | "downloaded" | "cached_local" | "failed"
    error: str = ""


def _download_single_url(url: str, destination: Path) -> tuple[bool, str]:
    """Download ``url`` atomically into ``destination`` with strict byte cap."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0:
        return True, "cached_local"

    temp_path = destination.with_suffix(destination.suffix + ".tmp")
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    try:
        with requests.get(
            url,
            headers=headers,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
            stream=True,
            allow_redirects=True,
        ) as resp:
            if resp.status_code > HTTP_OK_MAX:
                return False, f"http_{resp.status_code}"
            written = 0
            with temp_path.open("wb") as handle:
                for chunk in resp.iter_content(chunk_size=STREAM_CHUNK_BYTES):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > MAX_SOURCE_FILE_BYTES:
                        temp_path.unlink(missing_ok=True)
                        return False, "exceeded_max_bytes"
                    handle.write(chunk)
        if written == 0:
            temp_path.unlink(missing_ok=True)
            return False, "empty_response"
        temp_path.replace(destination)
        return True, "downloaded"
    except requests.RequestException as exc:
        temp_path.unlink(missing_ok=True)
        logger.warning("Download failed for %s: %s", url, exc)
        return False, f"request_error:{type(exc).__name__}"


def _combined_sha256(paths: list[Path]) -> str:
    """Return SHA-256 of a single file or deterministic hash over multi-file HTML bundles."""
    if len(paths) == 1:
        return sha256_file(paths[0])
    import hashlib

    digest = hashlib.sha256()
    for path in paths:
        digest.update(sha256_file(path).encode("ascii"))
    return digest.hexdigest()


def acquire_source(
    spec: SourceSpec,
    *,
    raw_dir: Path,
    hf_cache_dir: Path = DEFAULT_HF_CACHE_SNAPSHOT,
    allow_network: bool = True,
) -> AcquiredSource:
    """Resolve a baseline cached file or download an authorized OA source."""
    if spec.origin == "baseline_v2_hf_cache":
        local_path = hf_cache_dir / spec.local_rel_path
        if local_path.is_file():
            return AcquiredSource(
                source_id=spec.source_id,
                local_paths=(local_path,),
                primary_sha256=sha256_file(local_path),
                total_bytes=local_path.stat().st_size,
                acquired_ok=True,
                status="reused_baseline_cache",
            )
        return AcquiredSource(
            source_id=spec.source_id,
            local_paths=(),
            primary_sha256="",
            total_bytes=0,
            acquired_ok=False,
            status="failed",
            error=f"missing_hf_cache:{local_path}",
        )

    urls = (spec.canonical_url, *spec.extra_urls)
    ext = f".{spec.source_format.value}"
    source_folder = raw_dir / spec.source_id
    downloaded_paths: list[Path] = []
    statuses: list[str] = []

    for idx, url in enumerate(urls):
        dest = source_folder / f"{spec.source_id}_part{idx:02d}{ext}"
        if dest.is_file() and dest.stat().st_size > 0:
            downloaded_paths.append(dest)
            statuses.append("cached_local")
            continue
        if not allow_network:
            return AcquiredSource(
                source_id=spec.source_id,
                local_paths=(),
                primary_sha256="",
                total_bytes=0,
                acquired_ok=False,
                status="failed",
                error="network_disabled_and_not_cached",
            )
        ok, status = _download_single_url(url, dest)
        if not ok:
            return AcquiredSource(
                source_id=spec.source_id,
                local_paths=(),
                primary_sha256="",
                total_bytes=0,
                acquired_ok=False,
                status="failed",
                error=f"{status}:{url}",
            )
        downloaded_paths.append(dest)
        statuses.append(status)

    if spec.source_format == SourceFormat.PDF:
        head = downloaded_paths[0].read_bytes()[:4]
        if head != b"%PDF":
            return AcquiredSource(
                source_id=spec.source_id,
                local_paths=(),
                primary_sha256="",
                total_bytes=0,
                acquired_ok=False,
                status="failed",
                error="invalid_pdf_magic_header",
            )

    total_bytes = sum(p.stat().st_size for p in downloaded_paths)
    final_status = "downloaded" if "downloaded" in statuses else "cached_local"
    return AcquiredSource(
        source_id=spec.source_id,
        local_paths=tuple(downloaded_paths),
        primary_sha256=_combined_sha256(downloaded_paths),
        total_bytes=total_bytes,
        acquired_ok=True,
        status=final_status,
    )
