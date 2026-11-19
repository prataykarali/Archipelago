# S5-C3 — Disagreement Adjudication & Text-Discrepancy Reconciliation Protocol

**Stage:** S5-C3-P0 (Human Adjudication Preparation)  
**Date:** 2026-11-19  
**Status:** `AWAITING_HUMAN_ADJUDICATION` (0 of 51 disagreements resolved)

---

## 1. Private 51-Item Disagreement Packet (Git-Ignored Only)

Generated reproducibly from preserved S5-C2 originals and canonical `okf_graph.db` text without modifying either original workbook:
- `data/annotation_local/s5c3/s5c3_disagreement_adjudication_packet_51.md` (`SHA-256: 09ee9242ae4b1443ea8ba8f633c1f4925849b7c0b7bf6792ec480be1785099a5`)
- `data/annotation_local/s5c3/s5c3_disagreement_adjudication_packet_51.json` (`SHA-256: db8d185884657fffaad91ca54f9a4dbcc58764d20c6a70ecf38dc00b5cd79ae6`)

### 1.1 Per-Item Contents (51 Items)
- Frozen `pair_id`, `query_id`, `domain`, exact `query_text`, canonical `doc_id` / `chunk_id` / `page_number`, and `passage_sha256`
- Canonical frozen passage text hydrated directly from `okf_graph.db` (`s5a_eval_corpus_v1`)
- Preserved original `REV_A` grade, quote, confidence, and notes (unchanged)
- Preserved original `REV_B` grade, quote, confidence, and notes (unchanged, explicitly tagged `AI_ASSISTED_OR_GENERATED — unconfirmed`)
- **Blank** adjudication fields: `adjudicated_grade`, `adjudication_evidence_quote`, `adjudication_rationale`, `adjudicator_id`, `decision_date_utc`, and `provenance_class`

### 1.2 Disagreement Distribution Across Queries (Total = 51 / 254)
- `Q-S5B2-01`: 4 | `Q-S5B2-02`: 7 | `Q-S5B2-03`: 0 | `Q-S5B2-04`: 9 | `Q-S5B2-05`: 10 | `Q-S5B2-06`: 5 | `Q-S5B2-07`: 8 | `Q-S5B2-08`: 0 | `Q-S5B2-10`: 8 | `Q-S5B2-11`: 0.
- Breakdown by original grade pair (`REV_A` → `REV_B`): `(0, 1)`: 34; `(1, 0)`: 4; `(1, 2)`: 4; `(2, 1)`: 9; `(0, 2)` and `(2, 0)`: 0.

---

## 2. Human Adjudication Rules

1. **Canonical Text Authority:** Adjudicate strictly against the **canonical `okf_graph.db` passage text** displayed in the packet, never against external memory or unverified document pages.
2. **No Automatic Resolution:** No script, majority vote, or LLM may fill `adjudicated_grade` or `adjudication_rationale`.
3. **Quote Enforcement:** Any adjudicated grade of `1` or `2` MUST include an exact verbatim substring from the canonical passage; adjudicated grade `0` MUST leave `adjudication_evidence_quote` blank.
4. **Provenance Honesty:** Because `REV_B` disclosed AI assistance on 254/254 pairs, adjudicating `REV_A` vs. `REV_B` alone does **not** satisfy dual-independent-human reliability. Under the Primary Path ([S5C3_REVIEWER_ASSIGNMENT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c3-human-adjudication-prep/S5C3_REVIEWER_ASSIGNMENT.md)), an independent human `REV_C` grades all 254 pairs first, and `REV_A` vs. `REV_C` disagreements are adjudicated under this same rubric.

---

## 3. Reconciliation of Five Passage-Text Discrepancies (Metadata-Only Public Summary)

S5-C2 identified **5 passage-text discrepancies** between original reviewer workbooks and canonical `okf_graph.db` (`REV_A`: 2, `REV_B`: 3). All 5 have been reconciled against canonical `okf_graph.db` in private Git-ignored `data/annotation_local/s5c3/s5c3_text_discrepancy_reconciliation_5.md` (`SHA-256: 08a49bdf013141faf7b7afbf9d0d5f409011f164935db03b48e2e9975c237101`) **without modifying either original workbook**:

| Pair ID | Query ID | Reviewer | Passage ID | Char Delta | Root Cause (Verified Against `okf_graph.db`) | Reviewer Grade | Grade Disagreement? | Quote Valid? |
|---|---|---|---|---:|---|---:|---|---|
| `S5B21-PAIR-091` | `Q-S5B2-04` | `REV_B` | `papers/bahdanau2014_attention.pdf::chunk_008` | `0` | 1 embedded PDF NUL byte (`0x00`) replaced with `U+FFFD` on save | `0` | No (`0` / `0`) | Yes (blank) |
| `S5B21-PAIR-119` | `Q-S5B2-05` | `REV_B` | `papers/karpukhin2020_dpr.pdf::chunk_031` | `0` | 3 embedded PDF NUL bytes (`0x00`) replaced with `U+FFFD` on save | `0` | No (`0` / `0`) | Yes (blank) |
| `S5B21-PAIR-134` | `Q-S5B2-06` | `REV_B` | `papers/bahdanau2014_attention.pdf::chunk_008` | `0` | 1 embedded PDF NUL byte (`0x00`) replaced with `U+FFFD` on save | `0` | No (`0` / `0`) | Yes (blank) |
| `S5B21-PAIR-189` | `Q-S5B2-08` | `REV_A` | `papers/willard2023_outlines.pdf::chunk_011` | `-1` | 1 backslash escape (`\`) stripped by rich-text editor on save | `0` | No (`0` / `0`) | Yes (blank) |
| `S5B21-PAIR-232` | `Q-S5B2-11` | `REV_A` | `papers/willard2023_outlines.pdf::chunk_011` | `-1` | 1 backslash escape (`\`) stripped by rich-text editor on save | `0` | No (`0` / `0`) | Yes (blank) |

**Reconciliation Finding:** All 5 discrepancies are benign editor encoding/escaping artifacts involving zero semantic text alteration, all 5 pairs received agreed grade `0`, and none overlap with the 51 grade disagreements. Both original workbooks remain preserved byte-identically (`REV_A`: `70049fa8...`; `REV_B`: `ca3e6af8...`).
