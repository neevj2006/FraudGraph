# Full IEEE-CIS tabular evaluation

This separate experiment uses all 590,540 labeled transactions and evaluates tabular models only. The public-cohort GNN results remain separate and frozen. No full-dataset GNN performance is claimed.

Chronological split: 355,520 training, 117,667 validation and 117,353 final-test transactions. Earlier validation selects models; later validation fits Platt calibration. The three seeded runs are deterministic for these configurations; zero variation is not statistical certainty.

| Model | Validation AP | Final AP | Precision@100 | Recall@100 | Fraud value fraction |
|---|---:|---:|---:|---:|---:|
| logistic | 0.0672 | 0.0528 | 17.00% | 0.42% | 0.07% |
| xgboost | 0.1052 | 0.0826 | 30.00% | 0.75% | 0.37% |
| xgboost_graph | 0.1840 | 0.1262 | 33.00% | 0.82% | 1.33% |

The frozen selection is xgboost_graph. Its calibrated final AP is 0.1262; Brier score is 0.0316 and ECE is 0.0022. There are 4,025 fraud cases in the holdout. Recall at 1% false-positive rate is 8.60%.

Top-100 metrics describe a fixed total review budget over this entire holdout, not a daily alert rate. This is much more selective than top-100 on the small cohort, so the two experiments are not directly comparable on recall. Scores do not establish identity, guilt or causal evidence.

The row-bootstrap AP interval is 0.1184 to 0.1355. The 400-repeat bootstrap ignores temporal and entity dependence and is only a descriptive uncertainty estimate.

Training plus validation preprocessing and fitting took 207.6 seconds. Final evaluation including history feature reconstruction and uncertainty calculation took 219.8 seconds. These are batch observations, not API latency benchmarks or peak memory measurements.

| Unseen signature slice | Rows | Frauds | Calibrated AP |
|---|---:|---:|---:|
| account | 17335 | 602 | 0.1004 |
| card | 2427 | 94 | 0.2377 |
| device | 892 | 143 | 0.2147 |
| address | 32 | 4 | 0.1022 |
| merchant | 0 | 0 | unavailable |

This closes the full-dataset tabular comparison and longer-horizon evaluation. It does not establish that the full-batch graph implementation fits local memory. The subsequent [full-data GNN comparison](scaled-gnn-results.md) measures the separate disk-backed implementation and retains these tabular outcomes unchanged. The source schema omits many original IEEE-CIS attributes; these are deliberately simple project baselines, not competition-leading models.

The final was opened once after verifying model, data and code checksums. No subsequent model selection or tuning used the final outcomes. The full baseline bundle is an offline experiment; the serving application continues to use its compatible frozen cohort bundle.
