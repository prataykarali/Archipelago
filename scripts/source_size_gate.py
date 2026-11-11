"""Audit hand-written source files against the production roadmap's line limit."""

from __future__ import annotations

import argparse
from pathlib import Path

MAX_SOURCE_LINES = 400
SOURCE_ROOTS = (
    "archipelago",
    "backend",
    "chat_server",
    "chat_ui",
    "deploy",
    "frontend",
    "host_inference",
    "infrastructure",
    "libraryAI",
    "okf",
    "scripts",
    "tests",
    "ui",
)
SOURCE_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "vendor",
}
GENERATED_SUFFIXES = (".min.js", ".min.css", ".generated.py", ".generated.ts")


def source_files(root: Path) -> list[Path]:
    """List application, UI, script, and test sources, omitting generated files."""
    paths: list[Path] = []
    for name in SOURCE_ROOTS:
        folder = root / name
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            if path.suffix not in SOURCE_SUFFIXES:
                continue
            if path.name.endswith(GENERATED_SUFFIXES):
                continue
            paths.append(path)
    paths.extend(
        path for path in root.iterdir() if path.is_file() and path.suffix in SOURCE_SUFFIXES
    )
    return sorted(set(paths))


def oversized_sources(root: Path, limit: int = MAX_SOURCE_LINES) -> list[tuple[Path, int]]:
    """Return source paths and line counts exceeding the configured limit."""
    violations: list[tuple[Path, int]] = []
    for path in source_files(root):
        try:
            count = len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            continue
        if count > limit:
            violations.append((path.relative_to(root), count))
    return sorted(violations, key=lambda item: (-item[1], str(item[0])))


def main() -> int:
    """Print violations and fail when any hand-written source exceeds the limit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    violations = oversized_sources(root)
    for path, count in violations:
        print(f"{count:5}  {path}")
    print(f"{len(violations)} source files exceed {MAX_SOURCE_LINES} lines")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
