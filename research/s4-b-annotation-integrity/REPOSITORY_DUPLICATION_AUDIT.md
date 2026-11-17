# Archipelago — Read-Only Repository Duplication & Mirror Audit

**Scope:** Inspection of `archipelago/`, `host_inference/archipelago/`, `frontend/ui`, `ui`, and `host_research/ui`.  
**Status:** Read-only audit. No files were deleted, moved, consolidated, or automatically synchronized.

---

## 1. Directory Overview & Structure

| Directory Tree | File Count | Purpose / Deployment Target |
| :--- | :---: | :--- |
| `archipelago/` | 400 | Canonical core Python library (evaluation, ingestion, scholarly search, models, resolver). |
| `host_inference/archipelago/` | 31 | Mirrored subset of `archipelago` required for standalone container runtime (`AntDeploy`). |
| `ui/` | 144 | Main application frontend UI assets, templates, stylesheets, and scripts. |
| `host_inference/ui/` | 146 | Frontend assets bundled inside the hosted inference service container. |
| `host_research/ui/` | 38 | Research-specific UI pages, templates, and analytics views. |
| `frontend/ui/` | 50 | Legacy / alternative web UI assets and graph visualizer scripts. |

---

## 2. Component Duplication Analysis

### A. Python Backend: `archipelago/` vs `host_inference/archipelago/`
- **Exact Duplicates (27 files):**
  - Includes core utilities: `archipelago/scholarly/discovery/openalex.py`, `arxiv.py`, `crossref.py`, `semanticscholar.py`, `archipelago/scholarly/graph.py`, `models.py`, `storage.py`, `workbook.py`, etc.
- **Divergent Mirrors (3 files):**
  1. `scholarly/pipeline/__init__.py` (canonical exports full pipeline components; mirror has minimal stubs for standalone inference).
  2. `scholarly/discovery/__init__.py` (canonical exports all search engines; mirror exports minimal subset).
  3. `scholarly/intelligence/workbook_extra.py` (*detailed investigation in Section 3 below*).
- **Unique Files:**
  - `archipelago/`: 370 canonical files (full evaluation harness, baseline runners, scrapers, training pipeline, Kuzu graph schemas).
  - `host_inference/archipelago/`: 1 file (`__init__.py` wrapper tailored for container execution).

### B. Frontend UI: `ui/` vs `host_inference/ui/`
- **Exact Duplicates (4 files):** Shared core icons/fonts.
- **Divergent Mirrors (14 files):**
  - Binary image/button assets (`assets/search_btn.png`, `note_btn2.png`, `brain_btn.png`, `landing_hero_curious.jpg`, etc.) have differing compression levels or updated branding between local development and hosted release.
- **Differences:**
  - `ui/` contains 126 files specific to local development and extended views.
  - `host_inference/ui/` contains 128 files customized with hosted endpoints and bundled scripts.

### C. Frontend UI: `ui/` vs `host_research/ui/`
- **Exact Duplicates:** 0
- **Divergent:** 0
- **Assessment:** `host_research/ui/` contains 38 distinct HTML/JS files specifically dedicated to research intelligence pages (`research_pages/papers.html`, `authors.html`, `topics.html`, etc.). They do not overlap or conflict with `ui/`.

### D. Frontend UI: `frontend/ui/` vs `ui/`
- **Exact Duplicates (37 files):** Shared graph visualization libraries, CSS stylesheets, and core UI icons.
- **Divergent Mirrors (5 files):**
  - `assets/library_goit.mp4`, `assets/library_type.mp4`, `graph/index.html`, `graph/js/00-escape-html.js`, `graph/js/02-build-concept-graph.js`.
- **Unique to `frontend/ui/`:** 8 legacy files.

---

## 3. Investigation: Why `workbook_extra.py` Differs

A line-by-line diff and Git history inspection revealed the precise reason:

```bash
diff -u archipelago/scholarly/intelligence/workbook_extra.py host_inference/archipelago/scholarly/intelligence/workbook_extra.py
```

### Git Provenance:
- Commit `a9c6b8a` originally added `workbook_extra.py` identically to both paths.
- On `Sat Nov 14 17:46:50 2026`, commit `9fe796d` (*"feat(quota,chat,security): rolling 10/hr student quota, library routing, graph provenance, workbook & analytics fixes"*) made targeted updates to canonical `archipelago/scholarly/intelligence/workbook_extra.py`:
  1. Added helper function `_linked_author_id(paper, idx)` to resolve author IDs consistently across OpenAlex and local graph models using `from .graph import author_key`.
  2. Preserved normalized institution names via `seen_inst_names.setdefault(...)`.
  3. Associated institutional records with linked author IDs.
- **Root Cause of Divergence:**
  `host_inference` is deployed as an isolated container root via AntDeploy (`host_inference` image root). Because `host_inference` has its own release cycle and tests (`test_host_log_redaction.py`), the update was made on the canonical branch and not back-ported to the container mirror.

---

## 4. Runtime Dependencies & Cleanup Strategy

### Runtime Dependencies:
- **`archipelago/`:** The single source of truth for the scientific evaluation harness, baseline experiments, benchmarks, and model training.
- **`host_inference/archipelago/`:** Hard runtime dependency for standalone hosted service deployment. Cannot be removed without refactoring AntDeploy build configuration.
- **`ui/` vs `host_inference/ui/`:** `host_inference/hostapp` serves files from `host_inference/ui/` at runtime.

### Safe Future Cleanup Candidates (Post-CIKM):
1. **Single Source Packaging:** Package `archipelago` as an installable wheel/package so `host_inference` installs it directly rather than keeping an un-synced vendored copy in `host_inference/archipelago/`.
2. **Synchronize `workbook_extra.py`:** Back-port the author linking and institution normalization improvements to `host_inference/archipelago/scholarly/intelligence/workbook_extra.py`.
3. **Consolidate `frontend/ui/`:** Deprecate `frontend/ui/` in favor of `ui/` after verifying that no external static build scripts depend on the `frontend/` path prefix.

---

## 5. Untracked Artifacts & Recommended `.gitignore` Rules

The working tree contains several generated workbooks, run logs, local databases, and temporary screenshots:

### Files Observed:
- `data/research_intelligence.sqlite3` (Local SQLite database)
- `data/catalogs/cron_harvest.log` (Harvesting log)
- `artifacts/validation/*.xlsx` (Generated test spreadsheets)
- `artifacts/validation/final-research-demo/` (Demo exports and patched runs)
- `artifacts/validation/final-ui-audit/browser/*.png` (Automated browser test screenshots)
- `outputs/research-overhaul-20261116/` (Evaluation run artifacts)

### Recommended `.gitignore` Additions:
```gitignore
# Local SQLite and operational logs
data/*.sqlite3
data/**/*.log

# Generated test and export workbooks
artifacts/validation/*.xlsx
outputs/**/*.xlsx
outputs/**/*.png
outputs/**/*.json

# UI audit browser screenshots
artifacts/validation/final-ui-audit/browser/*.png
```
*(As per instructions, these files have NOT been deleted or committed).*
