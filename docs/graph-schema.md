# Temporal graph schema

There are six node types: transaction, account signature, card signature, device signature, address signature and merchant signature. Exploration keys are `type:sha256(value)[:20]`. They are deterministic pseudonyms, not anonymization guarantees. Hash collisions are extremely unlikely at demo scale; sensitive production data needs an explicit keyed pseudonymization and collision policy.

Each transaction associates with its observed nonmissing signatures. Evidence edges retain the event time, relation type, `canonical-event-v1` provenance and `observed-signature-association` rule. The focal transaction's current edges are allowed; every other displayed transaction must have strictly earlier event time. Up to 60 recent related transactions are shown, with truncation clearly reported. Pattern counts use all permitted history, so a displayed subgraph may contain fewer nodes than a pattern count.

## Message-passing representations

The causal projection creates `(earlier transaction → later transaction)` edges per shared signature, sampling the latest eight strictly earlier transactions per relation. Equal-time events are processed together before histories update. No edge crosses backwards in time; missing identifiers never form a common node. A pair may have several distinct relation edges, which is intentional.

GraphSAGE consumes transaction `x: [N,19]`, `edge_index: [2,E]`, and discards the relation array. Two SAGE layers produce `[N,24]`; a linear head produces `[N]` raw logits. Mean aggregation has the standard linear self/neighbor form. For neighbors `[1,3]` and `[3,5]`, the mean is `[2,4]`; a weight `[2,-1]` gives zero before bias and nonlinearity.

The heterogeneous R-GCN constructs a `HeteroData` object with all six types. For each target transaction and relation with history, it creates a **separate entity snapshot**. Its initial feature vector is zero and its `prediction_index` identifies the target cutoff. Ten edge types encode transaction-history-to-entity and entity-context-to-transaction. First-layer entity states summarize permitted prior transactions; the second layer supplies those states to the target. The PyG homogeneous carrier preserves node/edge type indices for R-GCN's relation-specific weights. Only transaction logits are classified.

This makes entity states temporal without a recurrent temporal network. Cold-start entities with no prior events have no historical context node; current transaction features still score them. Future nodes cannot change earlier logits because no future-to-earlier path exists. Tests check this for both model families.

R-GCN was chosen over HAN/HGT for its small, explicit relation transformations and testability. Attention and learned ID embeddings would add complexity without established benefit here. Three-seed training, fixed neighbors, features, windows and metrics make comparisons inspectable, although the architecture depth and effective receptive field differ. No causal interpretation is assigned to a learned weight.

`graph-quality.json` reports relation counts, projection degrees, components, isolated transactions and a time-violation assertion. `edge-sensitivity.json` removes one relation at inference at a time. This is a perturbation test, not retraining without that relation. Tabular versus tabular-plus-history is the explicit trained structural-feature ablation.

Graph traversal by breadth-first search is O(V+E) on the visited subgraph. Shared merchants, NAT addresses, family cards and public terminals can form legitimate hubs; degree is context rather than proof of coordination.
