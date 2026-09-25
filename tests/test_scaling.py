"""Numerical and causal equivalence to the frozen graph implementations."""

import copy

import numpy as np
import pytest
import torch

from ml.data.dataset import synthetic
from ml.graph.build import causal_edges
from ml.models.gnn import GraphClassifier
from scaling.batched import forward_batch, predict_batched
from scaling.cache import GraphCache, build_aggregates, build_neighbors


def cache_for(frame, x, path):
    path.mkdir()
    np.save(path / "x.npy", x)
    neighbors = build_neighbors(frame, path / "neighbors.npy")
    build_aggregates(x, neighbors, path, block=11)
    return GraphCache(path)


@pytest.mark.parametrize("kind", ["sage", "rgcn"])
@pytest.mark.parametrize("batch_size", [1, 13, 128])
def test_predictions_and_accumulated_gradients_match(tmp_path, kind, batch_size):
    torch.set_num_threads(2)
    torch.manual_seed(7)
    frame = synthetic(60)
    frame["time"] = np.arange(len(frame)) // 3
    # Include a hub, missing nodes, and >8 earlier neighbors per relation.
    frame["device"] = ["hub"] * 55 + [None] * 5
    x = np.random.default_rng(4).normal(size=(len(frame), 6)).astype(np.float32)
    cache = cache_for(frame, x, tmp_path / "cache")
    edges, relations = causal_edges(frame)
    for relation in range(5):
        rows, slots = np.nonzero(cache.neighbors[:, relation] >= 0)
        got = set(zip(cache.neighbors[rows, relation, slots].tolist(), rows.tolist(), strict=True))
        want = set(map(tuple, edges[:, relations == relation].T.tolist()))
        assert got == want
    original = GraphClassifier(6, kind, hidden=9)
    batched = copy.deepcopy(original)
    ids = np.array([59, 0, 32, 1, 20, 7, 49, 3, 18, 55, 41, 9, 35, 12])
    logits = original(torch.tensor(x), torch.tensor(edges), torch.tensor(relations))[ids]
    probabilities = predict_batched(batched, cache, ids, batch_size)
    np.testing.assert_allclose(
        probabilities, logits.detach().sigmoid().numpy(), atol=2e-6, rtol=2e-5
    )
    y = torch.tensor(frame.label.to_numpy()[ids], dtype=torch.float32)
    loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, y)
    loss.backward()
    for start in range(0, len(ids), batch_size):
        prediction = forward_batch(batched, cache, ids[start : start + batch_size])
        part = torch.nn.functional.binary_cross_entropy_with_logits(
            prediction, y[start : start + batch_size], reduction="sum"
        ) / len(ids)
        part.backward()
    for (name, p), (_, q) in zip(
        original.named_parameters(), batched.named_parameters(), strict=True
    ):
        assert p.grad is not None and q.grad is not None, name
        torch.testing.assert_close(p.grad, q.grad, atol=3e-6, rtol=3e-5, msg=name)


@pytest.mark.parametrize("kind", ["sage", "rgcn"])
def test_future_rows_do_not_change_cached_predictions(tmp_path, kind):
    torch.set_num_threads(2)
    frame = synthetic(80)
    x = np.random.default_rng(2).normal(size=(80, 5)).astype(np.float32)
    earlier = cache_for(frame.iloc[:50], x[:50], tmp_path / "earlier")
    full = cache_for(frame, x, tmp_path / "full")
    model = GraphClassifier(5, kind)
    ids = np.arange(50)
    np.testing.assert_array_equal(earlier.neighbors, full.neighbors[:50])
    np.testing.assert_allclose(
        predict_batched(model, earlier, ids), predict_batched(model, full, ids), atol=1e-7
    )
