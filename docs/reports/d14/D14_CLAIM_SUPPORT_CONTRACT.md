# D14.4 Epistemic State & Claim-to-Passage Support Contract

- **Owner:** `d14-synthesis-math`
- **Phase:** D14.4 — Scientific Synthesis, Mathematics & Claim Support
- **Applies To:** `host_inference/engine/answer.py`, `host_inference/engine/reply_plan.py`, `host_inference/engine/math_guard.py`, `host_inference/engine/prompts/chat_reply.txt`, `archipelago/inference/math_validator.py`.

---

## 1. Five Explicit Epistemic States

Every response turn is deterministically classified by `reply_plan.classify_epistemic_state(payload, route, query)` and exposed on `payload["epistemic_state"]`, `payload["trace"]["epistemic_state"]`, and `[STREAM_META]`:

| # | State Identifier | Meaning | Required Attribution & Behavior |
|---|---|---|---|
| 1 | `DIRECTLY_SUPPORTED` | Factual claims backed by at least one `verified_full_text_passage` citation (`evidence_backed == True`). | Cite only verified evidence IDs (`[S1]`, `[S2]`, ...). Never fabricate extra markers. |
| 2 | `INDEPENDENTLY_DERIVED_EXAMPLE` | Worked mathematical or illustrative examples derived during synthesis rather than quoted from a passage. | Explicitly label as `Illustrative example (independently derived)`; verify dimensions and arithmetic deterministically; never misattribute textbook examples (e.g., OSTEP) as independently derived. |
| 3 | `GENERAL_MODEL_KNOWLEDGE` | Foundational domain knowledge not directly established by retrieved full-text passages. | Explicitly label as general explanation; never attach fabricated `[Si]` source markers. |
| 4 | `METADATA_ONLY` | Only bibliographic metadata, catalog cards, or concept summaries are available (`source_kind == "metadata_only_record"`). | State explicitly that full-text passages are not loaded; never claim passage-level verification. |
| 5 | `UNAVAILABLE_OR_UNCERTAIN` | Target document/full text unavailable, withdrawn, out-of-domain, or stream interrupted/truncated. | Abstain honestly; never fabricate architectures, experimental results, or page links. |

---

## 2. Claim-to-Passage Support Verification States

Implemented in `host_inference/engine/math_guard.py::verify_claim_support`:

| Status | `validated` | Condition |
|---|---|---|
| `VERIFIED` | `True` | `stream_status == "complete"`, at least one inline `[Si]` marker is present, every marker maps to a non-withdrawn `verified_full_text_passage` citation, and every citing sentence shares content-token support with its retrieved passage text. |
| `UNASSESSED` | `False` | `stream_status == "complete"`, but passage-level support was not assessed (e.g., `assess_passages=False`, no verified full-text passages exist, or no inline `[Si]` markers were emitted). **Unassessed support MUST be labeled `UNASSESSED`, never `VERIFIED`.** |
| `PARTIAL_OR_UNSUPPORTED` | `False` | `stream_status == "complete"`, and one or more inline `[Si]` markers either do not correspond to a verified full-text citation or lack lexical support in the referenced passage. |
| `INCOMPLETE_UNVALIDATED` | `False` | `stream_status != "complete"` (e.g., `truncated_token_limit`, `incomplete_stream`, `stream_deadline_exceeded`, `incomplete_eof`). |

---

## 3. Mandatory Enforcement Invariants

1. **Unsupported Citation Stripping (`strip_unsupported_citations`):**
   - In deterministic replies (`Engine.answer`), any inline `[Si]` marker that does not map to a verified full-text citation is stripped before returning `text`, and recorded in `payload["claim_support"]["stripped_unsupported_markers"]`.
   - In live-streamed replies (`Engine.stream_chat`), any unsupported `[Si]` marker emitted during streaming triggers a post-stream **Claim support notice** and sets `claim_support_status = "PARTIAL_OR_UNSUPPORTED"` and `validated = False` in `[STREAM_META]`.
2. **Never Label Partial or Interrupted Streams as Complete Validated Answers:**
   - Whenever `outcome_status == "truncated_token_limit"` or `incomplete_eof` / `stream_interrupted*` / `stream_deadline_exceeded`, `[STREAM_META]` MUST emit:
     - `"validated": false`
     - `"claim_support_status": "INCOMPLETE_UNVALIDATED"`
     - `"epistemic_state": "UNAVAILABLE_OR_UNCERTAIN"`
3. **Combined Validation Gate on Normal Completion:**
   - `[STREAM_META]["validated"]` is `true` if and only if BOTH `claim_report["validated"]` AND `sci_audit["passed"]` are `True`.
