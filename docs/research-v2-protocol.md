# Research improvement protocol

This protocol is written before version-two fitting. Earlier full-data results motivated the questions, so this is retrospective development, not a newly blind confirmation. No new scores or metrics will be calculated on the previously inspected final 20% window. A genuinely independent acceptance study requires new labeled time periods or a separately acquired dataset.

Only the original 355,520-row training prefix is used. Three expanding folds use the following fractions of its distinct timestamps; equal timestamps stay together:

| Fold | Training ends | Checkpoint window ends | Calibration ends | Assessment ends |
|---|---:|---:|---:|---:|
| 1 | 40% | 45% | 50% | 60% |
| 2 | 60% | 65% | 70% | 80% |
| 3 | 80% | 85% | 90% | 100% |

Each scaler fits on that fold's training rows. Histories include earlier events without their labels. Assessment blocks are rolling validation used for development selection; they are not independent final tests. Earlier fold assessments may enter later folds' training, as expected for expanding-window validation. Actual label delays are unavailable, so this does not validate delayed-label operation. The design follows the temporal ordering principle described in [scikit-learn's cross-validation guide](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split), while using timestamp boundaries for irregular transaction arrivals.

Four fixed candidates test two questions:

- `tree_reference`: the existing 100-tree, depth-3, learning-rate-0.06 history-feature XGBoost configuration.
- `tree_regularized`: 250 trees, depth 4, learning rate 0.04, minimum child weight 20, L2 penalty 5, and row/column subsampling 0.8. This is one predefined regularization/capacity package, not an attribution of improvement to an individual parameter. Parameter meanings follow [XGBoost documentation](https://xgboost.readthedocs.io/en/stable/parameter.html).
- `sage_reference`: unchanged 24-wide two-layer GraphSAGE with positive-class-weighted BCE, Adam 0.01 and weight decay 0.0001.
- `sage_unweighted`: exactly the same GraphSAGE and optimizer with unweighted BCE, isolating the loss-weighting change. Both graph candidates use the same complete capped-eight neighborhoods, batch size 1,024, one gradient-accumulated update per epoch, at most 40 epochs and patience 10.

The 40-epoch graph screen is an explicit compute budget, not a claim of convergence or a replacement for the original 100-epoch benchmark. Both trees run seeds 11, 29 and 42 on every fold. The graph screen uses seed 11 on all folds; a graph candidate receives seeds 29 and 42 only if its screen passes the improvement gates against the better eligible three-seed tree. A single-seed graph screen cannot by itself authorize promotion.

Each fitted model is calibrated only on its fold's separate calibration block. The assessment records AP, precision/recall@100, recall at 1% FPR, value capture, Brier score, ECE and fit/prediction time. Seed-level results and negative comparisons are retained. No additional hyperparameter trials are added after reading these assessments.

Promotion requires mean AP at least 0.005 above the reference, mean precision@100 no worse, AP improvement in at least two of three folds, and no fold AP more than 10% below its matching reference. The regularized tree is compared with the reference tree; fully confirmed graph candidates are compared with the best eligible tree. If multiple candidates qualify within 0.005 mean AP, prefer the simpler tree. If no change qualifies, retain the reference tree as the deployment candidate and record the comparison results. This is a development decision, not proof of production effectiveness.

The new tuple-based feature builder must match the original 19 features on ties, missing signatures and appended-future fixtures before experiments run. Original `ml/`, `scaling/` and frozen bundles remain unchanged. Source hashes, fold boundaries, seeds and every completed run are persisted so interrupted work can resume without silently replacing results.

Next stages: package the chosen model for full-history batch serving, verify local staging end to end, then implement and test production controls. External hosting, independent label collection, organizational policies and live analyst acceptance require a concrete target and evidence beyond this benchmark.
