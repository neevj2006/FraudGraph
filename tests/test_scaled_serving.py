import joblib
import numpy as np

from ml.data.dataset import synthetic, validate
from ml.features.history import build_features
from ml.graph.build import evidence
from ml.pipeline import probabilities
from scaling.cache import build_aggregates, build_neighbors
from services.inference.evidence import EvidenceIndex
from services.inference.scaled import score_scaled, tail_neighbors


def fixture():
    frame = synthetic(120)
    frame["time"] = np.arange(len(frame)) // 3
    frame["device"] = ["hub"] * 100 + [None] * 20
    return validate(frame)


def test_indexed_evidence_matches_full_history():
    frame = fixture()
    index = EvidenceIndex(frame)
    for row in [0, 50, 90, 119]:
        assert index.get(frame.id.iloc[row]) == evidence(frame, frame.id.iloc[row])


def test_tail_neighbors_match_full_builder(tmp_path):
    frame = fixture()
    full = build_neighbors(frame, tmp_path / "full.npy")
    np.testing.assert_array_equal(tail_neighbors(frame, 90), full[90:])


def test_scaled_serving_matches_reference_scores(artifacts, tmp_path):
    bundle = joblib.load(artifacts / "bundle.joblib")
    bundle["selected"] = "xgboost_graph"
    frame = fixture()
    history = frame.iloc[:90]
    cache = tmp_path / "cache"
    cache.mkdir()
    x = bundle["scaler"].transform(build_features(history)).astype(np.float32)
    np.save(cache / "x.npy", x)
    neighbors = build_neighbors(history, cache / "neighbors.npy")
    build_aggregates(x, neighbors, cache)
    ids = np.arange(90, 120)
    got = score_scaled(bundle, tmp_path, frame, ids)
    expected = probabilities(bundle, frame)
    for key, name in [
        ("score", "calibrated"),
        ("baseline_score", "logistic"),
        ("graph_score", "sage"),
    ]:
        np.testing.assert_allclose([r[key] for r in got], expected[name][ids], atol=2e-6, rtol=2e-5)
