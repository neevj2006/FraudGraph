# Release status

## V2 extension â€” September 2026

V2 includes rolling research comparisons, local multi-organization staging and service hardening. The earlier assessment below is the historical V1 scope. V2 adds a full-history serving bundle, separate organization databases, identity-provider token validation, viewer/analyst authorization, indexed entity pagination, atomic job quotas, recovery verification and updated tests. See [current evidence and remaining hosted acceptance](readiness-v2.md) and [operating instructions](staging-operations.md).

## Historical V1 release

The local research release is complete, including the full-dataset graph scaling experiment and final local release audit. All 590,540 IEEE-CIS rows participate in the chronological 355,520/117,667/117,353 split. The original synthetic, public cohort and full tabular artifacts remain frozen. See [full GNN results](scaled-gnn-results.md), [scaling method](scaling.md) and [release audit](release-audit.md).

| Area | Verification | Scope limit |
|---|---|---|
| Foundation | Locked environments, lint, backend tests, CI definition, clean API/web builds | Remote CI has not run |
| Data and splits | Full import checksums, audit, strict cutoffs, train-only preprocessing, unseen-signature slices | Source identifiers are ambiguous; label availability is not independently verified |
| Tabular models | Logistic and two tree baselines, three seeds, full-data final metrics | Simple selected attributes, not competition-leading feature engineering |
| Graphs | Deterministic typed causal graph, quality diagnostics, exact disk-backed representation | Eight prior neighbors per relation is the declared graph definition |
| GNN scaling | GraphSAGE and R-GCN, three seeds each, prediction/gradient equivalence, full inference | Specific to the implemented two-layer mean architectures |
| Evaluation | Frozen validation choice, calibration, budget metrics, uncertainty and novelty | Full-data test window was previously inspected for tabular results |
| Explanations | Time-valid evidence, uncertainty language, 25-FP/25-FN cohort diagnostic review | Relationships are not causal attribution or proof of identity |
| API and persistence | Authentication, private cases, idempotent worker, SQLite/PostgreSQL tests, restart persistence | Production identity, retention and operational controls remain outside scope |
| Investigator UI | Five synthetic workflows and a public-cohort workflow, mobile/keyboard checks, local screenshots/video | Automated walkthroughs are not an independent analyst study |
| Release | 27 backend tests, clean-source training/build/browser checks, bundle integrity, data exclusions | Publication and production deployment have not occurred |

The full-data graph bundle is an offline research artifact. The investigator application uses a separate compatible synthetic or public-cohort serving bundle. Full-dataset API loading, live-history accumulation and production throughput have not been validated.

Possible extensions include TGN, contrastive pretraining, active learning, ring clustering, suspicious-link prediction and model-specific attribution.

Source data, cached vectors and model weights remain local and excluded from Git. Screenshots, demonstration video and benchmark reports are included in the documentation.
