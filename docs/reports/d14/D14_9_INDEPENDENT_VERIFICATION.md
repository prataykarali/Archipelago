# D14.9 verification independence and integrity — 2026-11-28

This is same-coder verification, not independent review. The existing `D14_BENCHMARK_EXPOSURE_AUDIT.json` inventories 45 protected files. Rehashing the listed paths gave 44 matches and one absent file: `outputs/d11-a-author-diagnostic/D11_A_AUTHOR_DIAGNOSTIC_WORKSHEET.xlsx`. No held-out query content was opened or run. Checksums cannot prove absence of prior benchmark exposure. A separate primary-author-controlled post-merge leakage audit remains outstanding.

The historical 731-item `human_annotation_worksheet.json` was structurally inspected without evaluating query content: every `reviewer_assessment` field is null. The V2 graph's 1,943 edges all have `PENDING_REVIEW`; zero are human verified. The claimed 120-row blank D14 review packet is absent from this checkout. The local V3 corpus and V2 graph match their reported SHA-256 values; historical versions were not modified. No manuscript file was edited in this task. No research Supabase write, protected alias change, or UEM production action occurred.

Verification limits: hosted parity failed; application browser access was denied at Vercel protection; source rights are not proven per document; the eight-query challenge has no recorded completion; scientific claims remain unvalidated by human reviewers. The held-out 50-query benchmark stays locked.
