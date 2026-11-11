# Production deployment secrets

Keep provider credentials in Antideploy's encrypted environment store. The
tracked `.antideploy.json` contains app/build settings only and must not contain
credential values. Configure these variables in the Antideploy app settings
before a deploy that needs the corresponding integration:

- `XKIRO_API_KEY`
- `NARA_API_KEY`
- `HF_TOKEN`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- `PEARSON_USERNAME`
- `PEARSON_PASSWORD`

`SUPABASE_URL`, provider base URLs, model names, and dataset repository names are
configuration, not credentials. Keep them in the deployment config only when
they are safe to disclose. Never put credential values in browser configuration,
logs, issue reports, test fixtures, or screenshots. A credential that was
previously committed or shared should be revoked and rotated in its provider,
then installed as a platform secret.

For local development, use an untracked `.env` file. Never copy production
credentials into a local fixture or a document under `docs/`.

