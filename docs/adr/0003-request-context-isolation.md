# ADR 0003: Request Context Isolation and Concurrency Safety

## Status
Accepted

## Context
Previous iterations of the inference server maintained mutable session state in global variables within `state.py`. Under asynchronous or multithreaded traffic spikes, global state mutation introduces race conditions, state pollution across requests, and the critical risk of User A's private context bleeding into User B's response.

## Decision
1. **Immutable Explicit RequestContext:** Every inbound request generates an isolated `RequestContext` instance passed explicitly through all pipeline layers:
   ```python
   @dataclass
   class RequestContext:
       request_id: str
       user_id: str
       query: str
       timestamp: datetime  # UTC timezone-aware
       intent: str | None = None
       retrieved_sources: list[RetrievedChunk] = field(default_factory=list)
       graph_nodes: list[str] = field(default_factory=list)
       model_output: str | None = None
       verification_result: dict[str, Any] = field(default_factory=dict)
   ```
2. **Elimination of Global Request State:** No global or module-level variables may store in-flight request data.
3. **Session State Storage:** Conversational memory (`ContextTracker`) is strictly partitioned by cryptographically secure `session_id` and verified against `user_id`.
4. **Concurrency Testing:** Automated tests spin up parallel threads for distinct users (User A vs User B) and assert zero context cross-talk.

## Consequences
- Concurrency safety guaranteed across threads and async tasks.
- Request lifecycle is fully auditable and traceable via `request_id`.
