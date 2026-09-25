# Synthetic validation error review

These are observed synthetic validation errors under the frozen top-100 policy. The review uses known generator signatures for diagnosis only; those marker strings are not model inputs. It does not establish the cause of a real-world error or change the model.

## False Positives

Available: 78. Reviewed below: 25.

| Transaction | Score | Amount | Prior device events | Missing IDs | Observed context |
|---|---:|---:|---:|---:|---|
| TX-001086 | 0.175 | 145.11 | 28 | 0 | Injected shared-infrastructure cohort |
| TX-001087 | 0.041 | 25.18 | 11 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001091 | 0.170 | 6.22 | 76 | 0 | Legitimate shared terminal |
| TX-001092 | 0.040 | 173.44 | 6 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001093 | 0.101 | 80.60 | 77 | 0 | Legitimate shared terminal |
| TX-001094 | 0.076 | 101.23 | 0 | 1 | Missing device signature |
| TX-001097 | 0.170 | 76.01 | 31 | 0 | Injected shared-infrastructure cohort |
| TX-001106 | 0.054 | 85.75 | 78 | 0 | Legitimate shared terminal |
| TX-001111 | 0.041 | 107.50 | 9 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001112 | 0.047 | 5.42 | 11 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001114 | 0.065 | 59.96 | 79 | 0 | Legitimate shared terminal |
| TX-001118 | 0.076 | 53.49 | 80 | 0 | Legitimate shared terminal |
| TX-001119 | 0.056 | 83.57 | 1 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001131 | 0.236 | 835.04 | 26 | 0 | Injected shared-infrastructure cohort |
| TX-001138 | 0.036 | 19.56 | 3 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001139 | 0.084 | 119.24 | 81 | 0 | Legitimate shared terminal |
| TX-001140 | 0.573 | 45.02 | 21 | 0 | Injected shared-infrastructure cohort |
| TX-001143 | 0.045 | 45.54 | 12 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001145 | 0.046 | 94.28 | 16 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001149 | 0.061 | 271.28 | 82 | 0 | Legitimate shared terminal |
| TX-001158 | 0.034 | 25.67 | 19 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001159 | 0.044 | 6.86 | 12 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001161 | 0.265 | 95.78 | 22 | 0 | Injected shared-infrastructure cohort |
| TX-001168 | 0.068 | 14.15 | 0 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001175 | 0.037 | 18.01 | 0 | 1 | Missing device signature |

Context counts: Injected shared-infrastructure cohort: 5; Ordinary identifier pattern; outcome requires other evidence: 11; Legitimate shared terminal: 7; Missing device signature: 2.

## False Negatives

Available: 6. Reviewed below: 6.

| Transaction | Score | Amount | Prior device events | Missing IDs | Observed context |
|---|---:|---:|---:|---:|---|
| TX-001169 | 0.014 | 54.21 | 10 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001179 | 0.017 | 167.27 | 16 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001188 | 0.015 | 90.02 | 15 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001231 | 0.011 | 46.52 | 5 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001327 | 0.018 | 140.67 | 11 | 0 | Ordinary identifier pattern; outcome requires other evidence |
| TX-001430 | 0.019 | 67.08 | 16 | 0 | Ordinary identifier pattern; outcome requires other evidence |

Context counts: Ordinary identifier pattern; outcome requires other evidence: 6.

## Interpretation and follow-up

A negative label in the injected shared-infrastructure cohort is deliberately possible in the generator. Shared infrastructure raises risk without guaranteeing fraud. Public-terminal false positives would require context about legitimate sharing; do not automatically blacklist the signature.

Ordinary-pattern false negatives are consistent with the generator's low-rate independent fraud, which may have little recoverable relational signal. This is a hypothesis based on the simulation, not a causal explanation. Missing identifiers also remove evidence, matching the separate robustness result.

Measurable future experiments: evaluate missing-identifier training augmentation on a new validation window; compare workload and captured value against the historical-feature tree; gather independent context for shared hubs. Keep the current final holdout closed and the serving model frozen.

There are fewer than 25 false negatives in this validation window. The review includes all six available false negatives at the fixed threshold. The separate public-cohort review now includes 25 false positives and 25 false negatives; see [public results](ieee-results.md). This synthetic review remains unchanged.
