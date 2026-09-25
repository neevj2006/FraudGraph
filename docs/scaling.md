# Full-dataset graph scaling

The implementation under `scaling/` preserves the existing two-layer mean GraphSAGE and temporal entity-snapshot R-GCN architectures. The original `ml/` source and earlier frozen releases remain unchanged.

## Representation and computation

Each transaction stores at most eight strictly earlier neighbors for each of five entity types in a disk-backed int32 array. Equal-timestamp events enter history together after their predictions' neighbors are recorded. Missing identifiers create no shared unknown node. Fixed input-feature means and neighbor counts are cached on disk after fitting the scaler on training rows only.

For GraphSAGE, each prediction batch computes first-layer hidden states for all required source transactions using their cached complete input neighborhoods. It then aggregates those hidden states for the targets' second layer. For R-GCN, entity snapshots have zero initial features: their first-layer states depend only on the per-relation mean of earlier transaction features. This permits the same two-layer output to be computed directly, without constructing millions of snapshot nodes every forward pass.

No neighbor sampling or edge removal is introduced. Training sums loss gradients over every training target, then performs one Adam update per epoch, retaining the original full-batch objective. Small floating-point accumulation differences remain possible. This optimization is specific to these fixed two-layer architectures; it is not a generic implementation for arbitrary GNNs.

Eight tests compare predictions and accumulated parameter gradients against the original implementations across multiple batch sizes, and verify future-row invariance. A separate graph-count test checks tied timestamps, missing identifiers and the neighbor cap. The complete backend suite passed all 27 tests, including real PostgreSQL integration.

## Capacity ladder

Each stage prepared an independent chronological cohort, then ran one training/validation epoch for each graph family. These runs establish capacity, not final performance or model selection. The Linux container had a 2 GiB memory limit and an equal memory-plus-swap limit, so additional container swap was unavailable.

| Source rows | Training/validation cache rows | Two-model check time | Sampled peak process RSS |
|---|---:|---:|---:|
| 10,000 | 8,019 | 0.81 s | 471 MiB |
| 50,000 | 39,993 | 1.46 s | 490 MiB |
| 100,000 | 79,796 | 3.26 s | 515 MiB |
| 590,540 | 473,187 | 13.75 s | 753 MiB |

Full-data cache preparation took 295.6 seconds and sampled approximately 1.02 GiB peak process RSS. RSS is sampled every 20 ms, excludes OS filesystem cache, and may miss shorter peaks. Python import time precedes the monitored command body. Measurements are observations on this host, not general capacity guarantees.

## Frozen experiment protocol

The full experiment uses 355,520 training and 117,667 validation transactions, with the same later 117,353-transaction held-out window used for the tabular comparison. That window has already been inspected for tabular results; the graph comparison must not be described as a newly blind test. Graph fitting, stopping and selection use only training/validation data. Earlier validation selects checkpoints and the graph family; later validation fits calibration. Graph-family selection uses mean AP over seeds 11, 29 and 42, with the original 0.005 simplicity margin. It must still be compared with the simpler full-data tabular baselines.

Training uses a maximum of 100 epochs, patience 15, batch size 1,024, and the existing model dimensions, learning rate, loss weighting and optimizer. Model, dataset and source hashes are frozen before final graph evaluation. The final command refuses to reopen an existing final result. Existing tabular and small-cohort outcomes are retained unchanged.

## Reproduction

First follow dataset acquisition and import in the README so `data/ieee/canonical.csv` exists. These commands are for a fresh copy with no existing full-data experiment outputs. On this completed workspace, retain the frozen outputs rather than rerunning them. The tabular fit supplies the validation comparator needed to freeze the five-family choice:

```powershell
uv run python -m scripts.full_ieee_tabular train
uv run python -m scaling.experiment prepare --cache artifacts/scaling/cache-590540
uv run python -m scaling.experiment train --cache artifacts/scaling/cache-590540 --out artifacts/scaling/full-gnn --epochs 100 --batch-size 1024
uv run python -m scripts.freeze_release_selection
uv run python -m scripts.full_ieee_tabular final
uv run python -m scaling.experiment final --cache artifacts/scaling/cache-590540 --out artifacts/scaling/full-gnn --batch-size 1024
uv run python -m scripts.report_full_ieee
uv run python -m scripts.report_scaled_gnn
```

Use the Linux API image if the host blocks native PyTorch. Mount the workspace at `/workspace`, use it as the working directory, and add Docker flags `--memory=2g --memory-swap=2g`. The API Dockerfile now includes the scaling package. The serving cohort application remains a separate artifact; this experiment does not silently replace its model or investigator cases.

For the overall offline comparison, the same 0.005 validation-AP simplicity margin is applied across all five families, ordered logistic, transaction-only tree, history-feature tree, GraphSAGE, R-GCN. `scripts/freeze_release_selection.py` records that choice from completed validation records before opening graph final metrics. The graph-family calibration and all simpler baseline outcomes remain available regardless of the overall choice. This is an offline comparison choice, not a silent serving deployment.

## Completed experiment

The full three-seed training, frozen model choice and once-only held-out comparison are complete. See [results and measured resource use](scaled-gnn-results.md). The local release audit also verifies the original bundles and the clean runtime source identity.
