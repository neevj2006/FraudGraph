# Engineering notes

A lockfile fixes package resolution. A seed fixes stochastic generation and initialization within a given numerical environment. A checksum verifies exact bytes or canonical content. None substitutes for the others; floating-point hardware and library changes can still cause small training differences.

Building histories by timestamp groups avoids accidental same-time leakage. The feature builder reads all group rows before updating counts, first-seen times or unique-account sets. An apparently harmless shared entity embedding can otherwise pass future information backwards, even when the loss is masked to training nodes.

The first implementation explored relation-labeled transaction edges. The heterogeneous model adds cutoff-specific entity snapshots so node types have an actual role in the computation while preserving causality. Early experiments were not final-holdout evaluations. The recorded release comparison is the source for numerical claims.

Class-weighted binary cross-entropy accepts logits and increases the weight of rare positive examples. Applying sigmoid before `BCEWithLogitsLoss` would apply the sigmoid twice. Tiny-batch overfit tests verify gradient flow for both GNNs before relying on generalization metrics.

Calibrating on the same validation subset used to choose a model can exaggerate confidence. This implementation separates those windows and labels calibration-fit reliability plots as diagnostics. The test set is still needed to assess out-of-sample calibration.

Persisting evidence with the alert protects an investigation from changing neighborhood queries. It also means model rollback must not overwrite historical evidence. Batch inputs use a frozen history policy so retrying the same job produces the same predictions; accumulating live history is a separate design change.

Synthetic performance is useful for integration testing and controlled structural sensitivity, but cannot establish fairness, robustness or utility in real financial operations. Public IEEE-CIS cohort and full-data tabular results are recorded separately; they also do not establish operational suitability.

Scaling did not require changing the graph architecture or randomly sampling its history. The two-layer mean models permit exact batch computation from cached fixed-feature aggregates. Checking both predictions and accumulated parameter gradients against the original implementation is stronger than comparing just a final metric: a similar AP can hide a different computation. Accumulating all target gradients before one optimizer update retains the full-batch training objective.

The six graph runs use validation-only stopping and selection. The later test window had already been inspected for tabular comparisons, so subsequent graph results must disclose that sequence. A once-only command protects a recorded workflow; it cannot make previously observed data newly blind.
