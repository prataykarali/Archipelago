# S1 reply engine implementation evidence

## Changed behavior

- The main chat API uses intent plus exact concept evidence to route paper, research,
  and multi-concept questions when the semantic scope provider is unavailable.
  Library inventory falls back to the existing holdings handler if the scope
  router rejects it. Multi-turn pronouns resolve against the last user question.
- Both engines retain the existing 130 template registry. Research explanations
  avoid an automatic learning graph; concept learning keeps its graph. Paper,
  library, and research-intelligence replies have no diagnostic MCQs.
- Both multi-anchor engines cover every extracted anchor, preserve typed path
  direction, and report missing or unconnected concepts. Hosted replies choose
  supporting passages and unique source IDs. Opposing paper claims about the
  same named metric are reported without selecting a winner.
- Recent-study replies state the dates of verified indexed examples, or disclose
  that the local index has no verified publication-date coverage.

## Before and after samples

**Main chat, three concepts**

Before: `How are transformers, retrieval-augmented generation and knowledge graphs related?`
returned the generic out-of-scope notice with no concept citations.

After: the local API returns route `multi_concept`, resolves `transformer`,
`retrieval_augmented_generation`, and `knowledge_graph`, and cites one relevant
passage for each. Its explanation begins:

> The Transformer is a sequence-to-sequence architecture based on attention
> instead of recurrence. [S1]
>
> RAG adds external retrieval before generation [S2]. A knowledge graph can
> organize entities and relationships for a GraphRAG workflow [S3].

**Hosted chat, Transformer evidence**

Before: the stored Transformer summary described a “bidirectional, generative”
model using masked language modeling and next-token prediction, then cited a
BERT passage. It also emitted three distinct papers with the same `S1` marker.

After: the hosted reply says:

> The Transformer replaces recurrent and convolutional sequence transduction
> layers with attention. [S1: Vaswani2017_Attention_Is_All_You_Need.pdf, #page=10]
>
> RAG combines a retriever and a generator, training them together to use
> retrieved documents. [S2: Lewis2020_RAG.pdf, #page=4]

The knowledge-graph statement cites Edge 2024 as `S3`. The response also gives
one synthesis of their different roles and keeps stored graph paths in the
structured `multi_hop.paths` payload.

**Paper lookup**

Before: local `Which paper introduced RAG?` returned the scope refusal.
After: it names the closest indexed RAG paper with its evidence ID and states
that one source cannot establish historical priority. No graph or quiz is sent.

## Verification

`pytest -q` over S1 routing, multi-hop, multi-turn, template, main API, hosted
API, library, and source-link suites: **169 passed**. Ruff check and format
check pass for the changed S1 Python files.

The repository-wide `scripts/quality_gate.py` still exits 1: its lint pass
includes pre-existing issues in OPAC and other files outside S1; strict mypy
reports 880 baseline errors; and eight pre-existing files exceed its 400-line
threshold. Banned patterns, magic numbers, and dependency direction pass.

## Limits and handoff

- Exact concept resolution reports missing anchors instead of guessing a fuzzy
  identity. This may leave a paraphrase with partial coverage.
- A stored graph edge is reported as graph structure. It is not presented as a
  paper-verified scientific dependency unless supporting text exists.
- The local concept index does not verify publication-date coverage for recent
  studies; dated scholarly retrieval remains in the research workspace.
- The working tree was already on `feature/s2a-academic-coverage-repair` with
  extensive uncommitted changes. These edits have not been rebased onto the
  requested `session3-stable` base.
