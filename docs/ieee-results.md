# IEEE-CIS cohort results

This experiment uses the first 10,000 chronological transactions (about 2.6 days) from the 590,540-row labeled dataset. It is a small public-data cohort benchmark, not full-dataset or production validation. The cohort was chosen for local memory capacity before fitting models. Raw records and identifier signatures are excluded from this report.

Frozen version: `0f0de617a814b8f9`. The unchanged selection policy chose R-GCN from three-seed validation means; serving uses predeclared seed 11. The final holdout was evaluated once.

| Model | Validation AP mean ± SD | Final AP | Precision@100 | Recall@100 | Fraud value fraction |
|---|---:|---:|---:|---:|---:|
| logistic | 0.0258 ± 0.0000 | 0.0491 | 8.00% | 10.53% | 21.91% |
| xgboost | 0.0285 ± 0.0000 | 0.0416 | 2.00% | 2.63% | 3.67% |
| xgboost_graph | 0.0526 ± 0.0000 | 0.1446 | 19.00% | 25.00% | 9.59% |
| sage | 0.0618 ± 0.0300 | 0.1292 | 20.00% | 26.32% | 9.05% |
| rgcn | 0.0849 ± 0.0144 | 0.1160 | 20.00% | 26.32% | 7.84% |

The final window has 1,981 transactions and 76 frauds. The selected model catches 20 frauds in 100 alerts, missing 56; 80 reviewed alerts are false positives. Recall at 1% false-positive rate is 3.95%. Its amount-weighted capture is only 7.84%. This is insufficient evidence for operational deployment.

The history-feature tree beats the selected GNN on final AP. Logistic regression captures more fraud value despite poor ranking. These negative comparisons are retained without changing the frozen selection or retuning on the holdout. Three-seed GNN variation is material; deterministic tree configurations have zero seed variation because subsampling is disabled.

Calibration reduces R-GCN Brier score from 0.2100 to 0.0362; calibrated ECE is 0.0211. Calibration used only 16 positive cases in its fit window, limiting confidence. The 400-repeat row-bootstrap AP interval is 0.0797–0.1811; it ignores temporal/entity dependence.

## Validation error review

The following review covers the first 25 chronological errors of each class at the fixed top-100 budget. It describes observed missingness and prior device activity, not causal explanations or a human investigator study. Full case details remain in the ignored local artifact.

### False Positives

Available: 92; reviewed: 25. 10 reviewed cases have no prior device events. Missing merchant information affects every case; additional missing signatures further limit observable relationships.

| Review case | Prior device events | Missing signature fields | Interpretation |
|---|---:|---:|---|
| 1 | 471 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 2 | 1 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 3 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 4 | 94 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 5 | 1 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 6 | 95 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 7 | 97 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 8 | 1 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 9 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 10 | 1 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 11 | 0 | 1 | No prior device evidence; inspect other signatures and external context |
| 12 | 1 | 1 | Device history exists; coarse sharing alone does not establish fraud |
| 13 | 98 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 14 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 15 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 16 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 17 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 18 | 1 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 19 | 494 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 20 | 496 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 21 | 3 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 22 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 23 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 24 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 25 | 4 | 1 | Device history exists; coarse sharing alone does not establish fraud |

### False Negatives

Available: 32; reviewed: 25. 22 reviewed cases have no prior device events. Missing merchant information affects every case; additional missing signatures further limit observable relationships.

| Review case | Prior device events | Missing signature fields | Interpretation |
|---|---:|---:|---|
| 1 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 2 | 0 | 3 | No prior device evidence; inspect other signatures and external context |
| 3 | 484 | 2 | Device history exists; coarse sharing alone does not establish fraud |
| 4 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 5 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 6 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 7 | 205 | 1 | Device history exists; coarse sharing alone does not establish fraud |
| 8 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 9 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 10 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 11 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 12 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 13 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 14 | 510 | 1 | Device history exists; coarse sharing alone does not establish fraud |
| 15 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 16 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 17 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 18 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 19 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 20 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 21 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 22 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 23 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 24 | 0 | 2 | No prior device evidence; inspect other signatures and external context |
| 25 | 0 | 2 | No prior device evidence; inspect other signatures and external context |

## Robustness and scale

Validation-only perturbations reduce AP from 0.0743 to 0.0542 with 20% additional missing signatures, and to 0.0482 when 10% of devices are mapped to a shared hub. Amount and one-hour time shifts have smaller effects. These diagnostics include calibration-fit rows and do not select new models.

Scoring all five models over 10,000 graph rows took about 4.0 seconds in this run. Validation perturbation process RSS after calls was approximately 493–518 MiB, including libraries and all models; this is not peak memory or a production latency guarantee. These cohort measurements preceded the separate [full-scale graph comparison](scaled-gnn-results.md), which now reports full-data training and longer-horizon evaluation with prior tabular holdout inspection disclosed.

Unseen-account AP is 0.0837 across 1,155 cases (43 frauds). Unseen-card and unseen-device slices contain only 5 and 6 frauds respectively; they do not support a strong generalization claim.

The model code and original synthetic freeze are unchanged. The public-data result is a reproducible research baseline with explicit limitations.
