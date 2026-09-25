"""Scale counter must match actual graph construction, including timestamp ties."""

import pandas as pd

from ml.data.dataset import ENTITIES
from ml.graph.build import causal_edges
from scripts.assess_ieee_scale import count_graph


def test_scale_counter_matches_causal_edges():
    frame = pd.DataFrame(
        {
            "time": [0, 0, *range(1, 13)],
            "account": ["a"] * 14,
            "card": ["c"] * 14,
            "device": [None, None, *(["d"] * 12)],
            "address": [None] * 14,
            "merchant": [None] * 14,
        }
    )
    for cutoff in (None, 8):
        subset = frame if cutoff is None else frame[frame.time < cutoff]
        edges, relations = causal_edges(subset)
        actual = count_graph(frame, cutoff)
        assert actual["projected_edges"] == edges.shape[1]
        assert actual["transactions"] == len(subset)
        for relation, kind in enumerate(ENTITIES):
            assert actual["projected_edges_by_relation"][kind] == int((relations == relation).sum())
            assert actual["entity_snapshots_by_relation"][kind] == len(
                set(edges[1, relations == relation])
            )
