"""Count causal graph size without materializing edges or reading outcome labels."""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.dataset import ENTITIES


def count_graph(frame, cutoff=None):
    counts = defaultdict(int)
    edges = dict.fromkeys(ENTITIES, 0)
    snapshots = dict.fromkeys(ENTITIES, 0)
    pending = []
    previous = None
    rows = 0
    for row in frame.itertuples(index=False, name=None):
        timestamp, *values = row
        if cutoff is not None and timestamp >= cutoff:
            break
        if previous is not None and timestamp < previous:
            raise ValueError("Input must be chronologically sorted")
        if timestamp != previous:
            for key in pending:
                counts[key] = min(8, counts[key] + 1)
            pending.clear()
            previous = timestamp
        for kind, value in zip(ENTITIES, values, strict=True):
            if pd.isna(value):
                continue
            key = (kind, value)
            prior = counts[key]
            edges[kind] += prior
            snapshots[kind] += int(prior > 0)
            pending.append(key)
        rows += 1
    projected = sum(edges.values())
    entities = sum(snapshots.values())
    hetero_edges = projected + entities
    nodes = rows + entities
    return {
        "transactions": rows,
        "projected_edges_by_relation": edges,
        "entity_snapshots_by_relation": snapshots,
        "projected_edges": projected,
        "heterogeneous_edges": hetero_edges,
        "heterogeneous_nodes": nodes,
        "projected_edge_index_and_relation_bytes": projected * 3 * 8,
        "heterogeneous_edge_index_and_relation_bytes": hetero_edges * 3 * 8,
        "heterogeneous_input_features_bytes": nodes * 19 * 4,
        "one_hidden_state_bytes": nodes * 24 * 4,
        "one_all_edge_hidden_message_tensor_bytes": hetero_edges * 24 * 4,
        "largest_relation_hidden_message_tensor_bytes": max(
            max(edges.values()), max(snapshots.values())
        )
        * 24
        * 4,
    }


def main():
    frame = pd.read_csv("data/ieee/canonical.csv", usecols=["time", *ENTITIES])
    frame = frame[["time", *ENTITIES]]
    times = np.sort(frame.time.unique())
    cutoff = float(times[int(len(times) * 0.8)])
    result = {
        "method": "Exact capped-eight earlier-neighbor and snapshot counts; equal timestamps update together; outcome labels not loaded",
        "training_validation_cutoff_exclusive": cutoff,
        "training_validation": count_graph(frame, cutoff),
        "full_inference": count_graph(frame),
        "memory_caveat": "Calculated tensor sizes, not measured peak RAM. Allocations need not coexist; relation-wise execution may use smaller message tensors. Python graph construction, autograd, optimizer, allocator and library overhead are excluded. No model fitting or holdout metrics.",
    }
    target = Path("docs/results/ieee-scale-assessment.json")
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
