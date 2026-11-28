# D14.9 author retest packet — hold until hosted parity is repaired

**Operational verdict: REVISE.** Isolated URL: https://archipelago-sigir-670tlv38p-sigir1.vercel.app . It is currently Vercel protected and the in-app browser showed `You Need Access`; the author needs access approved by the `sigir1` team owner, then a normal Supabase research account login. Do not disable JWT verification or use UEM credentials.

Candidate Git SHA: `6f1fa77864fa006c1519e465e9e7faf6f6836b42`. Current deployed release SHA reported by readiness: `fe8887c878e27f1770690236513f0f6c79c37d7c` (a release identifier, not proof of Git parity). Actual hosted corpus: `corpus_v2_d10_3025`, 3,025 passages, 43 documents, SHA-256 `93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52`. Advertised V3 is inconsistent. Actual graph: 631 concepts, version prefix `4f6861e6131c`; full candidate graph SHA-256 `4f6861e6131cbccd7f60fa811492b20cba77fd1012acc7aecb9607f63c5c35ac`, 1,943 pending edges. No authenticated response trace has been obtained.

After staging is corrected, run these author inspection batches. For each query, record response completion, exact citation IDs, source and printed page, reader link, graph route and direction, coverage signal, and a human judgment. These are development/manual examples, not the held-out benchmark.

| Batch | Domain | Manual query examples |
|---|---|
| 1 | AI & Machine Learning; Probability & Statistics | What is attention?; Explain DPO's reward model; Derive Gaussian MLE; What is Bayes' theorem?; Explain overfitting. |
| 2 | Operating Systems; Computer Architecture | What is paging?; Does vLLM require OS paging?; Explain virtual memory; What is a cache hierarchy?; Explain instruction pipelining. |
| 3 | Data Structures & Algorithms; Database Systems | Explain B+ trees; What is Dijkstra's algorithm?; Explain ACID isolation; What is a database index?; Show prerequisites for query optimization. |
| 4 | Computer Networks; Information Security | Explain TCP congestion control; What is DNS?; Explain public-key cryptography; What is threat modeling?; Show downstream concepts from encryption. |
| 5 | Compilers & Languages; Automata & Computation | What is a parser?; Explain type checking; What is a finite automaton?; Explain decidability; Show prerequisites for compiler optimization. |
| 6 | Mathematics for Computing; Software Engineering | Explain matrix multiplication; What is a gradient?; Explain continuous integration; What is a unit test?; Show downstream concepts from linear algebra. |
| 7 | Cross-domain boundary | Ask an in-corpus concept using a paraphrase; ask a weak-evidence in-corpus question; ask an unresolved concept; ask an out-of-coverage non-computing question; start and cancel a streaming answer; observe long-answer completion/truncation. |

## Inspection and acceptance

For a citation, open its source card and reader, verify the cited passage ID exists in the **activated** corpus manifest, compare the displayed printed page with the source, and judge whether the passage actually supports the claim. For graph navigation, inspect both prerequisite and downstream directions and relation labels; record any invalid edge. Compare institutional and OA-only sessions without granting broader access. Check browser console and network errors, session persistence after reload, streaming completion and cancellation. Unauthorized requests must still return the appropriate authentication error.

Accept only if readiness, suggestions, catalog, chat, passage retrieval, citation resolution, reader and graph coverage all name the same activated corpus and graph; actual passage IDs and counts match verified manifests; all 12 domains are inspectable; authenticated flows work; and the author has recorded judgments. Citation availability alone does not prove correctness. Paraphrase citation coverage was only 3/6 in the prior local diagnostic. Graph edges remain unverified. Retrieval superiority, novelty, and personalization effectiveness are not established.

Human judgment fields (leave blank until author review): query ID ___; response correctness ___; evidence relevance ___; citation support ___; printed page correctness ___; graph relation validity ___; navigation usefulness ___; coverage/abstention appropriateness ___; notes ___.

Before D15, the author must approve the contribution, candidate release, rights evidence, benchmark integrity, independent leakage review, and experimental protocol. The [68-document rights audit](D14_9_SOURCE_RIGHTS_AUDIT.csv) currently quarantines 63 documents, excludes one, and leaves four conditional; the unactivated filtered review subset has only three domains. The held-out 50-query benchmark remains locked.
