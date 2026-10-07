# Inference links and graph handoff — 2026-10-07

## Built

- Expanded grounded chat replies and source lists to as many as six indexed pages, with readable title and page labels. Added XKIRO to NVIDIA fallback with pacing and rate-limit cooldown.
- Showed the normal concept graph for diagnostic and curated concept prompts by default, with clearer quiz and graph controls.
- Fixed legacy Hugging Face PDF path resolution when the manifest has duplicate basenames. The in-app reader uses the approved dataset path and offers an official Hub file link.
- Removed the imported Pearson page-count rejection. Verified that eLibrary reflowable books use `viewer.html` and corrected that book link. The handoff retains the requested page number and makes no unverified exact-page claim.

## Verification

- 52 focused unit tests passed.
- Changed Python modules passed `ruff check`; changed JavaScript modules passed `node --check`.
- Local HTTP checks returned 200 for readiness, Pearson page 822 handoff, and Hugging Face page 4 reader metadata.

## Next pair

- Pearson eLibrary catalog records need official internal page IDs or an institutional deep-link integration before exact-page redirects can be verified.
- The Hugging Face dataset requires a valid Hub session for the official link; the app PDF proxy uses its configured dataset credential.
