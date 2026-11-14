# S5 Multi-Source Scholarly Provider Validation Report

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Production Backend:** `https://archipelago-blond.vercel.app`  
**Preview Deployment:** `https://archipelago-l7ihqkcd9-archipelago-6383.vercel.app`  
**Policy:** Zero paper, author, or journal ranking; zero composite quality scores; zero Google Scholar scraping or CAPTCHA/PoW bypasses.

---

## 1. Provider Capability Matrix (Phase 1 & Phase 2)

| Provider | API Availability | Auth Requirements | Supported Entities | Rate Limits / Constraints | Terms / Licensing | Current Integration |
|---|---|---|---|---|---|---|
| **OpenAlex** | `api.openalex.org/works`, `/authors`, `/sources` | Polite `mailto:` recommended; optional API key | Works, Authors, Institutions, Sources, Topics, Grants, OA | 10 req/s polite pool; 50-ID batch filters | CC0 metadata | **Live** (`openalex_adapter.py`, `enrichment.py`) |
| **Crossref** | `api.crossref.org/works` | Polite `mailto:` (`User-Agent`) | DOIs, Journals, Proceedings, Publishers, References, Grants | Polite pool ~50 req/s | Public metadata API | **Live** (`crossref_adapter.py`) |
| **Semantic Scholar** | `api.semanticscholar.org/graph/v1/paper/search` | Optional `x-api-key` (`SEMANTIC_SCHOLAR_API_KEY`) | Papers, Author IDs, Citations, Abstracts, OA PDFs | Strict shared unauth burst limits (`HTTP 429`); no aggressive retry | S2 API Terms | **Live** (`live_sources.py`) |
| **arXiv** | `export.arxiv.org/api/query` | None | CS/Math/Physics preprints, versioned IDs, abstracts, categories | 1 req / 3s recommended | arXiv API Terms | **Live** (`arxiv_adapter.py`) |
| **DBLP** | `dblp.org/search/publ/api` | None documented; currently fronted by **Anubis JS PoW (`HTTP 202`)** | CS conferences/journals, DBLP keys, author PIDs, DOI/EE links | Bot-protection challenge blocks non-browser clients | CC0 metadata | **Implemented + Gate-Detected** (`extended_sources.py` surfaces `blocked_bot_challenge` without bypassing) |
| **OpenAIRE** | `api.openaire.eu/graph/v1/researchProducts` | Public REST API | Research products, Projects, Funding links, Organizations, OA | Standard polite HTTP limits | OpenAIRE Graph CC-BY | **Live** (`extended_sources.py`) |
| **OpenCitations** | `api.opencitations.net/index/v2/citation-count/doi:` | Public REST API (optional token) | DOI-linked external citation counts & citing/cited links | Rate-limited (`429` handled gracefully) | CC0 citation data | **Live** (`extended_sources.py`, `search.py`) |
| **DataCite** | `api.datacite.org/dois` | Public REST API | Dataset & Software DOIs, Creators, Publishers, Related IDs, Grants | Standard REST pagination | CC0 metadata | **Live** (`extended_sources.py`) |
| **Europe PMC** | `ebi.ac.uk/europepmc/webservices/rest/search` | Public REST API | Biomedical papers, PMIDs, PMCIDs, abstracts, affiliations, OA URLs | Polite REST limits | EMBL-EBI Open | **Live** (`biomed_sources.py`) |
| **PubMed / NCBI** | `eutils.ncbi.nlm.nih.gov/entrez/eutils/` | Optional `NCBI_API_KEY` | PMIDs, DOIs, journals, publication dates, authors | 3 req/s (10 req/s with key) | NLM/NCBI Public | **Live** (`biomed_sources.py`) |
| **ORCID** | `pub.orcid.org/v3.0/{orcid}/person` | Public Read API | Verified researcher names/records by ORCID (no name-based merging) | Standard polite limits | ORCID Public | **Live** (`biomed_sources.py`) |
| **Google Scholar** | No public search API | Manual researcher browser only | Outbound topic link + user-exported **BibTeX / RIS** import (`USER_IMPORTED_GOOGLE_SCHOLAR`) | Never scraped; never automated | Compliant manual workflow | **Live** (`scholar_import.py`, `/api/research/intelligence/import`) |

---

## 2. Live Seven-Topic Multi-Provider Acceptance Results

All 7 topics were executed live against documented APIs (`s5_multisource_validation.json`) with domain-aware provider selection (`provider_selector.py`), conservative deduplication (`canonicalizer.py`), OpenCitations external citation lookup, and 14-sheet workbook generation:

| Topic | Domain Profile | Queried Providers (Live Status) | Candidates -> Filtered -> Selected | Multi-Source Merged | OpenCitations Enriched | Author Obs. | Claims | 14-Sheet Workbook | Elapsed (ms) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `graph neural networks` | `ai_cs` | OpenAlex (25), arXiv (25), Crossref (13), S2 (`429`), DBLP (`202 gate`) | 63 -> 44 -> 20 | 0 | 8 | 37 | 47 | 14/14 | 14,360.2 |
| `retrieval-augmented generation` | `ai_cs` | OpenAlex (23), arXiv (25), Crossref (30), S2 (`429`), DBLP (`202 gate`) | 77 -> 69 -> 20 | 0 | 8 | 29 | 73 | 14/14 | 11,353.5 |
| `continual learning` | `ai_cs` | OpenAlex (26), arXiv (25), Crossref (28), S2 (`429`), DBLP (`202 gate`) | 76 -> 76 -> 20 | 0 | 8 | 31 | 47 | 14/14 | 11,153.6 |
| `bengali speech recognition` | `ai_cs` | OpenAlex (15), arXiv (25), Crossref (36), S2 (`429`), DBLP (`202 gate`) | 67 -> 45 -> 20 | 4 | 8 | 15 | 46 | 14/14 | 10,678.4 |
| `biomedical ai` | `biomedical` | OpenAlex (22), S2 (40), Europe PMC (25), PubMed (20), Crossref (15) | 95 -> 74 -> 20 | 5 | 8 | 39 | 38 | 14/14 | 12,601.3 |
| `research datasets software` | `datasets_software` | OpenAlex (12), DataCite (30), Crossref (21), OpenAIRE (30) | 92 -> 79 -> 20 | 0 | 8 | 2 | 28 | 14/14 | 9,835.1 |
| `jarvis ai` | `ai_cs` | arXiv (25), Crossref (23), OpenAlex (`504`), S2 (`429`), DBLP (`202 gate`) | 48 -> 15 -> 15 | 0 | 8 | 0 | 4 | 14/14 | 14,146.8 |

---

## 3. Negative Tests & Automated Suite

`ruff check` passed cleanly and **51/51** pytest tests passed across:
- `tests/unit/test_s5_multisource_providers.py` (6/6): Domain selection & skip reasons, DBLP JSON & Anubis HTTP 202 gate detection, OpenAIRE/DataCite/Europe PMC/PubMed/OpenCitations parsing + HTTP 429 handling, ORCID verified lookup, conservative no-title-merge deduplication, valid + malformed BibTeX/RIS Google Scholar import, and Research Chat provider/duplicate/external-citation queries.
- `tests/unit/test_s5_research_intelligence.py` (13/13)
- `tests/unit/test_s6_platform_integration.py` (7/7)
- `tests/unit/test_host_inference_deployment.py` (18/18)
- `tests/unit/test_research_transport.py` (5/5)
- `tests/integration/test_s4_academic_dashboard.py` (2/2)
