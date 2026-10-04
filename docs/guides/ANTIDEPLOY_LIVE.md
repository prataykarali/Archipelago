# Updating the existing hosted app

The live address is `https://archipelago.antideploy.com`.
Its application ID is `4427410e-8b49-4122-aedb-8dbb5e2e3c60`, on the owner's Google-sign-in account.
It is an **uploaded-folder application**, not a GitHub-connected application.
Merges and pushes do not redeploy it. Do not create another app or change its hostname.

The repository root Dockerfile is the local inference service. The live UI uses
the standalone `host_inference` application. Package it with
`deploy/antideploy/Dockerfile`, not the root Dockerfile. The release wrapper
requires the existing Supabase corpus before opening its socket and refuses a
fixture, malformed artifact, or corpus/catalogue smaller than the recorded live
baseline (520 concepts, 40 Pearson books). Review these minimums against the
current live baseline when preparing a future release.

`scripts/package_antideploy.py` includes the complete tracked hosted source/UI,
verifies original LFS assets by SHA-256, excludes runtime caches, private data,
backups and credentials, and reports original assets that are unavailable.
Use a new output directory outside the checkout. `release.json` identifies the
exact source commit in the HTTP `X-Archipelago-Release` header.

Authenticate through Antideploy's approved terminal device flow. Account tokens
belong only in `~/.antideploy/config.json`, mode 0600, never in this repository,
terminal output, chat, an archive or artifact. Keep all existing application
secrets; the release request does not supply or overwrite secret values.

POST the archive to `/api/v1/deploy?applicationId=...`, then watch the returned
deployment URL until terminal status. A queued deployment is not proof of a live
fix. Verify the public hostname, release header, `/api/readiness` remote source
and corpus counts, `/chat`, UI assets, real chat/diagnostic flow and protected
staff endpoints before reporting success. Record warnings/security results.
Antideploy's rollback endpoint can rebuild the previous release if needed.

Hosted optional learning memory is SQLite on ephemeral container storage: its
30-day retention is a maximum, not a cross-release persistence guarantee.
Deployments or container replacement may reset it. Staff remains authenticated;
browser-owned memory inspection/deletion uses only the caller's opaque cookie.
