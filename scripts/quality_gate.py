#!/usr/bin/env python3
"""Quality gate enforcement script (Skill 4 — 5-pass review).

Run locally before every commit:

    python scripts/quality_gate.py

Exits non-zero if any gate fails. Each gate is a "pass" in the 5-pass review:

    Pass 1: Lint          — ruff check + ruff format --check
    Pass 2: Types         — mypy --strict
    Pass 3: Banned patterns — auto-fail list from AGENTS.md
    Pass 4: Architecture  — dependency rules, file size, feature boundaries

Pass 5 (human review) is manual and not automated here.

The script is designed to be fast and informative: it prints a summary table
at the end so developers can see exactly what passed and what failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

MAX_FILE_LINES = 500

EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".git",
    "build",
    "dist",
    "node_modules",
    "okf_graph.db",
    "okf_graph.db/",
    ".strix-pentest",
    "training",
}

BANNED_PATTERN_EXCLUDES = {"tests", "scripts"}


@dataclass
class BannedPattern:
    """A pattern that causes immediate CI failure."""

    name: str
    pattern: str
    description: str
    exclude_dirs: set[str] = field(default_factory=set)
    compile_flags: int = 0

    def matches(self, content: str) -> list[tuple[int, str]]:
        """Return list of (line_number, line_content) for matches."""
        results: list[tuple[int, str]] = []
        for i, line in enumerate(content.splitlines(), start=1):
            if re.search(self.pattern, line, self.compile_flags):
                results.append((i, line))
        return results


BANNED_PATTERNS: list[BannedPattern] = [
    BannedPattern(
        name="bare_except_pass",
        pattern=r"^\s*except\s*:\s*pass",
        description="Bare except: pass — silently swallows all errors.",
    ),
    BannedPattern(
        name="exception_pass",
        pattern=r"^\s*except\s+Exception\s*:\s*pass",
        description="except Exception: pass — silently swallows errors.",
    ),
    BannedPattern(
        name="eval",
        pattern=r"(?<![.\w])eval\s*\(",
        description="eval() — code execution from untrusted input.",
    ),
    BannedPattern(
        name="exec",
        pattern=r"\bexec\s*\(",
        description="exec() — code execution from untrusted input.",
    ),
    BannedPattern(
        name="shell_true",
        pattern=r"shell\s*=\s*True",
        description="shell=True — shell injection risk.",
    ),
    BannedPattern(
        name="pickle_load",
        pattern=r"pickle\.load\b",
        description="pickle.load — deserialization attack vector.",
    ),
    BannedPattern(
        name="os_system",
        pattern=r"os\.system\s*\(",
        description="os.system — shell injection risk.",
    ),
    BannedPattern(
        name="yaml_load_unsafe",
        pattern=r"yaml\.load\s*\(",
        description="yaml.load without Loader — use yaml.safe_load.",
    ),
    BannedPattern(
        name="verify_false",
        pattern=r"verify\s*=\s*False",
        description="verify=False — TLS certificate bypass.",
    ),
    BannedPattern(
        name="prompt_injection_sink",
        pattern=r'f["\'].*\{.*user_input.*\}.*["\']',
        description="f-string with user_input — potential prompt injection sink.",
        exclude_dirs={"tests", "scripts"},
    ),
    BannedPattern(
        name="unchecked_ollama_output",
        pattern=r"ollama\.chat\s*\(",
        description="Direct ollama.chat() call without output validation.",
        exclude_dirs={"tests", "scripts"},
    ),
    BannedPattern(
        name="hardcoded_password",
        pattern=r'password\s*=\s*["\'][^"\']+["\']',
        description="Hardcoded password — security risk.",
        exclude_dirs={"tests", "scripts"},
    ),
    BannedPattern(
        name="hardcoded_api_key",
        pattern=r'api_key\s*=\s*["\'][^"\']+["\']',
        description="Hardcoded API key — security risk.",
        exclude_dirs={"tests", "scripts"},
    ),
    BannedPattern(
        name="hardcoded_token",
        pattern=r'token\s*=\s*["\'][a-zA-Z0-9_\-]{16,}["\']',
        description="Hardcoded token — security risk.",
        exclude_dirs={"tests", "scripts"},
    ),
]

MAGIC_NUMBER_EXCLUDES = {"tests", "scripts", "pyproject.toml"}
MAGIC_NUMBER_PATTERN = re.compile(
    r"(?<![a-zA-Z_.'\"])(?<![\w.])(\d{2,})(?!\w*['\"])",
)

MAGIC_NUMBER_EXCEPTIONS = {
    200,
    201,
    204,
    301,
    302,
    400,
    401,
    403,
    404,
    409,
    500,
    502,
    503,
    80,
    443,
    8080,
    5050,
    5051,
    5052,
    32,
    64,
    128,
    256,
    512,
    1024,
    60,
    120,
    600,
    900,
    3600,
    100,
    255,
    1000,
}

FORBIDDEN_IMPORTS: dict[str, list[str]] = {
    "archipelago.inference": ["import okf", "from okf"],
    "archipelago.ingestion": ["import okf", "from okf"],
    "okf": [
        "import archipelago.inference",
        "from archipelago.inference",
        "import archipelago.ingestion",
        "from archipelago.ingestion",
    ],
}


@dataclass
class GateResult:
    """Result of a single quality gate check."""

    name: str
    passed: bool = False
    details: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[{status}] {self.name}"]
        for d in self.details:
            lines.append(f"       {d}")
        for w in self.warnings:
            lines.append(f"       ⚠ {w}")
        return "\n".join(lines)


def find_python_files(root: Path) -> list[Path]:
    """Find all Python files, excluding configured directories."""
    files: list[Path] = []
    for path in root.rglob("*.py"):
        parts = path.relative_to(root).parts
        if any(part in EXCLUDE_DIRS for part in parts):
            continue
        files.append(path)
    return sorted(files)


def should_exclude_from_banned(filepath: Path, root: Path) -> bool:
    """Check if a file should be excluded from banned-pattern checks."""
    rel = filepath.relative_to(root)
    return any(part in BANNED_PATTERN_EXCLUDES for part in rel.parts)


def should_exclude_from_magic(filepath: Path, root: Path) -> bool:
    """Check if a file should be excluded from magic-number checks."""
    rel = filepath.relative_to(root)
    return any(part in MAGIC_NUMBER_EXCLUDES for part in rel.parts)


def run_command(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=120,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=cmd, returncode=127, stdout="", stderr=f"Command not found: {cmd[0]}"
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=cmd, returncode=124, stdout="", stderr="Command timed out"
        )


def print_separator(title: str) -> None:
    """Print a section separator."""
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def print_summary(results: list[GateResult]) -> None:
    """Print a summary table of all gate results."""
    print_separator("QUALITY GATE SUMMARY")

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        symbol = "✓" if r.passed else "✗"
        print(f"  {symbol} [{status}] {r.name}")

    print(f"\n  Total: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 60}")

    if failed > 0:
        print("\nFailed gates:")
        for r in results:
            if not r.passed:
                print(f"\n  {r}")
        print("\n" + "=" * 60)
        print("  Fix the issues above and re-run: python scripts/quality_gate.py")
        print("=" * 60)


def main() -> int:
    """Run all quality gates and return exit code."""
    import sys as _sys

    _scripts_dir = str(Path(__file__).resolve().parent)
    if _scripts_dir not in _sys.path:
        _sys.path.insert(0, _scripts_dir)
    from quality_gate_checks import (
        gate_banned_patterns,
        gate_dependency_direction,
        gate_except_pass,
        gate_file_size,
        gate_lint,
        gate_magic_numbers,
        gate_types,
    )

    print_separator("Archipelago Quality Gate (Skill 4 — 5-pass review)")
    print(f"  Root: {ROOT}")
    print(f"  Max file lines: {MAX_FILE_LINES}")
    print(f"{'=' * 60}")

    results: list[GateResult] = []

    print("\n--- Pass 1: Lint ---")
    results.append(gate_lint(ROOT))
    print(results[-1])

    print("\n--- Pass 2: Types ---")
    results.append(gate_types(ROOT))
    print(results[-1])

    print("\n--- Pass 3: Banned patterns ---")
    results.append(gate_banned_patterns(ROOT))
    print(results[-1])

    print("\n--- Pass 3b: Magic numbers ---")
    results.append(gate_magic_numbers(ROOT))
    print(results[-1])

    print("\n--- Pass 4: Architecture ---")
    results.append(gate_file_size(ROOT))
    print(results[-1])
    results.append(gate_dependency_direction(ROOT))
    print(results[-1])
    results.append(gate_except_pass(ROOT))
    print(results[-1])

    print_summary(results)

    failed = sum(1 for r in results if not r.passed)
    if failed > 0:
        print(f"\n  ✗ {failed} gate(s) failed — code does not meet quality standards.")
        return 1

    print(f"\n  ✓ All {len(results)} gates passed — code meets quality standards.")
    print("  Pass 5 (human review) is required before merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
