# S5 author and venue validation

The graph-neural-networks live Top-20 retained 83 author rows and 11 venue rows in the workbook. Seventy-nine author occurrences carried provider ORCID values; this count includes repeats across papers and is not a count of distinct verified people. Authors without ORCID are keyed to their paper and name, so same-name strangers cannot be merged by default. OpenAlex supplied affiliation names where available. Historical versus current affiliation is unknown.

Venue names and optional publisher text come from paper metadata. ISSN, Journal Impact Factor, CiteScore, SJR, CORE rank and acceptance rate are blank because no authorized metric provider was integrated. No venue citation count is relabeled as an impact factor. Publication counts, h-index and i10-index are blank for authors; direct author-profile enrichment and independent identity review remain deferred. These omissions are visible in the workbook rather than fabricated.
