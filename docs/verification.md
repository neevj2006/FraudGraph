# Verification record

Environment: Windows, Python 3.12.13, CPU PyTorch Geometric, Node 26.4.0. Exact dependency resolutions are recorded in `uv.lock` and `apps/web/package-lock.json`.

- Python lint and formatter checks pass.
- 27 backend tests pass (including nine scale-count and batched-equivalence additions): canonical validation, deterministic checksums, strict chronological splits, unseen masks, label/future invariance, time-valid explanations, GraphSAGE/R-GCN tiny-batch overfit, future-node invariance, API auth, private-case export isolation, concurrent-note conflict detection, queue filtering, durable idempotent scoring, label injection rejection, readiness and once-only final evaluation. The PostgreSQL integration test also passed locally on 2026-09-13 against a dedicated PostgreSQL 17 container, exercising real case storage, exports and durable worker jobs.
- Next.js TypeScript check and production standalone build pass; npm dependency audit reported zero known vulnerabilities at install time.
- Five Playwright journeys pass against the live API and built web application: investigation/save/export/audit; filtering/pagination/empty state; mobile keyboard assessment and horizontal-overflow check; recoverable service error; entity exploration/persisted assessment.
- Browser verification confirmed nonblank content, key controls and no reported browser errors. Desktop/mobile screenshots and an automated walkthrough video are included.
- Fifteen model/seed runs were trained and mirrored into local MLflow. Frozen synthetic final evaluation completed once. Full numerical records are under `docs/results/`.
- `docker compose config --quiet` passes with staging environment values. Docker runtime verification is recorded below; configuration validation alone does not prove containers run.

Browser-test friction found and resolved: implicit filter labels required role-based selectors; Next's route announcer needed excluding from application error assertions; the initial graph was too dense, so its canvas now focuses on focal shared signatures; the entity dialog now uses native modal focus handling. Fonts are self-hosted, eliminating a remote font request during the analyst workflow.

Final hardening also replaced timestamp-based optimistic locking with integer revisions after a fast-write test exposed equal timestamps. SQL indexes use `CREATE INDEX IF NOT EXISTS` because SQLite reflection does not reliably discover expression indexes. The final backend suite passes with both corrections. Browser types are generated from validated OpenAPI response contracts, and queue filtering/summaries execute in SQL.

The test framework emits upstream deprecation notices for FastAPI/Starlette's httpx adapter and PyTorch's TorchScript path. These did not cause failures. The application has not been load-tested on the entire IEEE-CIS dataset or validated with real analysts. Five automated scenarios are not five independent human usability participants.

## Clean-folder reproduction

Copied only files eligible for version control to `artifacts/repro-source`, excluding environments, datasets, model artifacts and local credentials. Installed fresh locked Python and Node environments there. Backend tests and the production web build passed. Rebuilt the full three-seed synthetic experiment without reopening its final holdout. The following artifacts matched the original byte for byte:

| Artifact | SHA-256 |
|---|---|
| manifest.json | fcf90a4027e72b7e8814ec290f65e8f2fa70d96acf0bf2bc3daafe01d88d8b85 |
| scores.json | 32a81612b1f2752012cfaee1206625bf8cbf2be096db4e3166af97bceea1256d |
| events.csv | 58448b850ed31585526e36cbbc2fb4d11d4101259c2fbb327d9d6156879ba8f5 |
| graph-quality.json | a15fc114a19a10346e63efd277a4c78e5083f19ed476d06189d3c7bee23f598e |

The audit caught and fixed an overly broad `.gitignore` pattern that excluded the `ml/data` source package. The corrected `/data/` pattern ignores only the root dataset directory. Experiment manifests use canonical-content dataset hashes; the table above measures physical file bytes, including line endings.

## Container runtime verification â€” 2026-09-13

The earlier Docker Desktop stale-socket startup blocker is resolved on this host. Docker Engine 29.5.3 successfully built all three images from the locked dependencies: API, worker and web.

The complete Compose stack ran with PostgreSQL 17, the frozen Windows-generated artifact mounted read-only, staging authentication and non-root application containers. Verification used loopback ports 18000 (API) and 13000 (web) to preserve the native demo on ports 8000 and 3000.

- Readiness reported frozen version `f16663bdd7621c76` inside Linux.
- All five Playwright workflows passed against the container web proxy and PostgreSQL-backed API (13.9 seconds).
- A submitted scoring job completed in the separate worker and produced `CONTAINER-VERIFY-001`, including its frozen-history policy and provenance.
- After the workflows and scoring, telemetry reported 361 alerts, zero queued or failed jobs, and zero server errors across 46 measured requests. The observed recent p95 was 37.01 ms; this small smoke run is not a load benchmark.
- The separate full backend suite passed all 18 tests, including the isolated real-PostgreSQL integration.
- After restarting API and worker and waiting for readiness, the saved case, completed job and generated alert remained available with the same model version. Verification containers were then stopped; PostgreSQL volumes were preserved.

At this historical container milestone, public IEEE-CIS evaluation and full-dataset scaling were still pending; the later sections and final release audit record their completion. Container success does not substitute for public-data model evidence. Remote CI and hosted deployment were not tested.

## Public cohort verification

The recovered Docker environment completed the 10,000-row IEEE-CIS cohort's 15 model/seed runs, once-only final evaluation and validation robustness diagnostics. Frozen model version: `0f0de617a814b8f9`. The ML code hash matches the original synthetic release; no model code was changed based on the new holdout.

The API loaded all 1,996 validation alerts from this artifact. Readiness, evidence generation, case persistence and export passed. A dedicated Playwright public-cohort journey passed (8.8 seconds), covering dataset provenance, source-unit amounts, graph rendering, saving/exporting an assessment, empty-state recovery, pagination and mobile layout. The web production Docker build, TypeScript checks and Python script lint/format checks passed. Test media containing public source-derived rows remain in ignored test-results rather than published documentation.

This cohort milestone preceded the full-dataset comparison documented below. This cohort result does not replace the original synthetic verification or imply production acceptance.

The separate public-cohort worker check completed successfully using version `0f0de617a814b8f9`. Its explicitly synthetic smoke input produced a new alert with the frozen training/validation history policy, without changing source data or model weights.

The full-dataset graph-size counter passed a direct parity test against the actual causal builder, including tied timestamps, missing identifiers and the eight-neighbor cap. See [scale assessment](ieee-scale.md). This validates counting logic, not full-scale GNN training.

## Full-data tabular verification

The separate full IEEE-CIS tabular experiment completed nine model/seed runs over the chronological 355,520/117,667/117,353 split. Its final evaluation ran once after code, data and model checksums were frozen and verified. The history-feature tree achieved final AP 0.1262 and precision@100 33%. Aggregate results, novelty slices, bootstrap uncertainty and timings are in [the full-data report](ieee-full-tabular.md). No GNN full-scale result is implied.

The revised public-data browser workflow passed again (13.7 seconds), including the additional worker-created alert. Python script lint/format checks, TypeScript validation and the production Docker web build passed. The scale-counter parity test passed. That browser check used local port 13001 with the separately frozen cohort model; service availability depends on the local containers being running.

## Full-data graph and final local release audit

All six graph training runs completed. The five-family validation choice was frozen as sage before graph final evaluation. The final command verified code, cache, dataset and model hashes and completed once on all 117,353 held-out targets. The window had previously been inspected for tabular results. See [graph results](scaled-gnn-results.md) for the full disclosure and measurements.

The final local audit passed: 27 backend tests including PostgreSQL and graph prediction/gradient parity; clean locked API/web builds; fresh synthetic training; five synthetic browser workflows and one public-data workflow; durable worker scoring and saved-case/job persistence after restart. Ruff lint and formatting pass. Data/artifact exclusions and all four frozen bundle hashes are verified by [the machine-readable inventory](results/release-inventory.json).

Docker Desktop initially encountered a stale host socket on September 16. Its stopped runtime socket folder was preserved under a backup name, and a subsequent startup succeeded. Evaluation used the existing clean-built image; no Docker factory reset, dataset deletion or host reboot was performed. The final run sampled 1044.1 MiB process RSS under a 2 GiB limit. Source hashes still match the clean runtime snapshot.

Full-dataset offline scaling is verified. Full-dataset API throughput and independent analyst utility are not. Remote CI and hosted deployment were not tested. See [the audit scope and evidence](release-audit.md).
