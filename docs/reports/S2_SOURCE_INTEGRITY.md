# S2 source integrity report

## Scope and findings

This checkout is `feature/s2a-academic-coverage-repair`, with existing uncommitted changes. It was not rebased onto `session3-stable`. S2 changes stay in reply, evidence and catalog presentation code; graph persistence, OPAC sync and research discovery were not edited.

The local Koha file `data/koha/Titles List with specified keyword-reportresults.ods` is an export snapshot, last modified 2026-10-03 15:01:07 UTC. It contains 108 parsed title keys, primarily journal records. It does not establish physical holdings for the sample AI/CS textbooks. Local catalog replies therefore report those book holdings as unverified. The hosted `library_book_inventory.csv` is metadata only: its embedded counts and shelves are no longer treated as verified holdings. A live Koha integration is not present in this evidence path.

The requested `host_inference/engine/gap_resources.py` file is absent from this checkout. The active hosted inventory paths are `inventory_card.py`, `inventory.py`, `catalogue.py`, and `compose.py`.

## Contract

`evidence_record` retains available bibliographic, page, provider, timestamp, verification and access fields. Ingested local PDFs are linked only when the file and requested physical page exist. DOI records link to a DOI target without a fabricated PDF page. Book metadata has no stock claim. Koha copy counts are labeled `Catalog snapshot` with the export file timestamp. Separate observations with different values or timestamps remain separate.

Inline citations use the validated URL and a deduplicated Sources listing. The local page viewer no longer substitutes a demo summary when a chunk is absent. The demo citation overlay no longer creates query-dependent sources.

## Rendered examples

Before: `[S1] Hu2021_LoRA.pdf, PDF page 4` (plain source footer).

After: `[S1: BERT, PDF p.2](/api/page-view?doc_id=papers%2FDevlin2018_BERT.pdf&page=2#page=2)` and `[S2: Verified Paper](https://doi.org/10.1000/example)`.

Before: `Operating Systems: Three Easy Pieces — 4 of 7 available, OS-01` (static hosted inventory text).

After: `Not verified in the catalog snapshot. Search the OPAC.` for physical book inventory with no matching Koha export row.

For journal inventory, the rendered table has title, author, edition/ISBN, call number, copies, available and OPAC search link. An example row is `Journal of human resource management | — | — | — | 3 | 3 | OPAC search`, marked as a 2026-10-03 export snapshot, not current availability.

## Verification

- S2 acceptance tests: 7 passed, including exact Koha fixture, metadata-only book, local PDF page, DOI-only record, multi-source synthesis, unknown document/book, and conflicting timestamps.
- Citation, S1, local library, and hosted route selection: 131 passed in the final combined run.
- Local library integration: 4 passed in isolation. A mixed run before isolation hit four Flask setup-order errors because another test module issued a request before all route decorators were imported; the tests pass when run as their own integration module.
- Focused Ruff checks, formatting, and `git diff --check` pass on S2 changes.
- Repository-wide `scripts/quality_gate.py` still fails on unrelated lint/format issues, a strict-type baseline of 891 errors, and eight files above its 400-line threshold. The edited hosted `compose.py` is 448 lines after splitting (below the `AGENTS.md` 500-line limit, above the gate's stricter 400-line threshold).

## Known limitations

The supplied export cannot verify live availability. An OPAC search URL is an action to check a title, not proof of a matching record. DOI syntax and publication metadata are only as trustworthy as the upstream scholarly record; this change does not perform live DOI resolution. The hosted catalog currently has no authoritative live Koha response. Source disagreement is preserved in records, but the reply engine does not yet produce a full comparative narrative for every conflicting metadata field.
