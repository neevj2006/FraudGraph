import numpy as np
import pytest
import torch
from sklearn.metrics import average_precision_score

from ml.data.dataset import synthetic
from ml.evaluation.metrics import metrics
from ml.features.history import build_features
from ml.graph.build import causal_edges
from ml.models.gnn import GraphClassifier


def test_metrics_hand_calculation():
    result = metrics([1, 0, 1, 0], [0.9, 0.8, 0.7, 0.1], [10, 20, 30, 40], k=2)
    assert result["precision_at_k"] == 0.5
    assert result["recall_at_k"] == 0.5
    assert result["fraud_value_captured"] == 10
    assert result["pr_auc"] == pytest.approx((1 + 2 / 3) / 2)
    assert result["pr_auc"] == average_precision_score([1, 0, 1, 0], [0.9, 0.8, 0.7, 0.1])
    assert metrics([], [], [])["n"] == 0


@pytest.mark.parametrize("kind", ["sage", "rgcn"])
def test_one_batch_overfit_and_causality(kind):
    torch.set_num_threads(2)
    torch.manual_seed(42)
    model = GraphClassifier(4, kind, hidden=16)
    x = torch.randn(16, 4)
    y = (x[:, 0] > 0).float()
    edges = torch.tensor([[0, 1, 2, 3], [6, 7, 8, 9]])
    relations = torch.tensor([0, 1, 2, 3])
    opt = torch.optim.Adam(model.parameters(), lr=0.03)
    for _ in range(150):
        opt.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(model(x, edges, relations), y)
        loss.backward()
        opt.step()
    assert loss.item() < 0.02
    model.eval()
    before = model(x, edges, relations).detach()
    x[15] = 9999
    torch.testing.assert_close(before[:15], model(x, edges, relations)[:15])


@pytest.mark.parametrize("kind", ["sage", "rgcn"])
def test_appending_future_cannot_change_old_predictions(kind):
    df = synthetic(100)
    x = build_features(df)
    torch.manual_seed(4)
    model = GraphClassifier(x.shape[1], kind)
    e, r = causal_edges(df.iloc[:70])
    full_e, full_r = causal_edges(df)
    with torch.no_grad():
        a = model(torch.tensor(x[:70]), torch.tensor(e), torch.tensor(r))
        b = model(torch.tensor(x), torch.tensor(full_e), torch.tensor(full_r))[:70]
    np.testing.assert_allclose(a.numpy(), b.numpy(), rtol=1e-5, atol=1e-5)
