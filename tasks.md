# Development roadmap

Implementation checklist and future work. See [release status](docs/completion.md) and [verification](docs/verification.md). Checkboxes retain their recorded status; unchecked items require separate verification.

## Phase 0 â€” Set up a reproducible engineering foundation

- [x] Write `README.md` with the problem statement, intended user, non-goals, setup commands, and current project status.
- [x] Create the repository skeleton from `project_idea.md`: `ml/data`, `ml/graph`, `ml/features`, `ml/models`, `ml/evaluation`, `services/api`, `apps/web`, `tests`, `docs`, and `infrastructure`.
- [x] Create a Python environment and a minimal dependency file. Begin with only data/science and test tooling; add graph and web dependencies when their phases start.
- [x] Add `pyproject.toml` with formatter, linter, and test configuration.
- [x] Add `.gitignore`, `.env.example`, and a configuration module. Never commit datasets, credentials, model weights, or generated artifacts.
- [x] Add a `Makefile`, task runner, or documented commands for setup, linting, testing, and running experiments.
- [x] Write one trivial unit test and run it locally to verify the test setup.
- [x] Create `docs/learning-log.md` and explain, why a lockfile, random seed, and data checksum solve different reproducibility problems.

**Exit check:** a new developer can clone the repository, install it from the documentation, and run linting and tests successfully.

---

## Phase 1 â€” Frame fraud detection as an ML decision problem

- [x] Write `docs/problem-framing.md` defining one prediction row, the target, prediction time, label observation window, and who acts on the prediction.
- [x] Draw a timeline for a transaction showing event time, prediction time, feature cutoff, and when its fraud label becomes known.
- [x] Create a two-by-two confusion matrix and describe the practical cost of each cell for a fraud analyst.
- [x] Explain why accuracy and ROC-AUC can look strong on rare fraud while operational performance remains poor.
- [x] Implement PR-AUC, precision, recall, and precision@K on a tiny hand-written example; verify the results against a library implementation.
- [x] Define an initial alert-budget assumption, such as the top 100 transactions per evaluation window. Mark it as a product assumption to revisit.
- [x] Write a short leakage checklist covering future aggregates, delayed labels, entity histories, preprocessing fit, graph edges, and neighbor sampling.

**Exit check:** `docs/problem-framing.md` makes it unambiguous what information is available when a prediction is produced and which metric decides whether the model is useful.

---

## Phase 2 â€” Select, acquire, and audit one dataset

- [ ] Compare IEEE-CIS with one graph-ready public fraud dataset using availability, license, timestamps, identifiers, labels, size, and fit to the intended graph.
- [x] Record the decision in `docs/dataset-decision.md`; choose exactly one dataset for the MVP.
- [x] Create `ml/data/download.py` or precise manual acquisition instructions. Do not redistribute data unless its license permits it.
- [x] Create a dataset manifest containing source URL, retrieval date, license notes, file sizes, and SHA-256 checksums.
- [x] Define the raw schema with expected column names, types, nullable fields, and basic constraints.
- [x] Write a validation command that fails clearly on missing columns, invalid timestamps, duplicate primary keys, or unexpected label values.
- [x] Build a reproducible audit report covering row count, time range, fraud rate, missingness, amount distribution, identifier cardinality, and label delay if available.
- [ ] Plot fraud prevalence and transaction volume over time; write down at least three observations without claiming causation.
- [ ] Sample and inspect suspicious-looking and normal rows to learn what the encoded fields actually mean.

**Exit check:** raw data can be independently verified from the manifest, and the audit report identifies the exact columns that can form nodes, edges, features, timestamps, and labels.

---

## Phase 3 â€” Build leakage-safe chronological splits

- [x] Sort events by the chosen prediction timestamp and choose documented train, validation, and test time windows.
- [x] Implement split generation in `ml/data/splits.py`; save only stable row identifiers and split metadata, not duplicated raw data.
- [x] Fit imputers, encoders, scalers, and vocabulary mappings on training data only.
- [x] Add tests proving `max(train_time) < min(validation_time)` and `max(validation_time) < min(test_time)`.
- [x] Add a test that deliberately introduces a future-derived feature and confirms the leakage guard rejects it.
- [x] Define unseen-account, unseen-card, and unseen-device subsets based only on whether an identifier appeared in training.
- [x] Measure class rate, missingness, and identifier novelty per split to quantify temporal drift.
- [x] Seal the test split: add a project rule that test metrics are produced only by a dedicated final-evaluation command.

**Exit check:** one command deterministically recreates split manifests, all temporal invariants pass, and the unseen-entity subsets have documented sizes.

---

## Phase 4 â€” Establish non-ML and tabular baselines

- [x] Create a non-ML baseline, such as ranking by transaction amount or a simple frequency rule.
- [x] Build a leakage-safe transaction feature pipeline with numeric imputation, categorical handling, and explicit feature names.
- [ ] Train logistic regression with class weighting. Document the loss and regularization settings.
- [x] Train one boosted-tree model: XGBoost or LightGBM, not both initially.
- [x] Use a single experiment interface so every run records config, seed, code version, feature version, split version, runtime, and metrics.
- [x] Evaluate on validation data with PR-AUC, recall at a fixed false-positive rate, precision@K, amount captured, and a calibration plot.
- [x] Tune only a small, predeclared set of hyperparameters; record every attempted configuration rather than selecting a lucky run silently.
- [x] Perform error analysis by transaction amount, time window, missingness, and unseen entities.
- [x] Write `docs/tabular-baseline.md` explaining which model wins, by which metric, and whether the improvement is operationally meaningful.

**Exit check:** the boosted model and logistic regression run through the same reproducible pipeline and are compared against a non-ML rule on the validation split.

---

## Phase 5 â€” Design the graph before using a GNN

- [x] Write `docs/graph-schema.md` listing each node type, its stable key, allowed features, and first-seen time.
- [x] For every edge type, document source, destination, direction, timestamp, provenance, construction rule, and leakage risk.
- [x] Decide how a transaction becomes a node and why identifiers such as a shared device are evidence of a relationship rather than proof of common ownership.
- [x] Implement deterministic ID mapping from raw identifiers to internal typed node IDs.
- [ ] Build a tiny hand-written graph fixture with a few transactions, users, cards, devices, and one plausible collusion pattern.
- [x] Implement graph construction from training events first; add validation-time nodes and permissible historical edges without exposing future events.
- [x] Add tests for node/edge counts, types, timestamps, duplicate handling, unknown identifiers, and deterministic output.
- [x] Produce a graph-quality report with counts by type, degree distributions, isolated nodes, components, duplicate edges, and high-degree hubs.
- [x] Inspect the highest-degree identifiers and document legitimate reasons a device, address, or merchant might be shared.
- [x] Version and save a graph manifest containing schema version, data checksum, split version, feature cutoff, node mappings, and construction parameters.

**Exit check:** rebuilding from the same inputs produces the same graph manifest, and no edge or node feature uses information after its allowed cutoff.

---

## Phase 6 â€” Evaluate graph statistics before message passing

- [x] Implement cutoff-aware features such as prior transaction count, prior fraud-independent activity, unique devices per account, accounts per device, and time since first seen.
- [x] Compute every historical statistic using only events strictly earlier than the scored transaction.
- [x] Add unit tests using the tiny graph fixture with exact expected values at multiple timestamps.
- [x] Add selected graph statistics to the boosted-tree baseline.
- [x] Compare tabular-only versus tabular-plus-graph-statistics using the same validation window and seeds.
- [x] Investigate false positives caused by legitimate hubs and add safe features or analysis slices rather than hard-coded accusations.
- [x] Record an ablation table and decide whether the graph contains predictive signal beyond transaction columns.

**Exit check:** graph features improve at least one declared operational metric or there is a documented, evidence-based decision to revise the graph construction before proceeding.

---

## Phase 7 â€” Build a homogeneous GraphSAGE baseline

- [ ] Convert the graph fixture into PyTorch Geometric or DGL objects and document every tensor's shape and meaning.
- [x] Define a simplified homogeneous graph and explicitly document what type information is discarded.
- [x] Implement a two-layer GraphSAGE model for transaction classification.
- [x] Write a one-batch overfit test; the model should nearly memorize a tiny training sample before running a full experiment.
- [x] Implement training with weighted binary cross-entropy or focal loss only after explaining the chosen objective.
- [x] Keep raw logits for the loss; apply sigmoid only for probabilities and metrics.
- [x] Add early stopping based on validation PR-AUC and save the best checkpoint with its manifest.
- [x] Evaluate repeatability across at least three seeds and report mean and variation.
- [x] Compare GraphSAGE with the strongest tabular model on accuracy-independent operational metrics, latency, and memory.
- [x] Evaluate unseen-entity subsets separately to test GraphSAGE's inductive claim.

**Exit check:** the one-batch test passes, training is reproducible, tensor shapes are documented, and GraphSAGE is compared with the tabular baseline.

---

## Phase 8 â€” Add one heterogeneous GNN

- [ ] Compare R-GCN, HAN, and HGT on conceptual fit, complexity, library support, and dataset scale; select one and document the decision.
- [x] Create the heterogeneous graph representation with node-type feature matrices and typed edge indices.
- [x] Add schema and shape assertions for every node and relation type.
- [x] Implement the smallest useful heterogeneous model before adding attention, temporal encodings, or deep stacks.
- [x] Run a tiny forward-pass test and a one-batch overfit test.
- [x] Match the homogeneous baseline's split, feature availability, sampling budget, seed count, and evaluation code.
- [x] Run edge-type ablations to learn which relations contribute and whether any apparent gain comes from leakage-prone structure.
- [x] Compare tabular, tabular-plus-statistics, GraphSAGE, and the heterogeneous model in one experiment table.
- [ ] Choose the MVP model using usefulness, calibration, robustness, latency, memory, and simplicityâ€”not PR-AUC alone.

**Exit check:** the selected model beats or usefully complements the simpler baseline under the declared alert budget; otherwise ship the simpler model and document the negative result.

---

## Phase 9 â€” Calibrate scores and create defensible explanations

- [x] Fit Platt scaling or isotonic calibration using validation predictions only and compare reliability diagrams and expected calibration error.
- [x] Choose an alert threshold or top-K policy from the validation set using the documented analyst budget.
- [x] Define a versioned explanation payload containing score, calibrated confidence, baseline score, influential entities, typed edges, pattern summaries, cutoff, and model version.
- [x] Implement a model-independent evidence subgraph containing only time-valid nodes and edges near the transaction.
- [ ] Add model-specific attribution only if it is stable enough to test; clearly distinguish attribution from causal explanation.
- [x] Generate plain-language summaries from deterministic templates, such as shared-device counts, rather than an unconstrained text model.
- [x] Test explanations for empty neighborhoods, high-degree hubs, missing identifiers, and unseen entities.
- [x] Review at least 25 false positives and 25 false negatives; categorize failure modes and propose measurable fixes.
- [x] Write user-facing language stating that a score and its subgraph are investigation aids, not proof of fraud.

**Exit check:** every alert can be traced to versioned inputs and shows time-valid relational evidence without overstating what the evidence proves.

---

## Phase 10 â€” Package batch inference behind a FastAPI service

- [x] Write an API contract before implementation for health, model metadata, ranked alerts, transaction detail, evidence subgraph, annotation, and case export.
- [x] Create request/response models with schema validation and version fields.
- [x] Separate model loading, scoring, persistence, and HTTP handling so each can be tested independently.
- [x] Implement batch scoring as an idempotent job with a stable run ID and model/graph/feature manifests.
- [x] Store alerts, cases, analyst annotations, model metadata, and audit events in PostgreSQL.
- [x] Start with a graph-friendly persisted representation that meets query needs; introduce Neo4j only after measuring a concrete limitation.
- [x] Add structured logs for request ID, model version, latency, input statistics, and failures without logging sensitive raw identifiers.
- [x] Add health and readiness checks that distinguish a live process from a loaded, usable model.
- [x] Write integration tests that build the tiny graph, score it, fetch an alert, retrieve its explanation, and create an annotation.
- [x] Add authorization tests before exposing analyst cases or annotations.

**Exit check:** a clean environment can start the API, run the end-to-end fixture test, and retrieve a fully versioned explanation payload.

---

## Phase 11 â€” Build the investigator dashboard

- [x] Sketch the analyst journey: open queue â†’ filter â†’ inspect alert â†’ explore evidence â†’ annotate â†’ export case.
- [x] Scaffold the Next.js application and create a typed API client from the documented contracts.
- [x] Build a ranked alert queue with filters for score, amount, time, and entity type.
- [x] Build transaction detail showing tabular and graph scores, calibration, model version, cutoff, and uncertainty.
- [x] Add an interactive Cytoscape.js or React Flow subgraph with a legend for node and edge types.
- [ ] Highlight influential neighbors while keeping the full visible evidence distinguishable from model attribution.
- [x] Add analyst disposition, notes, and case export with an audit event for every change.
- [x] Handle loading, empty, stale-model, partial-data, and API-error states explicitly.
- [ ] Test keyboard navigation, color contrast, responsive layout, and performance on a high-degree evidence graph.
- [x] Conduct five task-based usability walkthroughs, even if initially self-run, and record friction points.

**Exit check:** a user can complete the full analyst journey against real API responses without inspecting raw JSON or running a notebook.

---

## Phase 12 â€” Final evaluation, hardening, and public case study

- [x] Freeze code, chosen model, features, graph schema, calibration method, and alert policy before opening the test split.
- [x] Run the final test evaluation once and report all declared metrics, unseen-entity slices, latency, memory, and confidence intervals where practical.
- [ ] Run ablations for graph features, edge types, temporal handling, and model complexity.
- [x] Test sensitivity to missing identifiers, legitimate hubs, temporal drift, and small controlled graph perturbations.
- [x] Write `model-card.md` covering intended use, prohibited use, data, evaluation, limitations, ethical risks, and monitoring needs.
- [x] Write `architecture.md` with data flow, trust boundaries, artifacts, services, and failure modes.
- [x] Containerize the API, inference job, database dependencies, and web application.
- [x] Add CI for linting, unit tests, integration tests, schema checks, and a tiny deterministic training smoke test.
- [x] Add model rollback instructions, structured metrics, latency monitoring, and data/score drift checks.
- [x] Perform the local reproducibility audit from a clean source folder using locked dependencies and documented dataset acquisition; remote clone/CI remains deferred until publication.
- [ ] Publish the experiment table, limitations, screenshots, and a short demo video without distributing restricted data.

**Exit check:** the MVP acceptance criteria in `project_idea.md` all pass, the untouched test result is documented, and another person can reproduce the system from the public instructions.

---

## Optional advanced extensions â€” only after the MVP

Choose one extension at a time and require it to beat the frozen MVP under the same evaluation protocol.

- [ ] Add timestamp-aware neighbor sampling or a temporal graph network.
- [ ] Explore graph contrastive pretraining and test whether gains survive unseen-entity evaluation.
- [ ] Cluster suspicious entities into candidate rings and evaluate cluster usefulness with synthetic and labeled cases.
- [ ] Add active learning from simulated analyst feedback while preventing test-label feedback loops.
- [ ] Create controlled synthetic collusion rings to measure structural sensitivity.
- [ ] Test adversarial removal/addition of edges and missing-identifier robustness.
- [ ] Add suspicious-link prediction only after defining a label and avoiding negative-sampling leakage.

---

## MVP progress scoreboard

Update this table only when a phase exit check passes.

| Capability | Required evidence | Status |
|---|---|---|
| Reproducible dataset | Manifest, checksum, schema, audit | Synthetic verified; full IEEE import and audit complete |
| Leakage-safe evaluation | Temporal split tests and inductive subsets | Synthetic and public cohort verified |
| Tabular baselines | Reproducible logistic and boosted-tree runs | Synthetic, public cohort and full dataset verified, three seeds |
| Deterministic graph | Schema, builder tests, quality report | Synthetic and public cohort verified |
| Graph models | Homogeneous and heterogeneous comparisons | Synthetic, public cohort and full dataset verified, three seeds |
| Operational ranking | Precision@K and amount captured at alert budget | Synthetic, cohort and full-data comparisons reported; prior tabular test inspection disclosed |
| Explainable alerts | Versioned evidence payload and failure tests | Local/public-cohort workflow verified; 25 FP and 25 FN diagnostic review recorded |
| Batch API | End-to-end integration test | SQLite and PostgreSQL verified; public-cohort worker verified |
| Investigator UI | Completed analyst workflow | Five synthetic journeys and a public-cohort journey passed |
| Responsible release | Model card, limitations, reproducibility audit | Final local audit passed; publication deferred |

## Evaluation rules

- Prefer a simpler model when a more complex model does not produce a meaningful, repeatable operational gain.
- Never use random train/test splits for the headline result.
- Never fit preprocessing, calibration, thresholds, or feature vocabularies on the test set.
- Treat shared identifiers as relational evidence, not identity or guilt.
- Record negative experiments; they are part of the engineering result.
- Add infrastructure only when the current milestone needs it. A working, measured pipeline is more valuable than an elaborate empty architecture.
