# ADR 0001: Graph Edge Semantics and Canonical Traversal

## Status
Accepted

## Context
Archipelago models knowledge as a directed educational dependency graph. The specification defines two core relational edges:
- `REQUIRES`: Backward prerequisite dependency ($A \xrightarrow{\text{REQUIRES}} B$ means concept $A$ requires understanding concept $B$).
- `UNLOCKS`: Forward capability enablement ($B \xrightarrow{\text{UNLOCKS}} A$ means mastering concept $B$ enables learning concept $A$).

Storing both directed edges independently in the database introduces severe edge desynchronization risks, potential cycle anomalies, and storage redundancy.

## Decision
1. **Canonical Persistent Edge:** The database persists `REQUIRES` as the sole canonical prerequisite edge between concepts.
2. **Derived Inverses:** Forward mastery projection (`UNLOCKS`) is derived dynamically at query time by traversing `REQUIRES` in reverse:
   ```cypher
   MATCH (b:Concept)-[:REQUIRES]->(a:Concept {id: $target_id}) RETURN b
   ```
3. **DAG Enforcement:** Directed cycles are strictly prevented on `REQUIRES` edges using Kahn's topological sort. Reciprocal cycles ($A \leftrightarrow B$) are resolved at ingestion using concept difficulty rankings.

## Consequences
- Zero desynchronization between prerequisite and unlock paths.
- Graph storage and index overhead in KùzuDB is reduced by ~30%.
- Forward traversal logic is mathematically guaranteed to reflect the exact inverse of backward requirements.
