# API contract v1

The FastAPI schema is generated to `openapi.json` by `uv run python -m scripts.export_openapi`. All `/v1` endpoints require a bearer token. Responses have no-store caching. Browser requests use the Next same-origin proxy, whose upstream is set only by the operator's `API_URL`.

| Method | Route | Behavior |
|---|---|---|
| GET | `/health` | Process liveness |
| GET | `/ready` | Database + verified model readiness |
| GET | `/v1/model` | Version, dataset, features, seeds, policy, checksums |
| GET | `/v1/metrics` | Current-process request/latency counters and caller's queue/failure counts |
| GET | `/v1/alerts` | Score-descending queue, amount/score/time/entity filters, limit/offset |
| GET | `/v1/alerts/{id}` | Score provenance, comparisons, uncertainty and caller's case |
| GET | `/v1/alerts/{id}/graph` | Time-valid typed evidence, provenance, summaries and truncation |
| POST | `/v1/alerts/{id}/case` | Save disposition + nonempty note and append an audit event |
| GET | `/v1/cases` | Caller's cases |
| GET | `/v1/cases/{id}/export` | Owner-only case JSON with evidence; audits export |
| GET | `/v1/audit` | Latest 100 events for caller |
| GET | `/v1/entities/{id}` | Associated alerts and maximum score; no independent probability claim |
| POST | `/v1/jobs` | Validated label-free batch; deterministic submission ID; HTTP 202 |
| GET | `/v1/jobs/{id}` | Owner-only durable job status/result |

Dispositions are `investigating`, `escalated`, `dismissed` and `confirmed`. A disposition is an analyst annotation, not a ground-truth training label. Notes are 1–4,000 characters. Event IDs are bounded safe ASCII identifiers; amounts and timestamps must be finite and nonnegative. Batch size is 1–500. Missing identity fields are allowed; unknown fields are rejected.

The explanation reports calibrated serving score, raw logistic and R-GCN scores, model version, graph schema through the model manifest, cutoff, input missingness and a statement about uncertainty. Evidence is observational and does not claim feature attribution. Nodes are pseudonymized except demo transaction identifiers. Export includes only the caller's notes.
