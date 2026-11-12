# S5 research graph audit

`build_graph` projects a run-scoped scholarly graph without mutating the academic concept graph. Node kinds: Paper, Author, Venue, Institution, Topic. Edges: `AUTHORED_BY`, `PUBLISHED_IN`, `AFFILIATED_WITH`, `STUDIES_TOPIC`, and `CITES` when an OpenAlex referenced-work ID matches a selected OpenAlex paper ID. No semantic-similarity citation inference is used. The graph-neural-networks live Top-20 produced 28 in-set `CITES` edges, each attributed to its provider. A zero-edge topic is possible because references outside Top-K are not invented as selected nodes.

`USES_METHOD` and `EVALUATED_ON` are not generated from titles or abstracts without structured evidence. Academic concept cross-links and published graph-version history are deferred. Saved run timestamps provide snapshot history, not an approved graph publication ledger. S4's pending D2L graph remains untouched.
