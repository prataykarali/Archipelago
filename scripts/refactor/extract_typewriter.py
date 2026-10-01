"""Extract the self-contained stream helpers out of ``08-send-message.js``.

``sendMessage`` is one long function; the typewriter class and the two pure
predicates inside it have no closure dependencies, so they move to
``stream-support.js`` verbatim.  This keeps the extraction byte-faithful.

Usage::

    python scripts/refactor/extract_typewriter.py ui/chat/js --dry-run
    python scripts/refactor/extract_typewriter.py ui/chat/js --write
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

CLASS_MARK = "class SmoothTypewriterStream {"
CLASS_END_MARK = "// No status chip — stream the model reply directly."
UTILS_START_MARK = "const _normText = (s) =>"
UTILS_END_MARK = "finalizeStreamedBubble = () => {"

HEADER = """// Stream rendering helpers extracted from send-message.
// SmoothTypewriterStream paints grounded text word-by-word, and the two
// predicates decide whether a late model rewrite should replace first paint.
"""


def dedent(text: str) -> str:
    lines = text.splitlines()
    trimmed = [line[16:] if line.startswith(" " * 16) else line for line in lines]
    return textwrap.dedent("\n".join(trimmed)).strip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("js_dir", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    source_path = args.js_dir / "08-send-message.js"
    text = source_path.read_text(encoding="utf-8")

    class_start = text.index(CLASS_MARK)
    class_end = text.rindex("\n", 0, text.index(CLASS_END_MARK, class_start))
    class_text = dedent(text[class_start:class_end])

    utils_start = text.index(UTILS_START_MARK)
    utils_end = text.rindex("\n", 0, text.index(UTILS_END_MARK, utils_start))
    utils_text = dedent(text[utils_start:utils_end])

    module = (
        HEADER
        + "\n"
        + class_text
        + "\n\n"
        + utils_text
        + "\n\nexport { SmoothTypewriterStream, _normText, _shouldReplaceFinal };\n"
    )
    print(f"stream-support.js: {len(module.splitlines())} lines")
    print(f"08-send-message.js: {len(text.splitlines())} -> "
          f"{len(text[:class_start].splitlines()) + len(text[class_end:utils_start].splitlines()) + len(text[utils_end:].splitlines())} lines")

    if not args.write:
        print("(dry run)")
        return 0

    (args.js_dir / "stream-support.js").write_text(module, encoding="utf-8")
    # Remove the class block and the utils block, leaving a single blank line.
    remaining = text[:class_start] + "\n" + text[class_end:utils_start] + "\n" + text[utils_end:]
    import_line = (
        "import { SmoothTypewriterStream, _normText, _shouldReplaceFinal } "
        "from './stream-support.js';\n"
    )
    anchor = "import { saveSession } from './20--compact-history.js';\n"
    remaining = remaining.replace(anchor, anchor + import_line, 1)
    source_path.write_text(remaining, encoding="utf-8")
    print("written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
