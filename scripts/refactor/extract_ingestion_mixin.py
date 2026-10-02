"""Extract IngestionWorker._process_job into a JobProcessingMixin module."""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path("ingestion_worker.py")
MIXIN = Path("ingestion_worker_job_mixin.py")

text = SRC.read_text(encoding="utf-8")
tree = ast.parse(text)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "IngestionWorker")
meth = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_process_job")
segment = ast.get_source_segment(text, meth) or ""
assert segment.count("\n") > 300, "method block unexpectedly small"

mixin = '''"""JobProcessingMixin: staged pipeline job processing for IngestionWorker.

Split out of ingestion_worker.py to keep every file under 400 lines; the
method body is byte-identical to the original.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from ingestion_jobs import JobStatus
from okf.config import BASE_DIR
from okf.exports import export_vis_json
from okf.pipeline import PipelineAborted, run_pipeline_staged


class JobProcessingMixin:
''' + segment + "\n"

MIXIN.write_text(mixin, encoding="utf-8")

lines = text.splitlines(keepends=True)
start, end = meth.lineno, meth.end_lineno
new_cls_line = "class IngestionWorker(threading.Thread, JobProcessingMixin):"
out: list[str] = []
for i, line in enumerate(lines, 1):
    if i == cls.lineno:
        out.append(new_cls_line + "\n")
    elif start <= i <= end:
        continue
    elif line.strip() == "class IngestionWorker(threading.Thread):":
        continue
    else:
        out.append(line)
new_text = "".join(out)
# Add the mixin import right after the ingestion_jobs import line.
new_text = new_text.replace(
    "from ingestion_jobs import JobStatus, JobStore\n",
    "from ingestion_jobs import JobStatus, JobStore\n\n"
    "from ingestion_worker_job_mixin import JobProcessingMixin\n",
)
SRC.write_text(new_text, encoding="utf-8")
print(f"mixin: {len(mixin.splitlines())} lines")
print(f"ingestion_worker.py: {len(new_text.splitlines())} lines")
ast.parse(new_text)
ast.parse(mixin)
print("both parse OK")
