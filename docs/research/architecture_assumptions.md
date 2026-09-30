# Archipelago Architecture Assumptions & Mathematical Invariants

**Date:** September 2026  
**Status:** Validated Architecture Boundary  

---

## 1. Verified Mathematical & Algorithmic Invariants

The following principles are mathematically established and must be enforced unconditionally in code:

### 1.1 Directed Acyclic Graph (DAG) Invariant
- **Rule:** The prerequisite subgraph formed by the relation $A \xrightarrow{\text{REQUIRES}} B$ must remain a **Directed Acyclic Graph**.
- **Enforcement:** Kahn's topological sorting algorithm ($\mathcal{O}(V + E)$). Any graph mutation introducing a back-edge that violates topological ordering is rejected at insertion time.
- **Self-Loops:** $A \xrightarrow{\text{REQUIRES}} A$ is strictly forbidden ($d(A, A) \neq 0$).
- **Reciprocal Cycles:** $A \xrightarrow{\text{REQUIRES}} B$ and $B \xrightarrow{\text{REQUIRES}} A$ cannot co-exist. When detected, the edge violating the difficulty ranking hierarchy ($\text{foundational} \prec \text{intermediate} \prec \text{advanced} \prec \text{expert}$) is pruned.

### 1.2 Relational Inverses & Canonical Edges
- **Rule:** $A \xrightarrow{\text{REQUIRES}} B$ is semantically equivalent to $B \xrightarrow{\text{UNLOCKS}} A$.
- **Enforcement:** To prevent edge desynchronization, `REQUIRES` is treated as the **canonical persistent edge** in KùzuDB. Downstream enablement queries are evaluated via reverse-`REQUIRES` traversal:
  ```cypher
  MATCH (b:Concept)-[:REQUIRES]->(a:Concept {id: $target_id}) RETURN b
  ```
- Any legacy stored `UNLOCKS` edges are reconciled against this invariant.

### 1.3 Strict Pedagogical Path vs Connectivity Bridge
- **Rule:** An undirected path between concepts does not imply an educational prerequisite chain.
- **Enforcement:** If a user requests a curriculum roadmap between concept $X$ and concept $Y$, traversal occurs strictly along directed prerequisite/enablement edges. If no directed path exists, the engine returns:
  ```json
  {"error": {"code": "NO_VALID_PEDAGOGICAL_PATH", "message": "No directed pedagogical prerequisite path exists between concepts."}}
  ```
  The engine will **never** return an undirected random walk as a pedagogical sequence.

---

## 2. Engineering Assumptions Requiring Validation

The following items are engineering heuristics that must remain configurable:

| Heuristic | Default Setting | Assumption / Rationale | Failure Mode & Safeguard |
|---|---|---|---|
| **Max Traversal Depth ($k$)** | $k=2$ (default), max $k=6$ | Most technical prerequisites lie within 2 hops; roadmaps require up to 6 hops. | High $k$ causes exponential node explosion. Capped by hard budget of 5 to 10 nodes (Plan 2). |
| **Difficulty Gap Rejection** | $\text{Rank}(T) - \text{Rank}(P) \ge 2 \implies \text{Drop}$ | Advanced concepts cannot be prerequisites of foundational concepts. | Validated during ingestion; overridden only with explicit author provenance. |
| **Section Kind Filtering** | Discard `table`, `equation`, `front_matter` | Prose contains teachable conceptual definitions. | Mathematical definitions in equations could be omitted; equation captions are preserved. |
| **Deictic Memory Lookback** | 3 turns | Users rarely refer back to pronouns older than 3 conversational turns. | Older turns decay in relevance score; active concept anchor reset on topic shift. |
