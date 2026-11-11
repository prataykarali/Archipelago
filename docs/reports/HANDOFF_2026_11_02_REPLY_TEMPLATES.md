# Reply template handoff — 2026-11-02

## Built

- Bundled the supplied 130-template JSON registry separately in local inference and the standalone Vercel inference service. The file itself declares `template_count: 130`; no extra 20 templates were supplied.
- Added deterministic intent and route selection. Synthesis prompts receive one selected layout with an explicit rule to use verified evidence only and omit unsupported fields.
- Wired the layout into local streaming synthesis and hosted provider streaming. Hosted provider calls now accept the question and previous answer that the existing caller already passed, fixing the argument mismatch without changing the `/api/chat` stream framing.
- Added a hosted chat format picker backed by `GET /api/reply-templates`, so all 130 layouts can be explicitly selected; Auto uses query and route intent. The hosted UI now requests expanded answers by default, with a visible detail toggle. Expanded replies have a 1,800-token budget and include bounded, verified concept context for substantive explanations.
- UI requests can also format saved research-evidence replies. Verified source lines remain attached, and the original static research reply is returned when the provider is unavailable. Older clients retain the original static research path.
- Added registry parity, intent selection, and untrusted-question tests.

## Verification

- Focused format, chat route, hosted stream, provider, and hosted deployment tests: 40 passed, with one existing unrelated library-page assertion deselected. A separate wider run had two existing research-page assertion failures outside this change.
- Changed-file Ruff lint/format, JavaScript syntax checks, and registry-module strict type checks passed.
- Ruff lint and formatting passed for changed Python files.
- Strict type checking passed for the two new registry modules with imports skipped.
- Wider hosted deployment test suite has one existing unrelated library-page `/graph` link assertion failure.
- Repository quality gate remains red on existing strict-type and file-size baseline failures, plus unrelated formatting differences. Human review pass has not run.
- Final focused tests: 18 passed. Changed hosted Python passed Ruff; edited JavaScript passed `node --check`.
- Deployed production build `dpl_8UprN4spUtFtxnmQu3KBiMKpfZ1N` using `vercel deploy --prod --skip-domain`, checked the staged deployment, and promoted it to `https://archipelago-blond.vercel.app`.
- Public live smoke checks: `/api/readiness` 200 (`ok: true`, 537 concepts), `/api/reply-templates` 200 (130 entries), new format JavaScript 200, `/index.html` 200 with both controls, `/api/library/data` 200, `/login` 200, and unauthenticated `/api/chat` 401. `/chat` continues to redirect unauthenticated users to `/login?next=/chat`.
- UI correction after user feedback: removed the format picker, detail checkbox, and composer caption. The browser now requests `reply_detail: expanded` internally while the hosted engine chooses the template automatically. Promoted corrected deployment `dpl_5sa48T4iRyXMLdQzq1pcGW4NZ7i7` to `https://archipelago-blond.vercel.app`.
- Corrected live smoke checks: `/index.html` contains the chat input but no format picker, detail checkbox, or student caption; the request JavaScript sends expanded detail with no selector lookup; `/api/reply-templates` still returns 130 entries for API compatibility; readiness remains healthy; `/api/library/data` returns 200; unauthenticated `/api/chat` still returns 401. Focused tests: 18 passed.

## Deferred / next pair

- The local Vercel CLI is signed into the correct `archipelago-6383` team and linked to project `prj_yVvxBExHYiLa67oqnABK2vW9FfCS`. The separate Codex Vercel connector points to a different project; use the local CLI for this deployment.
- Run an authenticated live `/api/chat` smoke test with a real user session. The public checks confirm the authorization boundary but cannot exercise a generated reply without a session. Complete the separate human review pass when available.
