# Full-dataset scale assessment

The exact counter scanned the complete canonical IEEE-CIS graph without reading labels or materializing its edges. It matches the actual causal builder on a fixture covering timestamp ties, missing signatures and the eight-neighbor cap. The machine reported about 2.64 GiB free RAM before this assessment.

| Graph | Transactions | Heterogeneous nodes | Heterogeneous edges |
|---|---:|---:|---:|
| Training plus validation | 473,187 | 1,859,805 | 11,531,151 |
| Full inference | 590,540 | 2,329,707 | 14,562,281 |

For full inference, edge indexes and relation IDs require approximately 333 MiB, input node features 169 MiB, and one 24-wide hidden state 213 MiB. An all-edge 24-wide message tensor would require approximately 1.30 GiB; the largest relation alone would require approximately 401 MiB. These are calculated tensor sizes, not measured peak RAM. They need not coexist, and relation-wise execution changes allocations. Python edge lists, autograd, intermediate tensors, imported libraries and allocator overhead are additional costs.

The reference graph builder first stores edges in Python lists, and R-GCN builds its snapshot graph during each forward pass. These implementation choices are suitable for the measured cohort but increase full-scale memory pressure. The assessment does not claim a full training run passed or failed. This assessment motivated a separate memory-bounded graph representation and exact batched computation, now implemented and verified as described below.

A separate full-data tabular experiment completed to establish longer-horizon baselines without modifying the frozen cohort. It uses 355,520 training transactions, 117,667 validation transactions and a previously unopened 117,353-transaction final holdout. Outcomes from the earlier small cohort lie within this new training window; they are not reused as the new test result. Its protocol and aggregate results are documented in [the full-data report](ieee-full-tabular.md).

Exact counts and byte calculations are in [the machine-readable assessment](results/ieee-scale-assessment.json). No raw identities or transactions are included in this report.

## Completed scaling follow-up

The disk-backed implementation passed 10k, 50k, 100k and full-data capacity stages, then completed three-seed GraphSAGE/R-GCN training and full held-out inference under a 2 GiB container limit. It preserves the declared capped neighborhoods without random sampling. See [method and reproduction](scaling.md) and [measured results](scaled-gnn-results.md). This closes the offline GNN scaling gate; production API loading remains a separate question.
