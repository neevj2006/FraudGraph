# Local staging target

Local staging supports multiple organizations with separate databases. The original single-organization demo remains available.

The organization boundary uses separate configured databases selected by authenticated server-owned identity. Each organization has an explicit artifact path; both local fixtures intentionally share the public benchmark history/model. Private customer deployments require separate historical artifacts. A request must not be able to select a database, artifact path or organization through an arbitrary header. Identical transaction IDs and analyst names in separate organizations must remain independent. Cases remain private to their owner within the organization.

Required checks cover queue summaries, details, evidence, entity associations, cases, exports, jobs, audit records and metrics. Changing a URL identifier or token must never expose another organization's data. Worker jobs must use the matching organization's model and historical context. The same input submitted in different organizations must produce independent jobs and records.

Local staging may use generated opaque credentials with explicit analyst roles. Production authentication requires verified issuer/audience/expiry and server-side organization membership; no trust in unsigned claims or caller-chosen organization headers. Production readiness will also cover body/request limits, health/readiness, dependency checks, backups and restore, migration/rollback, resource limits, monitoring, recovery and a measured load envelope.

The benchmark is a research fixture, not live customer data. A production acceptance decision still requires a real identity-provider configuration, TLS/domain setup if hosted, data-retention decisions, validated label-delay assumptions, independent model evidence and analyst sign-off. These acceptance checks are required before hosted customer use.
