# S5 provider capability audit

OpenAlex, Crossref, arXiv and Semantic Scholar are accessed through the repository's existing fixed HTTPS API endpoints. No Google Scholar scraping is performed. ORCID values are retained when source metadata supplies them; direct ORCID reconciliation is deferred.

The eight captured live runs are under `artifacts/validation/s5-research-intelligence/`. OpenAlex, Crossref and arXiv returned live records in all eight. Semantic Scholar returned HTTP 429 in these final runs, with its status and request ID retained. Provider coverage is partial; returned Top-K is not global literature completeness. The earlier first graph-neural-networks call also returned OpenAlex 25, Crossref 13 and arXiv 25 records, with Semantic Scholar 429.

Author affiliations are retained when provided by OpenAlex. Citation counts remain provider-attributed observations, not paper quality scores. OpenAlex reference IDs support verified citation edges among selected works. Crossref and Semantic Scholar reference enrichment is not yet available in this path. Publisher metrics requiring licensed access are left unavailable.
