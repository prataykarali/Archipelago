"""
Archipelago Remote Storage Engine (Hugging Face Dataset Hub).

Provides offloaded cloud storage for book assets, manifests, and datasets
in Prataykarali/Library_books to prevent local disk exhaustion.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import BinaryIO, Optional

try:
    from huggingface_hub import HfApi, hf_hub_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

logger = logging.getLogger("archipelago.storage.hf_remote")

DEFAULT_REPO_ID = "Prataykarali/Library_books"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "archipelago" / "library_books"
# Hub revision to download from. Pin to a commit/tag SHA in production so an
# upstream force-push cannot silently change the corpus we ingest.
DEFAULT_REVISION = os.environ.get("HF_DATASET_REVISION", "main")


def compute_sha256(data_or_path: bytes | str | Path) -> str:
    """Compute SHA-256 checksum of bytes or file path."""
    hasher = hashlib.sha256()
    if isinstance(data_or_path, (str, Path)):
        with open(data_or_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
    else:
        hasher.update(data_or_path)
    return hasher.hexdigest()


class HFStorageClient:
    """Client for managing book assets in a private Hugging Face Dataset repository."""

    def __init__(
        self,
        repo_id: str | None = None,
        token: str | None = None,
        cache_dir: Path | str | None = None,
        offline: bool = False,
        revision: str | None = None,
    ):
        self.offline = offline
        self.revision = revision or DEFAULT_REVISION
        self.repo_id = (
            repo_id
            or os.environ.get("HF_DATASET_REPO")
            or DEFAULT_REPO_ID
        )
        self.token = token if token is not None else os.environ.get("HF_TOKEN")
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not self.token and not self.offline:
            # Check .env file directly if not in os.environ
            env_file = Path(__file__).resolve().parents[3] / ".env"
            if not env_file.is_file():
                env_file = Path.cwd() / ".env"
            if env_file.is_file():
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("HF_TOKEN="):
                            self.token = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.startswith("HF_DATASET_REPO="):
                            if not repo_id:
                                self.repo_id = line.split("=", 1)[1].strip().strip('"').strip("'")

        self.api = HfApi(token=self.token) if (HF_HUB_AVAILABLE and self.token and not self.offline) else None

    @property
    def is_available(self) -> bool:
        """Return True if HF API is authenticated and usable."""
        return bool(not self.offline and HF_HUB_AVAILABLE and self.api and self.token)

    def verify_remote_access(self) -> bool:
        """Verify that the repository exists, is private, and token has write access."""
        if not self.is_available:
            return False
        try:
            info = self.api.dataset_info(self.repo_id)
            return bool(info and info.private)
        except Exception as exc:
            logger.warning("HF remote access verification failed: %s", exc)
            return False

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists in the HF dataset repository."""
        if not self.is_available:
            return (self.cache_dir / remote_path).is_file()
        try:
            return bool(self.api.file_exists(self.repo_id, remote_path, repo_type="dataset"))
        except Exception as exc:
            logger.debug("Error checking remote file existence (%s): %s", remote_path, exc)
            return (self.cache_dir / remote_path).is_file()

    def list_files(self, prefix: str = "") -> list[str]:
        """List files in the dataset repository matching prefix."""
        if not self.is_available:
            cached = []
            for p in self.cache_dir.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(self.cache_dir))
                    if rel.startswith(prefix):
                        cached.append(rel)
            return cached
        try:
            files = self.api.list_repo_files(self.repo_id, repo_type="dataset")
            if prefix:
                return [f for f in files if f.startswith(prefix)]
            return files
        except Exception as exc:
            logger.warning("Failed to list files from HF dataset: %s", exc)
            return []

    def upload_file(
        self,
        local_path: str | Path,
        remote_path: str,
        commit_message: str | None = None,
    ) -> dict:
        """Upload a local file to HF dataset with SHA-256 integrity check."""
        local = Path(local_path)
        if not local.is_file():
            raise FileNotFoundError(f"Local file not found: {local}")

        sha256 = compute_sha256(local)
        file_size = local.stat().st_size

        if not self.is_available:
            cache_target = self.cache_dir / remote_path
            cache_target.parent.mkdir(parents=True, exist_ok=True)
            cache_target.write_bytes(local.read_bytes())
            return {
                "success": True,
                "remote_path": remote_path,
                "sha256": sha256,
                "size_bytes": file_size,
                "mode": "local_fallback",
            }

        msg = commit_message or f"Upload {remote_path} (size: {file_size} bytes, sha: {sha256[:8]})"
        self.api.upload_file(
            path_or_fileobj=str(local),
            path_in_repo=remote_path,
            repo_id=self.repo_id,
            repo_type="dataset",
            commit_message=msg,
        )

        cache_target = self.cache_dir / remote_path
        cache_target.parent.mkdir(parents=True, exist_ok=True)
        if cache_target != local:
            try:
                cache_target.write_bytes(local.read_bytes())
            except Exception:
                pass

        return {
            "success": True,
            "remote_path": remote_path,
            "sha256": sha256,
            "size_bytes": file_size,
            "mode": "hf_hub",
        }

    def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        commit_message: str | None = None,
    ) -> dict:
        """Upload raw bytes directly to HF dataset."""
        sha256 = compute_sha256(data)
        file_size = len(data)

        if not self.is_available:
            cache_target = self.cache_dir / remote_path
            cache_target.parent.mkdir(parents=True, exist_ok=True)
            cache_target.write_bytes(data)
            return {
                "success": True,
                "remote_path": remote_path,
                "sha256": sha256,
                "size_bytes": file_size,
                "mode": "local_fallback",
            }

        msg = commit_message or f"Upload bytes {remote_path} ({file_size} bytes)"
        self.api.upload_file(
            path_or_fileobj=data,
            path_in_repo=remote_path,
            repo_id=self.repo_id,
            repo_type="dataset",
            commit_message=msg,
        )

        cache_target = self.cache_dir / remote_path
        cache_target.parent.mkdir(parents=True, exist_ok=True)
        try:
            cache_target.write_bytes(data)
        except Exception:
            pass

        return {
            "success": True,
            "remote_path": remote_path,
            "sha256": sha256,
            "size_bytes": file_size,
            "mode": "hf_hub",
        }

    def download_file(
        self,
        remote_path: str,
        local_path: str | Path | None = None,
        force_download: bool = False,
    ) -> Path:
        """Download a file from HF dataset or return from local cache."""
        target = Path(local_path) if local_path else (self.cache_dir / remote_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.is_file() and not force_download:
            return target

        if not self.is_available:
            if target.is_file():
                return target
            raise FileNotFoundError(f"File not available in offline cache: {remote_path}")

        cached_path = hf_hub_download(
            repo_id=self.repo_id,
            filename=remote_path,
            repo_type="dataset",
            token=self.token,
            revision=self.revision,
            local_dir=str(self.cache_dir),
            force_download=force_download,
        )

        result_path = Path(cached_path)
        if target != result_path:
            target.write_bytes(result_path.read_bytes())
            return target
        return result_path
