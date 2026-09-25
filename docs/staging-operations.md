# Multi-organization local staging

Run `docker compose -f compose.staging.yaml up -d` from the repository root with Docker Desktop running. Open http://127.0.0.1:13004. API: http://127.0.0.1:18004. `/health` checks liveness; `/ready` checks model and database readiness. Ports bind to loopback only.

Use the assigned organization/subject token from ignored `artifacts/staging-v2/organizations.json`. Never publish that file, bootstrap SQL, database dumps or browser artifacts. Credential preparation refuses to overwrite existing files. Stop with `docker compose -f compose.staging.yaml stop`, retaining the database volume.

North and South have distinct PostgreSQL databases and login roles. Identity selects the database; arbitrary organization headers do not. Cases and exports also require matching ownership. Viewers cannot write cases, submit jobs or export. Both fixture organizations deliberately share public benchmark history and models. API and worker processes are trusted across organizations and hold the full registry.

## Scoring and monitoring

The [research protocol](research-v2-results.md) retained the reference history tree: neither proposed model passed promotion gates. The staging bundle uses 473,187 frozen training/validation rows and a 200-alert seed queue. Each batch uses frozen history plus its own events; earlier submitted batches do not accumulate into history.

Defaults are 300 authenticated requests per subject/organization per minute, a 1 MiB body and at most 500 events per batch. Rate limits are process-local. Admission additionally caps pending jobs at 20 per organization and 5 per owner, retained jobs at 1,000 and serialized job payload storage at 64 MiB. Admission is serialized transactionally and returns 429 when full; exact retries remain idempotent. Completed records are retained until an operator-approved archive/retention decision. Entity lookups use an indexed association table and return at most 100 alerts per page. The [load check](results/staging-v2.json) covers 200 queue requests at concurrency 20, not sustained production capacity. Monitor authenticated `/v1/metrics` for queued/failed jobs and recent latency; container logs supply request IDs and status without credentials or notes.

## Production identity contract

A production registry requires `identity_provider` with HTTPS `issuer` and `jwks_url`, dedicated API `audience`, and `max_lifetime_seconds` at most 3600. Explicit server-owned `memberships` contain subject, organization and roles; static credentials are prohibited. RS256 access tokens must include `kid`, `sub`, `org`, `iss`, `aud`, `iat`, `nbf`, `exp`. Verified subject/organization must match a membership; token roles are ignored. The UI accepts an already-issued access token; interactive SSO login/refresh is not implemented.

JWKS uses a five-second timeout and five-minute cache. Registry/membership changes require restart. Expiry is checked every request. Real provider connectivity, key rotation and onboarding still require acceptance testing. Verification follows [PyJWT's API](https://pyjwt.readthedocs.io/en/stable/api.html).

## Recovery and rollback

`uv run python -m scripts.verify_recovery` writes custom-format dumps to ignored `artifacts/staging-v2/backups/<unique-id>/`, restores into fresh `recovery_*` scratch databases, and compares ordered row digests for alerts, cases, jobs, audit events and entity associations. Live databases are never restore targets. Run in a quiet interval; concurrent writes intentionally invalidate the comparison. Scratch databases/dumps remain for inspection. The [drill results](results/recovery-v2.json) show exact recovery for both organizations.

Local dumps are not off-device disaster recovery. Hosting requires encrypted off-device backups, retention/recovery objectives and recovery on another host. Preserve registry secrets and immutable artifacts separately from database backups.

Before schema/model changes: stop submissions, drain jobs, stop API/worker, verify a backup, and retain the current image digest/model directory. Storage provides first-schema creation, an idempotent legacy revision-column/index upgrade, and a transactional additive entity-association backfill. Startup serializes this migration; no existing case/job data is removed. Future schema changes require versioned migrations and a restore rehearsal. Never run an incompatible old image against an upgraded database. Restore separately, verify readback, then switch registry and retained image/model. Never delete the staging volume as a troubleshooting shortcut.

## Hosted acceptance

Still required before hosted customer use: real identity-provider acceptance; TLS/domain and ingress connection/rate limits; private organization histories; off-device backups; retention/deletion decisions; monitoring ownership and alert routing; sustained representative load; delayed-label validation; independent analyst/model acceptance. These checks remain deployment requirements.
