# D9 failure analysis and evidence limits

The frozen 50-query benchmark remains unchanged. The executable D9 table pipeline
uses the locked D5 artifacts and retains 37 queries with positive algorithmic
passage labels for Experiment B. These labels are candidates, not human qrels.

## Corrected interpretations

- Q45 is the frozen compiler question, “How do compilers transform source code
  into machine instructions?” Its single Pearson *Compilers: Principles,
  Techniques, and Tools, 2e* catalog pointer is metadata, with no indexed
  passage citation or graph anchor. A prior Raft description was erroneous.
- Seven target concepts recur across development and held-out sets. This affects
  14 of 38 supported held-out queries. Two development/held-out query pairs
  exceed content-token Jaccard 0.40. The earlier 12/26 stratification used a
  different implicit grouping and should not be cited.
- The paired accuracy intervals in the D9 pipeline are Wald intervals, not
  Newcombe intervals. The 10,000-sign-flip test is Monte Carlo randomization,
  not exhaustive permutation.
- Three concept-resolution McNemar comparisons remain below 0.05 after Holm
  adjustment. Of 12 exploratory passage comparisons, BM25 MRR no longer clears
  0.05 after Holm correction (adjusted p=0.078). Passage qrels are provisional.
- The deterministic selector reduced the number of emitted citations from 24
  to 7 across the five recorded queries. This is a count reduction only.
  Claim-support accuracy after selection has not been independently measured.
- Legacy citation and graph audit files contain human attribution fields.
  The primary author has not confirmed each recorded judgment in this D9
  workflow. Treat all such labels and attribution as unverified legacy records.
  No independent human judgments were generated here.

## Remaining evaluation gate

The 731-item local reviewer packets have fresh HMAC-based candidate IDs. The
secret and system/rank mapping are held only outside Git. The post-annotation
pipeline refuses blank or incomplete worksheets before creating any human-qrel
metric file. Independent reviewers and adjudicator must complete the sheets.
