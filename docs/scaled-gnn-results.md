# Full-dataset graph comparison

Both graph families were trained on all 355,520 training transactions, selected using the separate 117,667-row validation window, and evaluated in batches on the 117,353-row held-out window. All 590,540 source transactions participate in the chronological protocol. This window was previously inspected for tabular results; this is a subsequent held-out comparison, not a newly blind evaluation.

The optimized CPU implementation retains complete capped-eight temporal neighborhoods and the original full-batch objective through gradient accumulation. Small-graph predictions and gradients passed equivalence tests. No test-based tuning changed the frozen graph runs.

| Model | Validation AP mean | Final AP | Precision@100 | Recall@100 | Value fraction |
|---|---:|---:|---:|---:|---:|
| logistic | 0.0672 | 0.0528 | 17.00% | 0.42% | 0.07% |
| xgboost | 0.1052 | 0.0826 | 30.00% | 0.75% | 0.37% |
| xgboost_graph | 0.1840 | 0.1262 | 33.00% | 0.82% | 1.33% |
| sage | 0.1984 | 0.1093 | 14.00% | 0.35% | 0.97% |
| rgcn | 0.1980 | 0.0935 | 31.00% | 0.77% | 1.91% |

The validation-selected graph has **lower held-out AP** than the history-feature tree: 0.1093 versus 0.1262. At the top-100 budget its precision is 14%, versus 33% for the tree. This closes the scaling experiment, but does not establish that GNN complexity improves this task. AP, value capture and review-budget precision must be read separately; the frozen validation choice is retained without test-based reselection.

The graph-family selection rule chose **sage**, using three-seed validation means and the 0.005 simplicity margin. Serving-seed comparisons use predeclared seed 11. The previously frozen tabular experiment remains a separate comparator. These results do not silently replace the cohort model used by the investigator application.

The overall five-family comparison chose **sage** from validation before graph final evaluation, using the same 0.005 simplicity margin. The input validation hashes and decision are recorded in [release-selection.json](results/scaled-gnn/release-selection.json). This is the offline research choice; production deployment requires a separate serving integration and acceptance decision.

| Graph family | Validation AP population SD | Best epochs, seeds 11/29/42 |
|---|---:|---|
| sage | 0.0066 | 98, 100, 99 |
| rgcn | 0.0069 | 100, 98, 79 |

5 of 6 runs reached the predeclared 100-epoch limit. Checkpoint epochs are reported above. This measures the declared training budget, not proven optimizer convergence, and no extra epochs were chosen after viewing held-out metrics.

The selected graph's calibrated AP is 0.1093, Brier score 0.0320, ECE 0.0029, and recall at 1% FPR 7.98%. The final window contains 4,025 labeled frauds. Top-100 is a total-window review budget, not a daily alert rate.

The row-bootstrap AP interval is 0.1032–0.1159. It ignores temporal/entity dependence. Neither this interval nor a graph connection establishes causality, identity or operational suitability.

The six-run training command took 1655.4 seconds and sampled 771.8 MiB peak process RSS. The container was capped at 2 GiB without additional swap. Final evaluation including full-history cache preparation took 390.5 seconds. Resource readings are host observations, not production service guarantees.

The entire final command, including integrity checks, took 403.8 seconds and sampled 1044.1 MiB peak process RSS under the same container limit. Monitoring begins after imports, samples every 20 ms, and excludes OS filesystem cache.

| Unseen signature | Rows | Frauds | Calibrated AP |
|---|---:|---:|---:|
| account | 17335 | 602 | 0.0792 |
| card | 2427 | 94 | 0.1571 |
| device | 892 | 143 | 0.2792 |
| address | 32 | 4 | 0.0896 |
| merchant | 0 | 0 | unavailable |

Full-dataset graph training and evaluation are now measured. Production-scale API loading, streaming updates, independently measured analyst utility and automated adverse decisions remain outside this research release. Source data, cached vectors and model weights remain local and excluded from Git.
