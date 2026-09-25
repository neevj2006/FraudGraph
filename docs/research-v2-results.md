# Research improvement: rolling development validation

This experiment uses only the original 355,520-row training prefix. It does not reopen or rescore the previously inspected final window. The three rolling assessment blocks are development validation, not newly blind tests. The [protocol](research-v2-protocol.md) was fixed before fitting.

| Candidate | Fold 1 AP | Fold 2 AP | Fold 3 AP | Mean AP | Mean precision@100 | Seeds per fold |
|---|---:|---:|---:|---:|---:|---|
| tree_reference | 0.1432 | 0.1656 | 0.1230 | 0.1439 | 39.00% | 11, 29, 42 |
| tree_regularized | 0.1431 | 0.1595 | 0.1323 | 0.1450 | 33.78% | 11, 29, 42 |
| sage_reference | 0.1011 | 0.1022 | 0.1269 | 0.1101 | 20.67% | 11 |
| sage_unweighted | 0.0930 | 0.1089 | 0.0935 | 0.0985 | 17.00% | 11 |

The predeclared gates selected **tree_reference** as the staging candidate after 24 fitted runs. Eligibility required an AP gain of 0.005, no loss in mean top-100 precision, improvement in at least two folds and no fold AP loss greater than 10%. A graph candidate screened with only seed 11 cannot be promoted without the two confirmation seeds.

A failed promotion is retained as a negative research result, not followed by extra unrecorded tuning. The graph screen uses a 40-epoch budget and may underfit; it does not establish that longer or different GNN training can never help. The regularized tree changes several parameters together, so its differences cannot be attributed to one parameter.

| Candidate | Mean calibrated Brier | Mean ECE | Total fit seconds |
|---|---:|---:|---:|
| tree_reference | 0.0348 | 0.0063 | 7.2 |
| tree_regularized | 0.0347 | 0.0059 | 17.3 |
| sage_reference | 0.0355 | 0.0071 | 88.3 |
| sage_unweighted | 0.0355 | 0.0061 | 112.6 |

Calibration fits only on each fold's separate calibration block. Individual results, seeds, checkpoint epochs and metric records are retained in [progress.json](results/research-v2/progress.json). The original release metrics remain unchanged. These development outcomes support a local staging choice; new labeled time periods and independent analyst acceptance remain live-use gates.

The tuple-based feature builder passed original-feature equivalence, tied-time, missing-identifier, label-invariance and future-row checks. A separate [same-prefix timing measurement](results/history-benchmark.json) records its measured preprocessing improvement without changing the feature definition.
