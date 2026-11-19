# Stage S5 — Single Human-to-Final-Paper Handoff Runbook

**Canonical Repository:** `/home/pratay-karali/Desktop/archipelago`  
**Git-Ignored Private Root (`.gitignore:141`):** `data/annotation_local/s5c3/` *(NEVER store private workbooks, source passages, or human submissions under tracked `research/` paths)*  
**Current Governance Status:** **`HOLD`** — Real Stage S5-D1 effectiveness evaluation has **NOT** been executed.  
**Historical Reviewer A Recovery Status (`S5_MODULE1_RECOVERY_AND_PRESERVATION.md`):** Original Reviewer A workbook (`SHA-256: 70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`) was **NOT FOUND** anywhere on disk. Historical Reviewer A comparison is **`BLOCKED`** (see Section 13 for exact recovery paths; zero grades may ever be reconstructed or synthesized).  
**Legacy Contract Preservation:** Original Reviewer B provenance (`AI_ASSISTED_OR_GENERATED`, excluded from A/C v2 gold) and `research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py` (v1 contract) remain intact and untouched.

---

## 1. Exact Private Files to Complete

All private human-authored files reside strictly inside the Git-ignored directory `data/annotation_local/s5c3/`:

| # | Private File Path (Git-Ignored) | Purpose | Created / Edited By |
|---|---|---|---|
| 1 | `data/annotation_local/s5c3/workbench/reviewer_a_session.json` *(or externally supplied backup matching exact SHA-256 `70049fa8...`)* | Reviewer A's 254-pair blinded annotation session (required because original `70049fa8...` was not found on disk) | Reviewer A (`REV_A`) via Module 2 UI |
| 2 | `data/annotation_local/s5c3/submissions/reviewer_a_s5c3_submission.json` (+ `.csv`, `_sha256_manifest.json`) | Exported, validated, human-signed Reviewer A submission (`s5c3_human_submission_v1`) | Reviewer A (`REV_A`) via Module 2 CLI |
| 3 | `data/annotation_local/s5c3/workbench/reviewer_c_session.json` | Independent Reviewer C's 254-pair blinded annotation session | Reviewer C (`REV_C`) via Module 2 UI |
| 4 | `data/annotation_local/s5c3/submissions/reviewer_c_s5c3_submission.json` (+ `.csv`, `_sha256_manifest.json`) | Exported, validated, human-signed Reviewer C submission (`s5c3_human_submission_v1`) | Reviewer C (`REV_C`) via Module 2 CLI |
| 5 | `data/annotation_local/s5c3/adjudication/s5c3_ac_worksheet.json` (+ `.md`) | Generated A/C disagreement list & human adjudication worksheet (generated ONLY after both `REV_A` and `REV_C` pass validation) | Human Adjudicator via Module 3 UI |
| 6 | `data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json` (+ `_EXPORT.md`, `.sha256.json`) | Corpus-wide human negative-control verification worksheet for `Q-S5B2-03`, `Q-S5B2-08`, and `Q-S5B2-11` | Independent Human Verifier via Module 4 UI/CLI |
| 7 | `data/annotation_local/s5c3/submissions/investigator_signoff.json` | Signed investigator sign-off approving assembled A/C v2 gold labels | Principal Investigator |
| 8 | `data/annotation_local/s5c3/submissions/s5d1_gold_ac_v2_FINAL.json` | Assembled final `s5d1_adjudicated_gold_ac_v2` gold-label file (generated ONLY after all checks pass) | Principal Investigator via Module 3 CLI |
| 9 | `data/annotation_local/s5c3/submissions/s5d1_investigator_authorization.json` | Signed investigator D1 authorization artifact binding exact SHA-256 hashes of gold + negative-control files | Principal Investigator (from `--print-auth-template`) |
| 10 | `data/annotation_local/s5c3/d1_real/s5d1_preflight_real.json` & `s5d1_eval_report_real.json` | Real preflight report and manually authorized S5-D1 evaluation report | Principal Investigator via Module 5 CLI |

*(Note: Pre-existing blank Markdown templates in `data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md`, `s5c3_negative_control_verification_worksheets.md`, and `REVIEWER_A_PROVENANCE_ATTESTATION_TEMPLATE.md` are preserved with `0444` backups in `immutable_blank_backups/`; use the structured Module 2–4 local workbenches below so every export is cryptographically hashed and schema-validated.)*

---

## 2. Which Human Role Completes Which Form

| Human Role | Forms / Artifacts Owned | Blinding & Independence Rules |
|---|---|---|
| **Reviewer A (`REV_A`)** | `reviewer_a_session.json` → `reviewer_a_s5c3_submission.json` (OR external original workbook verified to exact SHA-256 `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` + signed provenance attestation) | Must work strictly blinded outside Git history access; zero AI relevance suggestions; must truthfully sign human provenance declaration. |
| **Reviewer C (`REV_C`)** | `reviewer_c_session.json` → `reviewer_c_s5c3_submission.json` | Must be a genuinely independent human with zero prior exposure to `REV_A`, `REV_B`, system identities, or retrieval rankings; zero AI assistance. |
| **Human Adjudicator** | `s5c3_ac_worksheet.json` (resolving every A/C disagreement with written human rationale) | Independent human or designated adjudicator; must verify verbatim quotes against frozen passage text; zero AI-generated adjudication; must sign adjudicator provenance. |
| **Negative-Control Verifier** | `s5c3_negative_control_verification.json` (`Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11`) | Independent human inspecting the frozen eligible 713-passage corpus (`s5a_eval_corpus_v1`); must never rely on automated regex/dense outputs alone; must sign verifier provenance. |
| **Principal Investigator** | `investigator_signoff.json`, `s5d1_gold_ac_v2_FINAL.json` assembly, `s5d1_investigator_authorization.json`, authorized S5-D1 run, final manuscript `TODO-00`..`TODO-17` completion | Verifies all SHA-256 manifests and preflight gates; explicitly authorizes real S5-D1 execution; reviews all permanent pilot non-claims before compilation. |

---

## 3. How Reviewers Save and Export Judgments (Module 2)

Both `REV_A` (if completing a fresh blinded annotation) and `REV_C` use the offline, `127.0.0.1`-only local annotation workbench (`research/s5-c3-human-adjudication-prep/scripts/s5_annotation_workbench.py`). Non-loopback hosts are rejected; zero external CDNs, AI suggestions, or prior-reviewer hints exist in the UI.

1. **Launch the local browser UI** (replace `reviewer_c` with `reviewer_a` and use a separate session file for Reviewer A):
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_annotation_workbench.py serve \
     --host 127.0.0.1 --port 5058 \
     --session data/annotation_local/s5c3/workbench/reviewer_c_session.json
   ```
   Open `http://127.0.0.1:5058` in a local browser.
2. **Grade all 254 blinded pairs** (`0` = Irrelevant with empty quote; `1` = Partially Relevant with exact verbatim substring quote; `2` = Highly Relevant with exact verbatim substring quote), record confidence (`HIGH`/`MEDIUM`/`LOW`) and notes, and save/resume progress at any time.
3. **Check live completion count and provenance status:**
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_annotation_workbench.py status \
     --session data/annotation_local/s5c3/workbench/reviewer_c_session.json
   ```
4. **Create a timestamped private backup + `.sha256` sidecar:**
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_annotation_workbench.py backup \
     --session data/annotation_local/s5c3/workbench/reviewer_c_session.json
   ```
5. **Sign the human provenance panel** inside the UI (never auto-populated or auto-signed), then **validate and export** JSON + CSV + SHA-256 manifest:
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_annotation_workbench.py validate \
     --session data/annotation_local/s5c3/workbench/reviewer_c_session.json

   python3 research/s5-c3-human-adjudication-prep/scripts/s5_annotation_workbench.py export \
     --session data/annotation_local/s5c3/workbench/reviewer_c_session.json \
     --output-dir data/annotation_local/s5c3/submissions \
     --prefix reviewer_c_s5c3
   ```
   Repeat the exact same steps for Reviewer A using `--session data/annotation_local/s5c3/workbench/reviewer_a_session.json` and `--prefix reviewer_a_s5c3` (unless an external backup matching exact SHA-256 `70049fa8...` is supplied and verified).

---

## 4. How to Verify Provenance

Before generating disagreements or assembling gold labels, verify that every submission carries truthful, signed, independent-human provenance (`provenance_class == "INDEPENDENT_HUMAN"`, `assistance_declaration == "NONE_INDEPENDENT_HUMAN"`, `human_attestation_confirmed == true`) and matches the frozen 254-pair pool (`SHA-256: 2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037`):

```bash
python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-submission \
  --submission data/annotation_local/s5c3/submissions/reviewer_a_s5c3_submission.json \
  --role REV_A

python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-submission \
  --submission data/annotation_local/s5c3/submissions/reviewer_c_s5c3_submission.json \
  --role REV_C
```

Verify file integrity against the exported SHA-256 manifests (`*_sha256_manifest.json`) using `sha256sum`. Any submission that is incomplete (`< 254` pairs), unsigned, missing verbatim quotes, altered in passage text, or flagged as `AI_ASSISTED_OR_GENERATED` is automatically rejected.

---

## 5. How A/C Disagreements Are Generated (Module 3)

Run the A/C comparison **only after** both `REV_A` and `REV_C` pass `validate-submission` (the CLI refuses to run if either reviewer is missing, incomplete, unsigned, or AI-assisted):

```bash
python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py compare \
  --rev-a data/annotation_local/s5c3/submissions/reviewer_a_s5c3_submission.json \
  --rev-c data/annotation_local/s5c3/submissions/reviewer_c_s5c3_submission.json \
  --output-worksheet data/annotation_local/s5c3/adjudication/s5c3_ac_worksheet.json \
  --output-markdown data/annotation_local/s5c3/adjudication/s5c3_ac_worksheet.md
```

This computes descriptive A/C inter-annotator agreement (exact agreement, unweighted $\kappa$, quadratic weighted $\kappa$) and writes a blank human adjudication worksheet containing every A/C disagreement.

---

## 6. How Humans Adjudicate Disagreements (Module 3)

1. **Launch the offline `127.0.0.1`-only adjudication browser UI:**
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py serve-ui \
     --worksheet data/annotation_local/s5c3/adjudication/s5c3_ac_worksheet.json \
     --port 5063
   ```
   Open `http://127.0.0.1:5063` locally.
2. For every disagreement, the human adjudicator inspects the frozen passage text, both reviewers' grades and quotes, selects the `final_grade` (`0`, `1`, or `2`), provides a verified verbatim `supporting_quotation` (for grades `1`–`2`; blank for `0`), and writes a mandatory human `adjudication_rationale`.
3. The adjudicator signs the human provenance attestation inside the UI (never auto-signed).
4. **Validate the completed adjudication worksheet:**
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-adjudication \
     --worksheet data/annotation_local/s5c3/adjudication/s5c3_ac_worksheet.json \
     --rev-a data/annotation_local/s5c3/submissions/reviewer_a_s5c3_submission.json \
     --rev-c data/annotation_local/s5c3/submissions/reviewer_c_s5c3_submission.json
   ```

---

## 7. How Negative Controls Are Verified (Module 4)

Independent human verification of `Q-S5B2-03`, `Q-S5B2-08`, and `Q-S5B2-11` is strictly restricted to the frozen eligible corpus (`s5a_eval_corpus_v1`, 713 passages / 53 documents, `corpus_sha256: 6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`).

*(Prerequisite: Pass `--db-path okf_graph.db` once the local Kùzu database is present, OR pass `--corpus-json <VERIFIED_CORPUS_JSON>` matching `corpus_sha256` if using a frozen corpus snapshot. Excluded/out-of-corpus passages are rejected with exit code 2 / HTTP 403.)*

1. **Initialize the blank private worksheet (with backup + SHA-256):**
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_negative_control_verifier.py init \
     --db-path okf_graph.db \
     --output data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json
   ```
2. **Launch the offline `127.0.0.1`-only verification UI** (or use CLI `search` / `inspect`):
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_negative_control_verifier.py serve \
     --db-path okf_graph.db \
     --worksheet data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json \
     --host 127.0.0.1 --port 8767
   ```
   Optional CLI corpus search & inspection (logs searches directly into the worksheet):
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_negative_control_verifier.py search \
     --db-path okf_graph.db --query "<TERM>" --mode substring \
     --worksheet data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json \
     --query-id Q-S5B2-03

   python3 research/s5-c3-human-adjudication-prep/scripts/s5_negative_control_verifier.py inspect \
     --db-path okf_graph.db --list-docs
   ```
3. For each of `Q-S5B2-03`, `Q-S5B2-08`, and `Q-S5B2-11`, the human verifier records `human_answerability_classification`, `d1_evaluation_impact`, `external_factual_premise_assessment`, `corpus_scope_checked`, `verification_rationale`, supporting excerpts, and signs `human_provenance` (`INDEPENDENT_HUMAN`).
4. **Validate and export Markdown + SHA-256 backup:**
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_negative_control_verifier.py validate \
     --db-path okf_graph.db \
     --worksheet data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json

   python3 research/s5-c3-human-adjudication-prep/scripts/s5_negative_control_verifier.py export \
     --db-path okf_graph.db \
     --worksheet data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json \
     --output-md data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification_EXPORT.md
   ```
   Confirm `valid: true` and `ready_for_d1: true`.

---

## 8. How the Investigator Approves Final Gold (Module 3 + Module 5)

1. **Create the investigator sign-off JSON** (`data/annotation_local/s5c3/submissions/investigator_signoff.json`) containing `investigator_id`, explicit `approval_declaration`, `human_signoff_confirmed: true`, and `signed_timestamp_utc`.
2. **Assemble and validate `s5d1_gold_ac_v2_FINAL.json`:**
   ```bash
   python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py assemble-gold \
     --rev-a data/annotation_local/s5c3/submissions/reviewer_a_s5c3_submission.json \
     --rev-c data/annotation_local/s5c3/submissions/reviewer_c_s5c3_submission.json \
     --worksheet data/annotation_local/s5c3/adjudication/s5c3_ac_worksheet.json \
     --neg-controls data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json \
     --investigator-signoff data/annotation_local/s5c3/submissions/investigator_signoff.json \
     --output data/annotation_local/s5c3/submissions/s5d1_gold_ac_v2_FINAL.json

   python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-gold \
     --gold data/annotation_local/s5c3/submissions/s5d1_gold_ac_v2_FINAL.json
   ```
3. **Generate the blank D1 investigator authorization template** (never auto-signed):
   ```bash
   python3 research/s5-d0-experimental-analysis-prep/scripts/s5_d1_evaluate.py --print-auth-template \
     > data/annotation_local/s5c3/submissions/s5d1_investigator_authorization.json
   ```
   Fill in `investigator_id`, explicit approval declaration, UTC timestamp, and the exact `sha256sum` digests of `s5d1_gold_ac_v2_FINAL.json` and `s5c3_negative_control_verification.json`.

---

## 9. Exact Tested Commands to Validate Real Human Inputs

Run the full validation chain before authorizing S5-D1 (every command must exit `0`):

```bash
# 1. Validate REV_A and REV_C submissions
python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-submission \
  --submission data/annotation_local/s5c3/submissions/reviewer_a_s5c3_submission.json --role REV_A
python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-submission \
  --submission data/annotation_local/s5c3/submissions/reviewer_c_s5c3_submission.json --role REV_C

# 2. Validate completed human adjudication
python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-adjudication \
  --worksheet data/annotation_local/s5c3/adjudication/s5c3_ac_worksheet.json \
  --rev-a data/annotation_local/s5c3/submissions/reviewer_a_s5c3_submission.json \
  --rev-c data/annotation_local/s5c3/submissions/reviewer_c_s5c3_submission.json

# 3. Validate corpus-wide human negative-control verification
python3 research/s5-c3-human-adjudication-prep/scripts/s5_negative_control_verifier.py validate \
  --db-path okf_graph.db \
  --worksheet data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json

# 4. Validate assembled A/C v2 gold JSON against schema + semantic gates
python3 research/s5-c3-human-adjudication-prep/scripts/s5_ac_adjudication.py validate-gold \
  --gold data/annotation_local/s5c3/submissions/s5d1_gold_ac_v2_FINAL.json

# 5. Run Stage S5-D1 preflight validator on real human inputs
python3 research/s5-d0-experimental-analysis-prep/scripts/s5_d1_preflight.py \
  --gold-labels data/annotation_local/s5c3/submissions/s5d1_gold_ac_v2_FINAL.json \
  --neg-control-file data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json \
  --schema-mode ac_v2 \
  --output data/annotation_local/s5c3/d1_real/s5d1_preflight_real.json
```

*(For dry-run testing without real human data, `--synthetic-demo` on `s5_d1_preflight.py` and `--synthetic-only` on `s5_d1_evaluate.py` write `SYNTHETIC_`-prefixed outputs into `data/annotation_local/s5c3/d1_synthetic/`.)*

---

## 10. Exact Manually Authorized D1 Execution Command

Execute **ONLY** after Section 9 preflight exits `0` AND the Principal Investigator has signed `s5d1_investigator_authorization.json`:

```bash
python3 research/s5-d0-experimental-analysis-prep/scripts/s5_d1_evaluate.py \
  --authorize-real-d1 \
  --auth-artifact data/annotation_local/s5c3/submissions/s5d1_investigator_authorization.json \
  --gold-labels data/annotation_local/s5c3/submissions/s5d1_gold_ac_v2_FINAL.json \
  --neg-control-file data/annotation_local/s5c3/negative_control/s5c3_negative_control_verification.json \
  --schema-mode ac_v2 \
  --output data/annotation_local/s5c3/d1_real/s5d1_eval_report_real.json
```

Then generate the reproducible Markdown, LaTeX, and CSV tables (9 files) plus SVG figures (2 files):

```bash
python3 research/s5-d0-experimental-analysis-prep/scripts/s5_d1_tables_figures.py \
  --eval-report data/annotation_local/s5c3/d1_real/s5d1_eval_report_real.json \
  --output-dir data/annotation_local/s5c3/d1_real/tables_and_figures
```

Verify that `is_synthetic` is `false` in `s5d1_eval_report_real.json` and that **zero** generated filenames carry a `SYNTHETIC_` prefix or watermark.

---

## 11. How Results, Tables, and Figures Enter the Manuscript

Use `research/s5-e0-pre-results-paper-prep/manuscript/MANUSCRIPT_TODO_MANIFEST.md` as the exact 1-to-1 checklist to replace `TODO-00` through `TODO-17` in `research/s5-e0-pre-results-paper-prep/manuscript/manuscript_draft.md`:

- **Tables (`data/annotation_local/s5c3/d1_real/tables_and_figures/`):**
  - `system_effectiveness_summary.{md,tex,csv}` → `§11.1` (`TODO-05`)
  - `fallback_and_shortlist_accounting.{md,tex,csv}` → `§11.3` (`TODO-07`) and `§11.6` (`TODO-10`)
  - `one_hop_vs_two_hop_comparison.{md,tex,csv}` → `§11.4` (`TODO-08`)
  - Query-level metrics and negative-control behavior from `s5d1_eval_report_real.json` → `§11.2` (`TODO-06`) and `§11.5` (`TODO-09`)
- **Figures (`data/annotation_local/s5c3/d1_real/tables_and_figures/`):**
  - `fig1_system_effectiveness.svg` and `fig2_fallback_vs_nonfallback.svg` → `§11.7` (`TODO-11`). Copy only aggregate non-private figures (containing zero source passages) into `research/s5-e0-pre-results-paper-prep/manuscript/figures/` before embedding.
- **Narrative & Provenance Sections:**
  - Fill `TODO-00` (authors), `TODO-01` (Abstract), `TODO-02` (C5), `TODO-03` (A/C IAA & adjudication), `TODO-04` (negative controls), `TODO-12`–`TODO-14` (Discussion RQ1–RQ3), `TODO-15` (Limitations update), `TODO-16` (Conclusions), and `TODO-17` (final SHA-256 hashes, never committing private passage text).
- **Mandatory Integrity Check:** Preserve all permanent non-claims in `§4.3` (no statistical significance tests, no superiority claims, no cross-document multi-hop claims, no large-scale/GPU extrapolation).

---

## 12. How to Compile the Final Paper

`manuscript_draft.md` and `references.bib` are intentionally venue-neutral. Once all 18 checklist items (`TODO-00`–`TODO-17`) in `MANUSCRIPT_TODO_MANIFEST.md` are checked off:

1. **Venue-neutral PDF / DOCX / LaTeX export via Pandoc** (if `pandoc` and `xelatex`/`pdflatex` are installed):
   ```bash
   cd research/s5-e0-pre-results-paper-prep/manuscript
   pandoc manuscript_draft.md \
     --bibliography=references.bib \
     --citeproc \
     --pdf-engine=xelatex \
     -o archipelago_s5_pilot_final.pdf
   ```
2. **Target-venue LaTeX compilation (once a venue is selected):**
   - Convert `manuscript_draft.md` to `.tex` via `pandoc manuscript_draft.md --biblatex -o manuscript_body.tex` (or drop the generated `.tex` tables from `tables_and_figures/*.tex` directly into the chosen venue's template).
   - Compile with `pdflatex` / `bibtex` / `pdflatex` / `pdflatex` against `references.bib`.
   - Re-check the 2 flagged preprints in `BIBLIOGRAPHY_AUDIT.md` (`merrick2024arctic`, `edge2024local`) for archival venue updates before final submission.
3. **Final privacy check before sharing or committing:** Run `git status` and confirm zero files from `data/annotation_local/` or raw textbook/paper passages are tracked or staged.

---

## 13. All HOLD Conditions and Recovery Steps

Real S5-D1 evaluation and final paper compilation remain strictly **`HOLD`** if **any** of the following conditions apply:

| # | HOLD Condition | Exact Effect | Required Recovery Step |
|---|---|---|---|
| **H1** | **Original Reviewer A workbook (`70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`) NOT FOUND on disk** *(ACTIVE)* | Historical Reviewer A comparison is **`BLOCKED`**. You MUST NOT reconstruct, infer, or synthesize Reviewer A's historical grades. | Reviewer A must either: **(a)** supply an external backup file whose `sha256sum` matches `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` exactly (plus signed provenance attestation), **OR (b)** complete a fresh blinded 254-pair annotation via Module 2 (`s5_annotation_workbench.py`) before running A/C comparison. |
| **H2** | **`okf_graph.db` absent in local workspace** *(ACTIVE after directory flattening)* | Module 4 (`s5_negative_control_verifier.py`) cannot open `--db-path okf_graph.db` directly, and `test_precomputed_embeddings_cache_validity` fails locally. | Restore/mount the local `okf_graph.db` snapshot (untracked) OR pass `--corpus-json <PATH>` pointing to a verified `s5a_eval_corpus_v1` JSON snapshot whose `corpus_sha256` matches `6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`. |
| **H3** | **Incomplete or unvalidated `REV_A` or `REV_C` submission** (`< 254` pairs, missing verbatim quotes, altered passage text, or unsigned provenance) | `s5_ac_adjudication.py compare` refuses to generate disagreements. | Complete missing pairs/quotes and sign human provenance in Module 2 (`s5_annotation_workbench.py`), re-export, and re-run `validate-submission`. |
| **H4** | **AI-assisted or AI-generated labels in `REV_A`, `REV_C`, adjudication, or negative-control verification** | Rejected automatically by Module 3, Module 4, and Module 5 preflight (`AI_ASSISTED_OR_GENERATED` is never accepted as independent human gold). | Quarantine AI-assisted file; have an independent human re-grade/re-verify from a clean blank session with truthful provenance. |
| **H5** | **Unadjudicated A/C disagreements or missing human rationales** | `validate-adjudication` and `assemble-gold` refuse to produce `s5d1_gold_ac_v2_FINAL.json`. | Launch Module 3 `serve-ui`, resolve every remaining disagreement with a verified quote and written human rationale, sign adjudicator provenance, and re-validate. |
| **H6** | **Unverified negative controls (`HOLD_UNVERIFIED_NEGATIVE_CONTROL`) or reclassification conflict** | Module 4 reports `ready_for_d1: false`; Module 5 preflight fails. If human verification reclassifies `Q-S5B2-03`, `08`, or `11` as answerable/ambiguous/requiring revision, metric stratification changes. | Complete corpus-wide inspection and signed human classification for all 3 queries in Module 4; verify Module 5 preflight explicitly logs any reclassification impact before authorizing D1. |
| **H7** | **Missing or hash-mismatched Investigator Authorization Artifact** | `s5_d1_evaluate.py` refuses real execution and stays in `--synthetic-only` / dry-run mode. | Recompute `sha256sum` of `s5d1_gold_ac_v2_FINAL.json` and `s5c3_negative_control_verification.json`, update `s5d1_investigator_authorization.json`, sign with `investigator_id` + UTC timestamp, and pass `--authorize-real-d1`. |
| **H8** | **Synthetic output accidentally referenced in manuscript** | Violates scientific integrity; `SYNTHETIC_` prefix/watermarks must never enter final results. | Delete any synthetic files from manuscript directories; re-run Section 10 on real authorized inputs and verify `is_synthetic: false`. |
| **H9** | **Private data or source passages detected in `git status`** | Violates copyright and blinding governance (`LIM-09`). | Immediately unstage (`git reset HEAD <file>`), move the file under Git-ignored `data/annotation_local/s5c3/`, and re-verify `git status`. |
