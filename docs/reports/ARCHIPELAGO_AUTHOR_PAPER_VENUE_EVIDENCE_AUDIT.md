# ARCHIPELAGO — AUTHOR, PAPER & VENUE EVIDENCE AUDIT

## 1. Paper Verification & Deduplication
- Preprint-to-published collapse in `search.py` (`by_work`) now keys on `(normalize_title, first_author)` without requiring identical years, preferring `published` over `preprint` and preserving `alternate_dois`.
- Europe PMC (`biomed_sources.py`) now detects `preprint` via `pubType` and preprint DOI prefixes (`10.21203/rs.`, `10.1101/`, `10.48550/arxiv.`).
- Scientific content fields (`methods`, `datasets`, `evaluation_metrics`, `code_repo_urls`, `dataset_repo_urls`) are extracted strictly from accessible titles/abstracts with `PRESENT_WITH_EVIDENCE` / `NOT_FOUND_IN_AVAILABLE_EVIDENCE` / `SOURCE_NOT_ACCESSIBLE`.

## 2. Author Identity & Enrichment
- OpenAlex batched author enrichment (`enrich_authors`) + bounded Semantic Scholar (`enrich_s2_authors`) + ORCID verification (`enrich_orcid_authors`).
- Same-name collisions without matching provider IDs/ORCID are preserved separately and flagged `IDENTITY_REVIEW_REQUIRED` (`detect_author_collisions`).
- Paper-specific affiliations and `current_affiliations` are stored separately.

## 3. Venue & Google Research / Scholar Provenance
- `classify_venue_category` distinguishes `peer_reviewed_journal`, `peer_reviewed_conference`, `workshop`, `preprint_repository`, and `institutional_listing`; licensed metrics (JIF, CiteScore, SJR, CORE) remain `LICENSE_RESTRICTED`.
- Google Research (`google_research.py`) separates `GOOGLE_RESEARCH_OFFICIAL_LISTING` from `GOOGLE_AUTHOR_AFFILIATION` and `GOOGLE_COLLABORATOR`.
- Google Scholar links are outbound search links only; unavailable metrics are `NOT_AVAILABLE`.
