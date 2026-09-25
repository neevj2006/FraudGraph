# FraudGraph

## Project identity

- **Subtitle:** Temporal Heterogeneous GNN for Fraud and Collusion Detection
- **Primary ML task:** Imbalanced transaction classification, entity risk ranking, and optional suspicious-link prediction on a temporal heterogeneous graph
- **Primary product task:** Help fraud analysts detect coordinated behavior and inspect the relational evidence behind each score
- **Target users:** Fraud analysts, risk teams, payment-platform operators, and ML engineers

## Project description

FraudGraph is a graph-native risk platform that identifies fraudulent transactions and coordinated fraud rings by modeling relationships among accounts, cards, devices, IP or physical addresses, merchants, and transactions. Conventional tabular fraud models evaluate transactions mostly in isolation and can miss collusion in which individually plausible transactions share infrastructure or identities. FraudGraph makes those relationships first-class model inputs and presents the relevant subgraph to an investigator.

The project must compare simple tabular baselines with graph models, use chronological evaluation, explicitly control leakage, and support unseen-entity testing. The product should expose ranked alerts and evidence; it should not present a risk score as proof of fraud.

## Goals and success definition

1. Build a reproducible pipeline that converts a public fraud dataset into a typed, timestamped graph.
2. Establish logistic-regression and gradient-boosted-tree baselines.
3. Compare a homogeneous GraphSAGE/GAT baseline with one heterogeneous GNN such as R-GCN, HAN, or HGT.
4. Rank suspicious transactions under an operational alert budget.
5. Explain alerts through contributing entities, edge types, graph patterns, and baseline comparison.
6. Package batch inference behind a versioned API and an investigator-facing web application.

The MVP is complete when the pipeline can be reproduced from a documented dataset manifest, all required models are evaluated on a temporal holdout, and a user can open a ranked alert and inspect its supporting subgraph.

## Scope

### MVP

- One public labeled fraud dataset, initially IEEE-CIS Fraud Detection or a suitable prebuilt fraud graph dataset.
- Typed nodes and edges constructed from available identifiers.
- Logistic regression, XGBoost/LightGBM, GraphSAGE/GAT, and one heterogeneous GNN.
- Chronological train/validation/test split with a separate unseen-user/device analysis.
- Batch scoring, ranked suspicious transactions, entity risk views, and interactive graph explanations.
- Model registry, experiment tracking, input-schema validation, health checks, and latency logging.

### Out of scope for the first release

- Real-time payment authorization decisions.
- Automatic account blocking or adverse action.
- Claims that an explanation proves criminal behavior.
- Production use with private financial data.

### Advanced extensions

- Temporal graph networks for streaming events.
- Graph contrastive pretraining.
- Active learning from analyst feedback.
- Fraud-ring clustering and automatic case generation.
- Robustness experiments against adversarial graph manipulation.

## Graph and data specification

### Node types

- **Transaction:** amount, timestamp, product, channel, location, and observed outcome.
- **Account/User:** tenure, verification state, historical activity, and prior risk features available at the cutoff.
- **Card/Payment instrument:** issuer, type, age, and country.
- **Device:** fingerprint, operating system, browser, and first-seen timestamp.
- **IP/Address:** ASN, geolocation, reputation, or address-derived attributes.
- **Merchant:** category, country, and historical chargeback features available before prediction time.

### Edge types

- Account performs transaction.
- Transaction uses card.
- Transaction occurs on device or IP.
- Transaction targets merchant.
- Account owns card or uses device.
- Entities share an identifier or have another explicitly documented relationship.

Every edge must retain its type, timestamp or valid-time window, provenance, and construction rule. Ambiguous identifiers must not be silently treated as identity proof.

### Dataset pipeline

1. Acquire data through a documented, license-compliant process and record immutable checksums.
2. Validate schemas, timestamps, missingness, label distribution, and identifier cardinality.
3. Define the prediction timestamp and ensure features use only earlier information.
4. construct typed nodes and relationships using deterministic mapping rules.
5. Generate chronological train, validation, and latest-window test sets.
6. Create inductive subsets containing unseen accounts, cards, or devices.
7. Optionally inject controlled synthetic collusion rings to test structural sensitivity.
8. Version graph manifests, feature definitions, splits, and preprocessing code.

## ML design

### Model progression

1. Logistic regression on transaction features.
2. XGBoost or LightGBM using tabular features plus handcrafted graph statistics.
3. GraphSAGE or GAT on a simplified homogeneous graph.
4. R-GCN, HAN, HGT, or another heterogeneous message-passing architecture.
5. Optional timestamp-aware neighborhood sampling or temporal graph components.

### Outputs

- Transaction fraud probability.
- Entity risk score for accounts, cards, devices, and merchants where supported.
- Optional suspicious-association link score.
- Calibrated confidence and model version.
- Explanation payload containing influential neighbors, edge types, and graph-pattern summaries.

### Evaluation

- **Primary:** PR-AUC.
- Recall at a fixed false-positive rate.
- Precision@K for the investigation queue.
- Fraud value captured, weighted by transaction amount.
- Calibration error and reliability plots.
- Inductive performance on unseen entities.
- Inference latency and memory use.
- Ablations for graph features, edge types, temporal handling, and model complexity.

Error analysis must cover class imbalance, cold-start entities, sparse/dense neighborhoods, missing identifiers, temporal drift, and false positives caused by legitimate shared devices or addresses.

## Product requirements

- Ranked alert queue with filters for score, value, time, and entity type.
- Transaction detail showing tabular baseline score and graph-model score.
- Interactive subgraph using Cytoscape.js or React Flow.
- Highlight influential neighbors and typed relationships.
- Plain-language pattern summaries, such as several new accounts sharing a device and payment instrument.
- Analyst annotations, disposition, and case export.
- Model/version timestamp and uncertainty visible on every score.
- Audit record of scoring and analyst actions.

## System architecture

- **Web:** Next.js investigation dashboard.
- **API:** FastAPI for scoring, ranked alerts, graph retrieval, and case operations.
- **ML/graph:** Python, PyTorch Geometric or DGL, and offline graph-construction jobs.
- **Storage:** PostgreSQL for users, alerts, cases, and audit metadata; Neo4j or a graph-friendly persisted representation for exploration.
- **Artifacts:** Object storage for datasets, graph manifests, features, and models.
- **Jobs:** Durable background queue for graph builds and batch inference.
- **Tracking:** MLflow or Weights & Biases.
- **Deployment:** Dockerized services with CI, staging/production separation, model rollback, structured logs, metrics, and health checks.

## Suggested repository layout

```text
apps/web
services/api
services/inference
ml/data
ml/graph
ml/features
ml/models
ml/evaluation
infrastructure
tests
docs
model-card.md
architecture.md
```

## Testing and acceptance criteria

- Unit tests cover feature cutoffs, graph construction, schema contracts, and score serialization.
- Leakage tests fail if post-cutoff labels or future aggregate values enter a feature.
- Integration tests build a small graph, score it, and retrieve an explanation.
- Authorization tests protect analyst cases and annotations.
- The test holdout is later in time than training and remains untouched until final evaluation.
- At least two model families are compared, and the chosen model is justified against a simpler baseline.
- Every prediction records model version, feature/graph manifest, cutoff, latency, confidence, and input statistics.
- The public documentation includes setup, architecture, experiments, limitations, screenshots, a demo video, and a model card.

## Delivery milestones

1. Dataset audit and leakage-safe split design.
2. Deterministic graph builder and graph-quality report.
3. Tabular baselines and operational metric baseline.
4. Homogeneous and heterogeneous graph experiments.
5. Explainability payload and error analysis.
6. Batch inference API and investigation dashboard.
7. Containerization, monitoring, reproducibility audit, public case study, and demo.

## Risks and safeguards

- Shared identifiers may be legitimate; explanations must be evidence, not accusations.
- Random splits can inflate performance; use chronological and inductive testing.
- Labels may be delayed or biased; document label provenance and uncertainty.
- Graph construction can leak outcomes; review every aggregate and relationship cutoff.
- Dataset and tool licenses must be verified before redistribution.

## Resume-ready description

Built a local temporal graph fraud-investigation workbench using FastAPI, Next.js and PyTorch Geometric; compared five model families on 590,540 IEEE-CIS transactions. Implemented exact batched GraphSAGE/R-GCN computation under a 2 GiB memory limit, chronological leakage tests, calibrated ranking and auditable case workflows. Reported GraphSAGE held-out AP 0.1093 against a history-feature tree's 0.1262, with explicit disclosure of prior tabular holdout inspection. Verified 27 backend tests and six browser workflows.
