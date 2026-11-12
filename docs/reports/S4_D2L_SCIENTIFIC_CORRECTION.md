# S4 D2L scientific correction and independent review

Job `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` remains `review_ready`; publication is **BLOCKED** because no independent reviewer decision is recorded.

Official chapter: [D2L Linear Regression](https://d2l.ai/chapter_linear-regression/linear-regression.html). License: CC-BY-SA-4.0. Markdown has no printed page references.

Corrected stage: 10 concept rows; 8 proposed relationships; 5 new concept IDs, 1 new document ID, 16 new chunk IDs. No prior concept, document, chunk, or edge identity was removed.

Staged graph SHA-256: `ac4d0bfa45edec7c933be7038e1db9a7d683bf7915adc0acd13636e03eb67ec0`. Approval digest (baseline + corrected results + staging + full decision ledger): `0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77`. Canonical graph SHA-256 remains `3ee305138a4a3661b505c30a1f782baeddd7e0779eef634720392821c0eb46ed`.

The local `review_recommendations.json` contains an exact `source_excerpt` and section URL for **every** item below; the authenticated librarian page renders each excerpt in full. The `chunk_id` below identifies that exact stored excerpt.

## Concept decisions

| Original concept | Decision | Evidence | Reason |
| --- | --- | --- | --- |
| Regression | MODIFY | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | The chapter defines regression as numerical prediction. |
| Linear Regression | MODIFY | [chunk_002](https://d2l.ai/chapter_linear-regression/linear-regression.html#basics) | Replace the section recap with the model definition and fitting objective. |
| Linear Transformation | MODIFY | [chunk_003](https://d2l.ai/chapter_linear-regression/linear-regression.html#model) | The bias makes the chapter's feature map affine, not strictly linear. |
| Model | REJECT | [chunk_005](https://d2l.ai/chapter_linear-regression/linear-regression.html#model) | The extracted sentence concerns observation noise, not a supported generic model definition. |
| Loss Function | MODIFY | [chunk_006](https://d2l.ai/chapter_linear-regression/linear-regression.html#loss-function) | Loss is a function; nonnegative loss is typical rather than universal. |
| Stochastic Gradient Descent | MODIFY | [chunk_009](https://d2l.ai/chapter_linear-regression/linear-regression.html#minibatch-stochastic-gradient-descent) | Distinguish the chapter's single-example extreme from minibatch SGD. |
| Minibatch Stochastic Gradient Descent | MODIFY | [chunk_010](https://d2l.ai/chapter_linear-regression/linear-regression.html#minibatch-stochastic-gradient-descent) | Use the chapter's random minibatch gradient update; remove the false UNLOCKS claim. |
| Prediction | KEEP | [chunk_013](https://d2l.ai/chapter_linear-regression/linear-regression.html#predictions) | The Predictions section directly defines this use of the fitted model. |
| Vectorization | KEEP | [chunk_014](https://d2l.ai/chapter_linear-regression/linear-regression.html#vectorization-for-speed) | The Vectorization for Speed section explicitly processes minibatches together. |
| Normal Distribution | MODIFY | [chunk_015](https://d2l.ai/chapter_linear-regression/linear-regression.html#the-normal-distribution-and-squared-loss) | Tie the Gaussian definition to the chapter's noise assumption and squared loss. |
| Maximum Likelihood Estimation | MODIFY | [chunk_016](https://d2l.ai/chapter_linear-regression/linear-regression.html#the-normal-distribution-and-squared-loss) | Replace the tautology with the likelihood objective and Gaussian example. |
| Mathematics | REJECT | [chunk_020](https://d2l.ai/chapter_linear-regression/linear-regression.html#biology) | A passing Biology analogy does not define a relevant linear-regression concept. |

## Relationship decisions

Every original `RELATED` edge was reassessed for semantic support. `MODIFY` means the corrected edge is retained with the stated semantic relation label; `REJECT` means absent from the corrected staging graph.

| Original typed edge | Decision | Corrected meaning | Evidence | Reason |
| --- | --- | --- | --- | --- |
| linear_regression → linear_transformation (RELATED) | MODIFY | uses_affine_map | [chunk_008](https://d2l.ai/chapter_linear-regression/linear-regression.html#analytic-solution) | The chapter's regression prediction uses an affine weighted sum. |
| linear_regression → loss_function (RELATED) | MODIFY | uses_squared_loss | [chunk_006](https://d2l.ai/chapter_linear-regression/linear-regression.html#loss-function) | The chapter fits linear regression with squared loss. |
| linear_regression → model (RELATED) | REJECT | — | [chunk_004](https://d2l.ai/chapter_linear-regression/linear-regression.html#model) | Generic Model row is removed. |
| linear_regression → prediction (RELATED) | MODIFY | produces_prediction | [chunk_004](https://d2l.ai/chapter_linear-regression/linear-regression.html#model) | The fitted regression model produces predictions. |
| linear_regression → stochastic_gradient_descent (RELATED) | REJECT | — | [chunk_021](https://d2l.ai/chapter_linear-regression/linear-regression.html#summary) | The chapter uses minibatch SGD; this single-example association is too loose. |
| linear_transformation → model (RELATED) | REJECT | — | [chunk_003](https://d2l.ai/chapter_linear-regression/linear-regression.html#model) | Generic Model row is removed. |
| linear_transformation → normal_distribution (RELATED) | REJECT | — | [chunk_003](https://d2l.ai/chapter_linear-regression/linear-regression.html#model) | An affine map does not imply Gaussian noise. |
| linear_transformation → prediction (RELATED) | MODIFY | maps_features_to_prediction | [chunk_003](https://d2l.ai/chapter_linear-regression/linear-regression.html#model) | The weighted feature map yields a target estimate. |
| loss_function → stochastic_gradient_descent (RELATED) | MODIFY | optimized_by | [chunk_009](https://d2l.ai/chapter_linear-regression/linear-regression.html#minibatch-stochastic-gradient-descent) | SGD updates parameters in a direction that lowers loss. |
| minibatch_stochastic_gradient_descent → stochastic_gradient_descent (UNLOCKS) | REJECT | — | [chunk_010](https://d2l.ai/chapter_linear-regression/linear-regression.html#minibatch-stochastic-gradient-descent) | These are batch-size strategies, not a progression unlocked in either direction. |
| model → normal_distribution (RELATED) | REJECT | — | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | Generic Model row is removed; Gaussian noise is optional. |
| model → prediction (RELATED) | REJECT | — | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | Generic Model row is removed. |
| normal_distribution → linear_regression (RELATED) | MODIFY | motivates_squared_loss | [chunk_015](https://d2l.ai/chapter_linear-regression/linear-regression.html#the-normal-distribution-and-squared-loss) | Gaussian observation noise motivates squared loss for this model. |
| prediction → normal_distribution (RELATED) | REJECT | — | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | Prediction itself does not imply a normal distribution. |
| regression → linear_regression (RELATED) | MODIFY | has_specialization | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | Linear regression is a specific regression method. |
| regression → linear_transformation (RELATED) | REJECT | — | [chunk_008](https://d2l.ai/chapter_linear-regression/linear-regression.html#analytic-solution) | Regression in general need not use an affine map. |
| regression → model (RELATED) | REJECT | — | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | Generic Model row is removed. |
| regression → normal_distribution (RELATED) | REJECT | — | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | Regression in general need not assume Gaussian noise. |
| regression → prediction (RELATED) | MODIFY | predicts_numeric_target | [chunk_001](https://d2l.ai/chapter_linear-regression/linear-regression.html#linear-regression) | Regression predicts numerical values. |
| regression → stochastic_gradient_descent (RELATED) | REJECT | — | [chunk_021](https://d2l.ai/chapter_linear-regression/linear-regression.html#summary) | Regression in general need not use SGD. |
| stochastic_gradient_descent → normal_distribution (RELATED) | REJECT | — | [chunk_009](https://d2l.ai/chapter_linear-regression/linear-regression.html#minibatch-stochastic-gradient-descent) | SGD does not require Gaussian noise. |

## Release gate

`lib-qwen` F1 remains failing. The preserved source excerpts prove provenance but do not substitute for independent scientific approval. After an attributable librarian decision on this exact digest, publication still requires a verified backup, atomic swap, hosted artifact sync, protected preview parity and six live chat checks before production promotion. No GPU extraction was made. On 2026-11-12 the existing S4 service and timer files were linked into user systemd for technical readiness; both timers remain inactive and unenabled.

The existing [protected Vercel preview](https://archipelago-gekz67pgk-archipelago-6383.vercel.app) ran the previous S4 code with `cache=supabase`, 537 concepts and graph version `bafb91ebe902`; `/chat` redirected to login and an unauthenticated graph request returned 401. It does **not** contain this corrected candidate. The canonical graph still has 610 concepts and SHA-256 `3ee305138a4a3661b505c30a1f782baeddd7e0779eef634720392821c0eb46ed`. Production promotion: **not started**. No six-query preview acceptance evidence exists because neither graph publication nor hosted parity has been authorized.
