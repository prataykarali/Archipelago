"""Archipelago CLI entry point.

Usage:
    python -m archipelago ingest --source <file>
    python -m archipelago graph validate
    python -m archipelago graph stats
    python -m archipelago graph diff --baseline <file>
    python -m archipelago model download --repo <org/model> --revision <version>
"""

from archipelago.cli import main

if __name__ == "__main__":
    main()
