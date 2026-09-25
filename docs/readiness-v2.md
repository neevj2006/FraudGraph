# V2 local readiness evidence

Research improvement, local multi-organization staging and local hardening are implemented. This is a production-like staging release, not an approved hosted customer deployment.

## Research outcome

The fixed rolling-development protocol completed 24 runs. Neither the regularized tree nor graph alternatives met the promotion gates; the reference history tree remains selected. The final test was not reopened. Fast history features matched the reference exactly on the measured 10,000-row sample and ran approximately 29.3 times faster. See [results](research-v2-results.md). The staging bundle uses 473,187 frozen training/validation history rows and retains the original comparison models.

Current aggregate check record: [readiness JSON](results/readiness-v2.json).

## Verified engineering

- 52 backend tests passed, including real PostgreSQL, cross-organization/owner authorization, JWT signature/issuer/audience/expiry/membership validation, viewer restrictions, exact serving parity, SQLite migration and concurrent job admission.
- The rebuilt two-organization browser workflow passed, including private cases, sign-out and mobile layout.
- API and web production images built successfully; generated API types and TypeScript checks passed.
- All 38 Python source files shipped in the API image match the workspace. All five frozen model bundle digests and staging asset hashes match. The frozen research source digest is unchanged. See [inventory](results/staging-inventory.json).
- Python installed-package compatibility passed; the production npm audit reported zero vulnerabilities. This is not a comprehensive operating-system vulnerability assessment.
- Local worker/load and backup recovery evidence: [staging](results/staging-v2.json), [recovery](results/recovery-v2.json). Measurements apply only to the recorded local workload.

## Security review and remediation

A static security review covered the services before remediation. It reviewed all 14 services Python files and reported two low-severity authenticated resource-exhaustion issues. The review predates the fixes described below.

Entity lookup previously decoded every stored graph. It now joins a composite-key entity association index, selects payloads only, and returns at most 100 alerts per page. An additive transactional startup migration backfills existing records, while seeded and worker-created alerts write associations in the same transaction. Regression tests verify pagination, absence of graph-column reads, and migration.

Job submissions previously accumulated without aggregate limits. Admission now serializes quota checks using a PostgreSQL transaction advisory lock or SQLite immediate transaction. Defaults cap queued jobs at 20 per organization/5 per owner, retained jobs at 1,000, and retained serialized payloads at 64 MiB. Exact retries remain idempotent at capacity. Tests race four submissions against a capacity of one on both database engines. Retention is fail-closed: the operator must approve archival policy before increasing capacity; no automatic deletion was introduced.

Other hardening includes bounded streamed proxy bodies, server-owned identity memberships/roles, short-lived signed access-token validation, separate databases, readonly non-root application containers, and clearing/guarding organization data during sign-out. The scan did not establish a confidentiality bypass. The review was static, not a penetration test; resource-exhaustion thresholds and Windows secret-file ACLs were not measured.

## Remaining hosted acceptance

The local fixture intentionally shares a public benchmark model/history. Before using private customer data or exposing the system externally, complete real identity-provider/onboarding and key-rotation acceptance, separate private histories, TLS/ingress controls, off-device encrypted backup and recovery, retention/deletion policy, monitoring ownership and alert routing, representative sustained load, delayed-label validation and independent analyst/model sign-off. Interactive SSO login/refresh and accumulating live transaction history are not implemented. See the [operations guide](staging-operations.md) for deployment requirements.
