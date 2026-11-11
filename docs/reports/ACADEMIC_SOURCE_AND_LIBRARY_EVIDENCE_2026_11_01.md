# Academic source and Library_books research evidence — 2026-11-01

## Source decision

The live academic graph is a published inference snapshot. It will not gain new concepts from browsing alone. An academic source needs to be fetched, attributed, chunked, extracted, relation-checked, reviewed, merged into the staging graph, and republished.

1. **Wikibooks Algorithms** is the first staged academic candidate. [The book](https://en.wikibooks.org/wiki/Algorithms) is a featured Wikibooks work. Its [Introduction](https://en.wikibooks.org/wiki/Algorithms/Introduction) explicitly lists prerequisite programming and data-structure knowledge. [Wikibooks copyright policy](https://en.wikibooks.org/wiki/Wikibooks:Copyrights) allows text reuse under CC BY-SA 4.0 with attribution and share-alike obligations. The page was fetched through Archipelago's existing allowlist and robots gate and staged as /tmp/archipelago-wikibooks-algorithms-introduction.md. It has **not** been merged into the graph. The source's named prerequisite relation is a review candidate, not a validated edge.
2. [Open Textbook Library](https://open.umn.edu/opentextbooks) is a source discovery directory. Each title needs its own license and access check before ingestion.
3. **OpenStax Introduction to Computer Science is excluded from automatic ingestion.** Its [current attribution terms](https://openstax.org/books/introduction-computer-science/pages/preface) explicitly require prior permission for use in large language models or generative AI offerings despite the book's free online reading access.
4. The Koha OPAC remains bibliographic discovery. Its holdings do not supply full text.

The new source-staging script accepts only HTTPS Algorithms chapter pages on en.wikibooks.org. It checks robots/allowlist policy, extracts prose, and writes attribution plus license metadata for the librarian review workflow. No broad crawl or graph mutation occurs.

## Research paper path

The local research worker already saves source records in Supabase and per-paper OKF in Prataykarali/graphier. It now exports a separate bounded paper catalogue to the private Prataykarali/Library_books dataset. Each record includes original source/DOI pointers and up to eight verified field values; raw abstracts, long evidence quotes, private user IDs, and PDFs are omitted.

The main chat now tries to read a matching paper's job export directly from Library_books on the server, using HF_TOKEN. When present, it answers with those bounded verified facts and an original paper link. A signed-in student or staff member can open the exact paper's Library evidence through /api/library/paper-evidence/<record_key>; the Hugging Face token stays server-side. When the export or token is unavailable, chat retains its existing Supabase excerpt fallback and does not pretend the HF artifact exists.

This design keeps search in Supabase and uses Hugging Face as the durable evidence archive. Private HF blob URLs would not work for ordinary student accounts, so the authenticated app endpoint serves the selected evidence row.

## Verification and release state

- The Wikibooks Introduction fetch passed the existing source gate and produced an attributed local review artifact.
- 20 targeted tests passed across private HF evidence selection, student/anonymous API boundary, chat use of HF facts, repository routing, and research worker behavior.
- Targeted Ruff checks passed after import formatting. The broader repository gate is still red from existing baseline issues, and the working tree contains extensive unrelated changes.
- No new research job, graph merge, HF upload, or Vercel deployment was performed. Hosted chat cannot use this new HF path until the code is released and HF_TOKEN is configured there.
