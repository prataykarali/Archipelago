# S5-C2 Annotation Validation Report

**Date:** 2026-11-19
**Dataset Pool:** `s5b2_1_proposed_pooled_v2.1_pending_approval` (254 pairs across 10 queries)

## 1. Preserved Original Evidence & Methodology Disclosure

| Reviewer | Preserved Git-Ignored Path | SHA-256 | AI-Assisted Notes | Independence Status |
|---|---|---|---:|---|
| **Reviewer A (`REV_A`)** | `data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` | `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` | 0 / 254 | No AI-assistance disclosure in notes |
| **Reviewer B (`REV_B`)** | `data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md` | `ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4` | 254 / 254 | **AI-assisted proposed annotations** (`requires independent human confirmation`); independence from AI suggestions not yet documented |

> [!WARNING]
> Reviewer B's notes explicitly state `AI-assisted proposed annotation; requires independent human confirmation` on all 254 pairs. These annotations are NOT reported as independent blind human judgments.

## 2. Programmatic Validation Results

| Check | Reviewer A (`REV_A`) | Reviewer B (`REV_B`) |
|---|---:|---:|
| Expected / Parsed Pairs | 254 / 254 | 254 / 254 |
| Missing Pairs | 0 | 0 |
| Duplicate Pairs | 0 | 0 |
| Invalid Grades (outside `0,1,2`) | 0 | 0 |
| Invalid Confidence (outside `HIGH,MEDIUM,LOW`) | 0 | 0 |
| Passage ID Mismatches | 0 | 0 |
| SHA-256 Hash Mismatches | 0 | 0 |
| Source Text Discrepancies | 2 | 3 |
| Missing Quotes for Grades 1 & 2 | 0 | 0 |
| Non-Empty Quotes for Grade 0 | 0 | 0 |
| Quote Exact Substring Matches | 70 | 100 |
| Quote Whitespace-Normalized Matches | 0 | 0 |
| Quote Substring Mismatches | 0 | 0 |

### Source & Quote Discrepancy Notes
- **Reviewer A quote mismatches (0):** None
- **Reviewer B quote mismatches (0):** None
- **Grade distributions:** `REV_A` = {0: 184, 1: 44, 2: 26}; `REV_B` = {0: 154, 1: 79, 2: 21}.
