# Annotation Candidate Reconciliation Report (S4-G2.2 -> S4-G3)

## Summary of Reconciled Specifications
During the iterative development of the S4-G2.2 corpus-locked candidate builder, an intermediate run initially reported 5 rejected candidate specifications due to search query formatting and extraction window sizing:

1. **`Vaswani2017:chunk_008` (`encoder` x `decoder`):** Initial search window (500 chars) trimmed the sentence boundary prematurely. Expanding search window to 600 chars resolved the match into an EXACT verbatim span.
2. **`Hu2021_LoRA:chunk_007` (`pre-trained model` x `downstream task`):** The original draft query searched for "full fine-tuning" with an ASCII "fi", whereas the PDF text in Kùzu stores the unicode ligature "ﬁne-tuning" (`\ufb01`). Updating the query to "downstream task" and "pre-trained model" resolved the match to an EXACT verbatim span.
3. **`Bahdanau2014:chunk_005` (`encoder` x `sequence of vectors`):** The initial draft query searched for "fixed-length vector", which also contained the "ﬁ" ligature (`\ufb01xed-length`). Updating the target concept pair to "encoder" and "sequence of vectors" matched the exact phrase in chunk 5 with an EXACT verbatim span.
4. **`Real-time network security:chunk_005` (`real-time NIDS` x `latency`):** The initial window distance between "real-time NIDS" and "latency" was 149 characters, which exceeded the left/right trimming threshold. Increasing window expansion to 150 chars captured both terms in their complete sentence context.
5. **`doc_computer_networks_6_e:p42_1` (`Physical Layer` x `Data Link Layer`):** The chunk text contained newline formatting between layer descriptions. Updating multi-clause sentence splitting allowed the verbatim paragraph to be captured cleanly.

## Final Status
In the final build, all 24 candidates passed the hardened validation gate with:
- **`evidence_match_type = EXACT` (24/24, 100%)**
- **Document existence verified in `okf_graph.db`**
- **Chunk ID verified and linked to document**
- **Exact page number agreement (24/24, 100%)**
- **All human judgment fields left blank (CANDIDATE_UNLABELED)**
