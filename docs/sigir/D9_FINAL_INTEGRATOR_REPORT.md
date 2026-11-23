# D9 final integrator report — 2026-11-23

## Scope and privacy

D9 integrates reproducibility code, generic statistical tables, and research
reports. The SIGIR manuscript TeX, bibliography, PDF, manuscript figures, and
older manuscript draft are absent from this branch's tracked head. The complete
manuscript package is delivered only under the author's local
`/home/pratay-karali/Desktop/sigit_manu/` directory. This report contains
no manuscript text or rendered copy.

The D9 figures branch (`81d8d42`), statistics branch (`3f9b98a`), and
integration base (`236526b`) each have privacy deletion commits. The
integration merge commit before this report is `058a196`. All have ordinary
history; no force-push or rewrite occurred. The former evaluation manuscript
branch also has a deletion commit (`65b690a`). Other older public heads and
historical Git/LFS/PR exposure are documented in the local
`reports/HISTORY_CLEANUP_ASSESSMENT.md`.

## Reproducibility and corrections

- Frozen held-out query SHA-256:
  `9e39430942b4f00d34911848cbe61a96532c29ffaee76f0d82ce69496f71103a`.
- Frozen algorithmic qrels SHA-256:
  `b3e55ab147907940c6cd90ea5273284558037363066c4cfdd199efa0743bc8a2`.
- Graph fixture SHA-256:
  `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`.
- Frozen Archipelago TREC run SHA-256:
  `61e425fa7add8d97375efc1417cb3585514cfd9efaa41fbc010f57bb4444fabe`.
- Q45 is the frozen compiler question, with a Pearson compiler-book metadata
  pointer and zero graph/passage citations. The erroneous Raft description was
  corrected.
- The runtime graph contains 610 concepts, 1,988 edges (267 REQUIRES,
  387 UNLOCKS, 1,334 RELATED), and 775 deduplicated passages from 60 source
  documents. Earlier D9 table-spec counts were corrected.
- Paired accuracy intervals are labeled Wald. The 10,000-sign-flip
  inference is Monte Carlo randomization. Holm correction is disclosed:
  concept McNemar comparisons remain below 0.05; BM25 MRR passage comparison
  does not (adjusted p=0.078). Passage qrels remain algorithmic candidates.
- Seven development-overlapping target concepts affect 14/38 supported
  held-out queries. Pruning 24 citations to 7 is a count result, with no
  claim-support improvement asserted.
- Legacy citation/edge labels and named attribution remain unconfirmed
  pending primary-author sign-off and independent human review.

## Local manuscript verification

The local `sigir2027_demo.tex` compiles from the local package using
`pdflatex`, `bibtex`, then two `pdflatex` passes. The resulting PDF has
five pages: four pages of main content and a separate references page,
consistent with the [SIGIR 2027 Demonstrations page limit](https://sigir2027.org/pages/submit-demo.html).
All pages were rendered and inspected. The final local PDF SHA-256 is
`8cd82d71573b6ca8ae44ce2143e42e3ff16cf74a40693ed92409d689cff0b581`.
The prior Git LFS PDF was verified as a real 1,020,656-byte binary with SHA-256
`8845469a259a868674624e051d37d8511bd2da0ed2b136f07ece8bcf1e50750d`.
The new PDF differs because local TeX paths, privacy wording, figure E wording,
and a separate references page were applied. There are no undefined
references or citations; a 1.2361 pt overfull vertical box warning remains.

## Engineering gates

- D9 and D5 targeted unit tests: 29 passed.
- D9 changed Python files: Ruff lint and format pass.
- D9 statistical table pipeline and local figure regeneration: pass.
- Local re-blinding: 731 fresh unique IDs, blank grades, private key mode 0600.
  Legacy IDs are disjoint from fresh IDs. The post-annotation tool refuses
  blank worksheets and produces no human metric file.
- Full unit suite: 1,318 passed, 69 failed, 12 errors, 11 skipped,
  1,021 deselected. Full integration suite: 42 passed, 3 failed, 1 error,
  4 skipped, 10 deselected. Failures include missing worktree root
  `okf_graph.json`, Kuzu fixture/schema failures, and unrelated inference
  contracts. These gates are **not green**.
- Repository-wide quality gate: **failed on baseline lint/format, 1,326
  strict mypy errors, and existing oversized files**. Targeted D9 Ruff
  checks pass; targeted D9 mypy remains blocked by absent NumPy/SciPy stubs
  and module import configuration. No baseline files were mass-formatted.
- Human review (the fifth quality pass): pending a different-role reviewer.

## Verdicts

| Gate | Verdict |
|---|---|
| Scientific reproducibility | HOLD for full CI; targeted frozen-data and D9 tests pass |
| Figures and tables | GO for local generation; legacy human labels remain provisional |
| Manuscript technical preparation | GO for local compilation and four-page body |
| Independent human evaluation | HOLD: zero new human judgments |
| Submission package | HOLD: author identity/contact, working reviewer access or video, and human review pending |

The draft PR must stay unmerged until a different-role reviewer and the
required CI gates resolve. No production deployment was performed.
