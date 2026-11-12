# S5 author and venue validation

The graph-neural-networks live Top-20 retained 83 author rows and 11 venue rows in the workbook. Seventy-nine author occurrences carried provider ORCID values; this count includes repeats across papers and is not a count of distinct verified people. Authors without ORCID are keyed to their paper and name, so same-name strangers cannot be merged by default. OpenAlex supplied affiliation names where available. Historical versus current affiliation is unknown.

Venue names and optional publisher text come from paper metadata. ISSN, Journal Impact Factor, CiteScore, SJR, CORE rank and acceptance rate are blank because no authorized metric provider was integrated. No venue citation count is relabeled as an impact factor. Publication counts, h-index and i10-index are blank for authors; direct author-profile enrichment and independent identity review remain deferred. These omissions are visible in the workbook rather than fabricated.

## S5-B update, 2026-11-12

OpenAlex work responses now preserve source ID, type, ISSN, URL and open-access status when supplied. Selected paper rows expose `venue_details`; the Venues worksheet uses the same provider facts. Proprietary impact factor, CiteScore, SJR and CORE values remain N/A. The research UI states this explicitly.

Author enrichment now looks up only validated OpenAlex author IDs attached to a paper authorship, with a bounded lookup count and timeout. It records provider, retrieval time, OpenAlex corpus coverage, works count, citation count, h-index, i10-index, ORCID when supplied, and dated affiliation observations when supplied. It never searches or merges authors by name. Lookup failures and ID mismatches leave metrics unavailable. A live OpenAlex author endpoint returned HTTP 200 with provider-supplied summary statistics during local validation. An independent human identity audit and cross-provider author reconciliation remain pending.
