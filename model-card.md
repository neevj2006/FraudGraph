# FraudGraph model card

## Release identity

- Artifact version: `f16663bdd7621c76`.
- Dataset: original **synthetic-demo**, 1,800 events, generator seed 42.
- Serving model: heterogeneous temporal-snapshot R-GCN, seed 11, selected before test evaluation.
- Comparison: amount rule, weighted logistic regression, XGBoost, XGBoost with historical features, GraphSAGE and R-GCN.
- Training seeds: 11, 29, 42. CPU PyTorch Geometric; resolved dependencies in `uv.lock`.

## Intended use

Research, portfolio demonstration, reproducible graph-ML experiments and analyst workflow testing. The system ranks suspicious transactions and provides observed relational evidence for human review. An entity risk view is the maximum associated alert estimate, not an independently trained entity-fraud probability.

Not suitable for production authorization, automated account blocking, credit or eligibility decisions, identifying criminals, or processing private financial data without a separate operational and privacy assessment. No protected-group fairness assessment has been conducted.

## Features, model and calibration

Nineteen numeric features encode amount, relative hour, missing identifiers, prior count, prior age and distinct account signatures for five entity types. All histories use strictly earlier events. No outcome history or neighbor label is used. The scaler fits on training only. R-GCN passes messages through distinct typed entity snapshots at each prediction cutoff; it has two 24-dimensional hidden layers and a scalar logit head. Weighted BCE trains raw logits. Early stopping uses average precision in the earlier validation half.

Model-family selection uses mean validation AP across three seeds, with a 0.005 simplicity tie-break. The first predeclared seed is served rather than cherry-picking the best seed. Platt scaling fits on the later validation half. Scores have no individual confidence interval; displayed confidence language says so.

## Evaluation

Chronological train / validation / final holdout sizes: 1,080 / 360 / 360. Validation is divided into 180 selection and 180 calibration rows. The holdout has 34 positive events. The sealed final command was run once after the ML code and model bundle were frozen.

The calibrated selected model achieved AP **0.6021**, precision@100 **0.30**, recall@100 **0.8824**, recall at 1% FPR **0.2647**, fraud-value capture **0.8976**, Brier score **0.0492**, and ECE **0.0308**. These describe generated data only. Row-bootstrap AP interval: **0.4403–0.7649**, with temporal/entity dependence ignored; it is not a reliable deployment confidence bound.

XGBoost with historical graph statistics captured more value (**0.9730**) and one more fraud in its top 100, despite lower AP (**0.5647**). The GNN is not uniformly superior. Retain the frozen selection and report this negative operational comparison instead of switching models after viewing test results.

Unseen-account AP is 0.4528 (107 rows, 9 positives); unseen-card AP 0.0696 (101 rows, 3 positives); unseen-device AP 0.0864 (69 rows, 2 positives). Address and merchant novelty subsets are empty. Claims of broad inductive generalization are unsupported by these tiny slices.

## Limitations and monitoring

The generator encodes structural fraud signal by construction. Real entities are ambiguous, outcomes delayed and biased, and legitimate users often share infrastructure. IEEE-CIS benchmark acquisition and evaluation are recorded in the separate public-data addenda below. Fraud-score differences can reflect calibration, feature availability or architecture and are not causal attribution. Relation removal tests change inference context without retraining.

The measured all-model full-graph scoring call took about 760 ms for 1,800 graph rows on this Windows CPU environment, excluding model loading and JSON/API transport. This is a single observation, not p95 latency or production capacity. Full-data offline memory measurements are recorded separately below; this synthetic timing is not a full-scale API load result.

Monitor missingness, signature novelty, amount PSI, queue size, score drift, delayed outcome prevalence, calibration, false-positive workload and inference latency. A real release needs labeled retrospective review, cohort-scale testing, validation of label-availability times, threshold/budget agreement, authentication and retention policy, and an explicit rollback decision process.

## Public-data cohort addendum

A separate IEEE-CIS model is frozen at `0f0de617a814b8f9`, trained on the predeclared first 10,000 chronological transactions. The full labeled source (590,540 rows) was imported and audited. See [public results](docs/ieee-results.md) and [protocol](docs/ieee-experiment.md).

R-GCN was selected by three-seed validation AP and retains serving seed 11. On the 1,981-row holdout (76 frauds), calibrated AP is 0.1160, precision@100 is 20%, recall@100 is 26.32%, and amount-weighted fraud capture is 7.84%. The history-feature tree has better AP (0.1446); these comparisons did not change the frozen model. This is an educational research baseline, not a validated operational fraud decision system. Missing-device prevalence, coarse identifiers, only 16 calibration-fit positives, short cohort duration and seed variation constrain interpretation. The subsequent full-dataset GNN experiment is documented in the addendum below.

The original synthetic model above remains separate. No source rows or learned identifier signatures are included in Git-visible reports.

## Full-data tabular addendum

A separate frozen offline tabular comparison now uses all 590,540 IEEE-CIS transactions. Its 117,353-row holdout includes 4,025 frauds. The history-feature tree was selected from validation and achieved AP 0.1262, precision@100 33%, recall@100 0.82%, and value capture 1.33%. Calibration reduced ECE but slightly increased Brier score; it is not a universal improvement. This baseline is not wired into the serving API and does not replace the cohort GNN bundle. See [the full-data report](docs/ieee-full-tabular.md). The subsequent full-dataset GNN experiment is documented in the addendum below.

## Full-data graph scaling addendum

GraphSAGE and R-GCN were each trained with seeds 11, 29 and 42 on all 355,520 training rows, with the separate validation window used for checkpoint selection and calibration. Exact batch computation uses disk-backed temporal neighbors and feature aggregates. Prediction and accumulated-gradient equivalence tests pass against the original small-graph implementations. The declared graph cap and model architectures were preserved.

The overall validation rule selected **sage** before graph final evaluation. On the 117,353-row held-out window, raw GraphSAGE AP is **0.1093** and R-GCN AP is **0.0935**, compared with **0.1262** for the separately frozen history-feature tree. The selected graph's calibrated AP is **0.1093**, precision@100 **14.00%**, recall@100 **0.35%**, Brier **0.0320** and ECE **0.0029**. See [the complete comparison](docs/scaled-gnn-results.md) for value capture, novelty, seed variation and uncertainty.

The six-run training command took 27.6 minutes and sampled 771.8 MiB peak process RSS. Full evaluation, including cache preparation and integrity checks, took 6.7 minutes and sampled 1044.1 MiB. Both ran under a 2 GiB container memory limit without extra swap. These are local offline observations, not API throughput guarantees or evidence of optimizer convergence.

The final window had already been inspected for tabular results. This subsequent graph comparison is not a newly blind evaluation; graph fitting and selection still use training/validation only. The scaled bundle remains separate from the compatible cohort serving artifact. No deployment switch or test-based retuning occurred.
