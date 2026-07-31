#!/usr/bin/env python3
"""Quality gate check functions (Skill 4 — 5-pass review).

This module contains the individual gate check functions used by
``scripts/quality_gate.py``. It is imported lazily by the main entry point
to avoid circular imports.

Each gate function returns a ``GateResult`` indicating pass/fail with
details about any violations found.
"""

from __future__ import annotations

from pathlib import Path
import re
from shutil import which as shutil_which

from quality_gate import (
    BANNED_PATTERNS,
    FORBIDDEN_IMPORTS,
    MAGIC_NUMBER_EXCEPTIONS,
    MAGIC_NUMBER_PATTERN,
    MAX_FILE_LINES,
    GateResult,
    find_python_files,
    run_command,
    should_exclude_from_banned,
    should_exclude_from_magic,
)


def gate_lint(root: Path) -> GateResult:
    """Pass 1: Lint — ruff check + ruff format --check."""
    result = GateResult(name="Pass 1: Lint (ruff)")

    ruff = shutil_which("ruff")
    if ruff is None:
        result.passed = False
        result.details.append("ruff not found — install with: pip install ruff")
        return result

    check = run_command([ruff, "check", str(root)])
    if check.returncode != 0:
        result.passed = False
        result.details.append("ruff check failed:")
        for line in check.stdout.strip().splitlines()[:20]:
            result.details.append(f"  {line}")
    else:
        result.details.append("ruff check: OK")

    fmt = run_command([ruff, "format", "--check", str(root)])
    if fmt.returncode != 0:
        result.passed = False
        result.details.append("ruff format --check failed:")
        for line in fmt.stdout.strip().splitlines()[:20]:
            result.details.append(f"  {line}")
    else:
        result.details.append("ruff format --check: OK")

    if not result.details:
        result.details.append("All lint checks passed")

    return result


def gate_types(root: Path) -> GateResult:
    """Pass 2: Types — mypy --strict."""
    result = GateResult(name="Pass 2: Types (mypy)")

    mypy = shutil_which("mypy")
    if mypy is None:
        result.passed = False
        result.details.append("mypy not found — install with: pip install mypy")
        return result

    cmd = [mypy, "--strict", "archipelago/", "okf/"]
    proc = run_command(cmd, cwd=str(root))
    if proc.returncode != 0:
        result.passed = False
        result.details.append("mypy --strict failed:")
        for line in proc.stdout.strip().splitlines()[-30:]:
            result.details.append(f"  {line}")
    else:
        result.details.append("mypy --strict: OK")

    return result


def gate_banned_patterns(root: Path) -> GateResult:
    """Pass 3: Banned patterns — auto-fail list from AGENTS.md."""
    result = GateResult(name="Pass 3: Banned patterns")

    files = find_python_files(root)
    total_violations = 0

    for filepath in files:
        if should_exclude_from_banned(filepath, root):
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        rel_path = filepath.relative_to(root)
        for pattern in BANNED_PATTERNS:
            matches = pattern.matches(content)
            if matches:
                total_violations += len(matches)
                for line_no, line in matches:
                    result.details.append(
                        f"{rel_path}:{line_no} [{pattern.name}] {pattern.description}"
                    )
                    result.details.append(f"  → {line.strip()}")

    if total_violations > 0:
        result.passed = False
        result.details.insert(0, f"Found {total_violations} banned pattern violation(s)")
    else:
        result.details.append("No banned patterns found")

    return result


def gate_magic_numbers(root: Path) -> GateResult:
    """Detect magic numbers (literals that aren't 0, 1, or -1)."""
    result = GateResult(name="Pass 3b: Magic numbers")

    files = find_python_files(root)
    total_violations = 0

    for filepath in files:
        if should_exclude_from_magic(filepath, root):
            continue

        try:
            lines = filepath.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue

        rel_path = filepath.relative_to(root)
        for line_no, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue

            for match in MAGIC_NUMBER_PATTERN.finditer(line):
                num_str = match.group(1)
                num_val = int(num_str)
                if num_val in (0, 1):
                    continue
                if num_val in MAGIC_NUMBER_EXCEPTIONS:
                    continue
                before = line[: match.start()]
                quote_count = before.count('"') + before.count("'")
                if quote_count % 2 == 1:
                    continue

                total_violations += 1
                result.details.append(f"{rel_path}:{line_no} magic number: {num_str}")
                result.details.append(f"  → {line.strip()}")

    if total_violations > 0:
        result.passed = False
        result.details.insert(0, f"Found {total_violations} magic number(s)")
        result.warnings.append(
            "Define named constants for non-trivial literals. Exception: 0, 1, -1 are allowed."
        )
    else:
        result.details.append("No magic numbers found")

    return result


def gate_file_size(root: Path) -> GateResult:
    """Check that no Python file exceeds MAX_FILE_LINES."""
    result = GateResult(name="Pass 4a: File size (≤500 lines)")

    files = find_python_files(root)
    violations: list[str] = []

    for filepath in files:
        try:
            line_count = len(filepath.read_text(encoding="utf-8").splitlines())
        except (UnicodeDecodeError, OSError):
            continue

        if line_count > MAX_FILE_LINES:
            rel_path = filepath.relative_to(root)
            violations.append(f"{rel_path}: {line_count} lines (max {MAX_FILE_LINES})")

    if violations:
        result.passed = False
        result.details.append(f"Found {len(violations)} file(s) exceeding {MAX_FILE_LINES} lines:")
        for v in violations:
            result.details.append(f"  {v}")
    else:
        result.details.append(f"All files within {MAX_FILE_LINES} line limit")

    return result


def gate_dependency_direction(root: Path) -> GateResult:
    """Check that features import downward only: apps → inference / okf."""
    result = GateResult(name="Pass 4b: Dependency direction")

    files = find_python_files(root)
    violations: list[str] = []

    for filepath in files:
        rel_path = filepath.relative_to(root)
        module_path = ".".join(rel_path.with_suffix("").parts)

        package = None
        if module_path.startswith("archipelago.inference"):
            package = "archipelago.inference"
        elif module_path.startswith("archipelago.ingestion"):
            package = "archipelago.ingestion"
        elif module_path.startswith("okf"):
            package = "okf"
        elif module_path.startswith("archipelago.apps"):
            package = "archipelago.apps"

        if package is None:
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        forbidden = FORBIDDEN_IMPORTS.get(package, [])
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for forbidden_import in forbidden:
                if forbidden_import in stripped:
                    violations.append(
                        f"{rel_path}:{line_no} [{package}] forbidden import: {stripped}"
                    )

    if violations:
        result.passed = False
        result.details.append(f"Found {len(violations)} dependency direction violation(s):")
        for v in violations:
            result.details.append(f"  {v}")
    else:
        result.details.append("All imports follow downward-only dependency rules")

    return result


def gate_except_pass(root: Path) -> GateResult:
    """Check for except: pass and except Exception: pass patterns."""
    result = GateResult(name="Pass 4c: No except: pass")

    files = find_python_files(root)
    violations: list[str] = []

    except_pass_patterns = [
        re.compile(r"^\s*except\s*:\s*pass"),
        re.compile(r"^\s*except\s+Exception\s*:\s*pass"),
    ]

    for filepath in files:
        try:
            lines = filepath.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue

        rel_path = filepath.relative_to(root)
        for line_no, line in enumerate(lines, start=1):
            for pattern in except_pass_patterns:
                if pattern.match(line):
                    violations.append(f"{rel_path}:{line_no} {line.strip()}")

    if violations:
        result.passed = False
        result.details.append(f"Found {len(violations)} except: pass violation(s):")
        for v in violations:
            result.details.append(f"  {v}")
    else:
        result.details.append("No except: pass patterns found")

    return result
