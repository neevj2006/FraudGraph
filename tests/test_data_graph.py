import numpy as np
import pandas as pd
import pytest

from ml.data.dataset import digest, synthetic, validate
from ml.data.splits import chronological, unseen
from ml.features.history import FEATURES, assert_cutoff, build_features
from ml.graph.build import causal_edges, evidence


@pytest.fixture
def fixture():
    return validate(
        pd.DataFrame(
            [
                {
                    "id": str(i),
                    "time": t,
                    "amount": 10,
                    "label": i % 2,
                    "account": a,
                    "card": "shared",
                    "device": "d",
                    "address": None,
                    "merchant": "m",
                }
                for i, (t, a) in enumerate([(0, "a"), (10, "b"), (10, "c"), (20, "a")])
            ]
        )
    )


def test_validation_and_manifest():
    df = synthetic(100)
    assert digest(df) == digest(synthetic(100))
    with pytest.raises(ValueError, match="unique"):
        validate(pd.concat([df, df]))
    for col, value in [("time", -1), ("amount", float("nan")), ("label", 2)]:
        bad = df.copy()
        bad.loc[0, col] = value
        with pytest.raises(ValueError):
            validate(bad)
    with pytest.raises(ValueError, match="Missing"):
        validate(df.drop(columns=["device"]))


def test_split_and_unseen():
    df = synthetic(100)
    split = chronological(df)
    assert df.iloc[split["train"]].time.max() < df.iloc[split["validation"]].time.min()
    assert df.iloc[split["validation"]].time.max() < df.iloc[split["test"]].time.min()
    assert sum(map(len, split.values())) == len(df)
    assert set(unseen(df, split["train"], split["test"])) == {
        "account",
        "card",
        "device",
        "address",
        "merchant",
    }


def test_strict_history_excludes_ties_and_labels(fixture):
    x = build_features(fixture)
    col = FEATURES.index("device_log_prior_count")
    np.testing.assert_allclose(x[:, col], np.log1p([0, 1, 1, 3]))
    fixture.label = 1 - fixture.label
    np.testing.assert_array_equal(x, build_features(fixture))
    altered = fixture.copy()
    altered.loc[3, "amount"] = 999999
    np.testing.assert_array_equal(x[:3], build_features(altered)[:3])
    for time in (20, 21):
        with pytest.raises(ValueError, match="Leakage"):
            assert_cutoff(time, 20)


def test_graph_edges_causal_and_deterministic(fixture):
    edges, rel = causal_edges(fixture)
    assert edges.shape[1] == len(rel)
    assert (fixture.time.to_numpy()[edges[0]] < fixture.time.to_numpy()[edges[1]]).all()
    assert 3 not in rel  # Missing address must not become a shared unknown node.
    np.testing.assert_array_equal(edges, causal_edges(fixture)[0])
    smaller, _ = causal_edges(fixture, omit="device")
    assert smaller.shape[1] < edges.shape[1]


def test_evidence_cutoff_and_truncation(fixture):
    graph = evidence(fixture, "1", limit=0)
    assert graph["truncated"]
    assert all(e["time"] <= 10 for e in graph["edges"])
    graph = evidence(fixture, "1")
    tx = {n["label"] for n in graph["nodes"] if n["type"] == "transaction"}
    assert tx == {"0", "1"}  # Same-time transaction 2 is unavailable history.
    assert evidence(fixture, "0")["historical_transactions"] == 0
    with pytest.raises(KeyError):
        evidence(fixture, "absent")
