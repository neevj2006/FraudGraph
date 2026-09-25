# Operations

## Local services and storage

Use README commands for API port 8000, web port 3000 and the worker. SQLite lives at `artifacts/fraudgraph.db`; the frozen graph/model lives in `artifacts/release`. API process health is `/health`; readiness is `/ready`. Authenticated model metadata is `/v1/model`. Request logs report request ID, HTTP status and elapsed milliseconds. Set Python logging to INFO when collecting application telemetry.

All investigator endpoints require `Authorization: Bearer <token>`. `FRAUDGRAPH_ANALYST_TOKENS` may contain a JSON object mapping analyst names to unique long tokens. Tokens identify analysts, not independent organizations; evidence alerts are shared across analysts, while cases, jobs, notes, exports and audit records are private to their owner. Never use the published demo token on a reachable deployment.

The generated OpenAPI reference is `docs/openapi.json`. The canonical score contract is `AlertScore`; requests reject extra fields including labels. Queue filtering and pagination execute in SQL, with score/time/amount indexes. Response contracts generate the frontend types through `npm run generate:api`. `/v1/metrics` exposes current-process request/error counts, recent p95 response latency and the caller's queued/failed job counts. Seeded offline alerts report unmeasured latency as null; worker-created alerts report amortized batch latency.

## Batch inference

Submit `POST /v1/jobs` with:

```json
{"events":[{"id":"BATCH-001","time":999999,"amount":125.50,"account":"new-account","device":"shared-1"}]}
```

Poll `GET /v1/jobs/{id}`. The worker returns `queued`, `completed` or `failed`. A completed result contains alert IDs, model version provenance in each alert and batch latency. Run `uv run python -m services.inference.worker --once` for one local job, or omit `--once` for a durable polling worker.

The batch must be later than the frozen train/validation history. IDs must not collide with history or existing alerts. Missing entities are allowed. A batch cannot supply labels. Scoring includes frozen history plus events in the same batch, not events from other batches. To advance history, build a new explicitly versioned experiment. Replay uses the same actor/payload/model hash; failed jobs retain the failure record. Correct the input or model and submit a new job.

Use one SQLite worker. PostgreSQL row locks support multiple workers. Long inference transactions can hold locks; the reference implementation is not a high-throughput streaming service. The worker currently treats validation, artifact and key errors as explicit failed jobs; unexpected infrastructure errors roll back so an operator can investigate and retry without partially written alerts.

## Docker / PostgreSQL

Set `POSTGRES_PASSWORD` and `DEPLOY_API_TOKEN` in the shell or an uncommitted environment file. Use URL-safe random characters for the database password because it enters a connection URL. The API token must be at least 32 characters and different from the demo token. Then:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs api worker
```

Artifacts must already exist at `artifacts/release`. The API and worker mount them read-only. The web and API ports bind to loopback. A real remote deployment needs TLS and proper identity management. PostgreSQL data uses a named volume. `docker compose down` preserves that volume; do not add `--volumes` unless intentionally deleting all cases and audit data.

Images run as non-root users. API and inference share the same locked Python image; web uses Next's standalone bundle. CI definitions are local files until code is explicitly pushed, and remote CI has not run merely because the workflow exists.

## Rollback and recovery

1. Stop accepting new batch submissions and drain queued jobs for the current version.
2. Back up PostgreSQL with `pg_dump`, or copy a quiescent SQLite database. Preserve the matching artifact directory and manifest checksums.
3. Point `FRAUDGRAPH_ARTIFACT_DIR` to a previous trusted, frozen bundle. Restart API and worker and verify readiness/model version.
4. Keep historical alert/evidence records intact. The UI identifies scores from older model versions. Do not overwrite existing transaction IDs with new scores; use a new database or an explicit migration for a rescore.
5. A pending job for another version fails clearly. Do not silently score it under a replacement model.

SQLAlchemy creates the initial schema idempotently. Startup includes first-release migrations for query indexes and integer case revisions. Later schema changes require an explicit migration and backup; `create_all` is not a general migration engine. The schema enforces one case per owner and transaction, and revision checks return 409 on a concurrent write instead of losing a note. Local case changes and exported audit records persist across process restarts.

## Monitoring and limitations

The experiment emits `drift.json`, graph-quality, validation-slice, calibration and scoring-latency reports. Compare against the artifact's baseline, not arbitrary universal PSI thresholds. Public-data monitoring needs known label delays and outcome reconciliation. The system does not feed analyst dispositions into training automatically.

MLflow mirroring is optional and local: `uv run --extra tracking python -m scripts.track_experiment`. Its SQLite database and `mlruns/` artifacts are ignored by Git. Repeating the mirror command records another set of tracking runs; the immutable experiment version identifies duplicates. It never changes the serving bundle.
