# IEEE-CIS experiment protocol

The official Kaggle training transaction and identity files were acquired on 2026-09-13. Raw files remain in Downloads. `scripts/import_ieee_downloads.py` records their full-file SHA-256 hashes and projects only mapped columns before applying the existing adapter. Canonical data and raw-derived projections remain in Git-ignored `data/ieee`.

The first public experiment uses the first 10,000 chronological transactions, including all ties at the last timestamp. This cohort is chosen before fitting models, based on the host's approximately 1.9 GB free RAM at acquisition. It is neither a random sample nor a label-selected subset. Results describe this early contiguous cohort, not all IEEE-CIS transactions or deployment-scale performance.

Run `uv run python -m scripts.train_ieee_cohort` after import. Its protocol records the exact cohort checksum, cutoff, seeds and split policy before training. Five model families use the same chronological 60/20/20 split and seeds 11, 29 and 42. Earlier validation chooses models; later validation fits calibration. The unchanged pipeline selects by mean validation average precision with its existing simplicity tie-break. Final evaluation is run once only after the experiment is frozen.

The original synthetic release remains a separate reproducible artifact. No test labels or public-cohort results are used to retune it. Larger-scale training remains a separate engineering assessment, subject to available memory and measured runtime.

## Execution environment

Canonical import completed on 2026-09-13: 590,540 rows, 3.499% fraud labels, 76.148% missing device signatures and 11.126% missing address signatures. Merchant identity is unavailable. Source checksums and aggregate statistics are in `docs/results/ieee-source-audit.json`.

Training ran in the Linux API image because Windows Application Control blocked the native PyTorch extension. All 15 model/seed runs completed on Docker Engine 29.5.3, producing frozen version `0f0de617a814b8f9`, one final evaluation and validation perturbations. See [cohort results](ieee-results.md).
