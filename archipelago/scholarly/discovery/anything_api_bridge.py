"""API-Anything Integration Bridge.

Dispatches external calls and captured site operations using the api-anything engine.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

logger = logging.getLogger("archipelago.scholarly.anything_api")


class AnythingApiBridge:
    """Bridge allowing the discovery pipeline to invoke api-anything operations."""

    def __init__(self, cli_path: str | None = None) -> None:
        self.cli_path: Path | None
        configured_path = cli_path or os.environ.get("ARCHIPELAGO_API_ANYTHING_CLI")
        if configured_path:
            self.cli_path = Path(configured_path)
        else:
            global_bin = shutil.which("api-anything")
            self.cli_path = Path(global_bin) if global_bin else None

    def is_available(self) -> bool:
        """Check if api-anything is installed and accessible."""
        return self.cli_path is not None and (
            self.cli_path.is_file() or shutil.which(str(self.cli_path)) is not None
        )

    def list_sites(self) -> list[dict[str, Any]]:
        """List active sites configured in api-anything."""
        if not self.is_available() or self.cli_path is None:
            return []
        try:
            cmd = (
                ["node", str(self.cli_path), "sites"]
                if self.cli_path.suffix == ".js"
                else [str(self.cli_path), "sites"]
            )
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                payload = json.loads(res.stdout)
                if isinstance(payload, list):
                    return [item for item in payload if isinstance(item, dict)]
        except Exception as e:
            logger.warning("api-anything list_sites failed: %s", e)
        return []

    def call(self, site: str, operation: str, **kwargs: Any) -> dict[str, Any] | None:
        """Execute an operation via api-anything and return structured JSON."""
        if not self.is_available() or self.cli_path is None:
            logger.warning("api-anything CLI is not available.")
            return None

        cmd = (
            ["node", str(self.cli_path), "call", site, operation]
            if self.cli_path.suffix == ".js"
            else [str(self.cli_path), "call", site, operation]
        )
        for k, v in kwargs.items():
            cmd.append(f"{k}={v}")

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if res.returncode == 0:
                payload = json.loads(res.stdout)
                return payload if isinstance(payload, dict) else None
            else:
                logger.error("api-anything call failed: %s", res.stderr)
        except Exception as e:
            logger.error("Error executing api-anything call: %s", e)
        return None
