# Frozen experiment results

All numbers below come from the original 1,800-row synthetic fixture. Source records are copied under `docs/results/`; model weights and raw generated rows remain under ignored `artifacts/release/`.

| Model | Validation AP mean Â± population SD, 3 seeds | Final AP, fixed seed 11 | Final precision@100 | Final value fraction |
|---|---:|---:|---:|---:|
| Logistic | 0.2467 Â± 0.0000 | 0.1296 | 0.13 | 0.7004 |
| XGBoost, transaction only | 0.2068 Â± 0.0000 | 0.1660 | 0.13 | 0.5796 |
| XGBoost + history | 0.5285 Â± 0.0000 | 0.5647 | 0.31 | 0.9730 |
| GraphSAGE | 0.5864 Â± 0.0243 | 0.5331 | 0.29 | 0.8934 |
| Heterogeneous R-GCN | 0.6009 Â± 0.0191 | 0.6021 | 0.30 | 0.8976 |

The deterministic XGBoost configurations do not use stochastic row/column subsampling, so changing seeds does not change their results. Zero variation is not evidence of certainty. There was one predeclared configuration per family, no extensive search, and GNN checkpoint selection used early stopping. The amount rule achieved selection-window AP 0.2341.

The frozen policy chose R-GCN by the highest mean validation AP, outside the 0.005 simplicity margin. Its Platt-calibrated holdout Brier score is 0.0492 and ECE 0.0308, versus 0.2259/0.4112 before calibration. Calibration-fit plots are labeled accordingly and are not held-out validation performance estimates.

The tree with history is competitive and wins on holdout value capture. The held-out comparison therefore provides no consistent advantage for the GNN. The result supports retaining a simple model as an operational comparator. The final holdout has only 34 positive examples; the apparent ranking is uncertain. Separate licensed public-data comparisons are now recorded in [cohort results](ieee-results.md) and [full-data results](scaled-gnn-results.md).

The unseen-card/device populations contain only three/two positives. Their poor AP and small sample sizes prevent a strong inductive-performance claim. Amount drift from training to validation has PSI 0.0280. Time PSI is large by construction because chronological windows do not overlap; it is not an unexpected alert.

`edge-sensitivity.json` reports each relation removed at inference for both graph models. `validation-diagnostics.json` covers time, amount, missingness, neighborhood density and unseen signatures and lists available false positives and false negatives under top-100 review. These diagnostic records are generated programmatically; the available error counts are reported below.

The [error review](error-review.md) examines the first 25 chronological false positives and all six false negatives. Seven reviewed false positives involve the legitimate shared terminal, five the injected shared-infrastructure cohort and two missing device signatures. Eleven have ordinary identifier patterns. The top-100 budget admits some low absolute probabilities in this small window; workload policy contributes to these false positives. All six missed frauds have ordinary identifiers, consistent with limited observable relational signal in the independent-fraud simulation component. None of these observations changes the frozen model or demonstrates causation.

`diagnostics.png` plots observed prevalence by time bin and calibration-fit reliability. Observations: prevalence varies despite a fixed generator; amounts are right-skewed; later windows introduce new signatures. These reflect the simulation and do not imply real-world causes.

The final evaluation is version `f16663bdd7621c76`. Its ML-code checksum, dataset checksum and bundle checksum were verified before the holdout was opened. No final-test-based model changes were made. The 400-repeat row-bootstrap AP range is 0.4403â€“0.7649; entity/temporal dependence limits its interpretation.

Post-freeze **validation-only** perturbations are recorded in `robustness.json`. Baseline AP there is 0.5517; randomly removing 20% of signatures reduces it to 0.1899, while mapping 10% of devices to a common hub gives 0.5367. A 50% amount shift gives 0.5625 and a one-hour time shift 0.5417. The serious missing-identifier sensitivity is a release limitation. These are descriptive results including calibration-fit rows, not additional model selection or a new holdout evaluation. Whole-process RSS after scoring was approximately 539â€“542 MiB with all five models and libraries loaded; this is not peak or incremental model memory.
