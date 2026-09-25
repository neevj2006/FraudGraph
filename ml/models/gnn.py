import copy

import numpy as np
import torch
from sklearn.metrics import average_precision_score
from torch import nn
from torch_geometric.nn import RGCNConv, SAGEConv

from ml.graph.heterogeneous import temporal_heterodata


class GraphClassifier(nn.Module):
    def __init__(self, features, kind="sage", hidden=24):
        super().__init__()
        self.kind = kind
        self.conv1 = (
            SAGEConv(features, hidden) if kind == "sage" else RGCNConv(features, hidden, 10)
        )
        self.conv2 = SAGEConv(hidden, hidden) if kind == "sage" else RGCNConv(hidden, hidden, 10)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x, edges, relations):
        transaction_count = len(x)
        if self.kind == "rgcn":
            graph = temporal_heterodata(x, edges, relations).to_homogeneous(node_attrs=["x"])
            x, edges, relations = graph.x, graph.edge_index, graph.edge_type
        args = (edges,) if self.kind == "sage" else (edges, relations)
        h = torch.relu(self.conv1(x, *args))
        h = torch.relu(self.conv2(h, *args))
        return self.head(h[:transaction_count]).squeeze(-1)


def train_gnn(x, y, edges, relations, train, validation, kind, seed=42, epochs=100):
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    model = GraphClassifier(x.shape[1], kind)
    tensors = (torch.tensor(x, dtype=torch.float32), torch.tensor(edges), torch.tensor(relations))
    targets = torch.tensor(y, dtype=torch.float32)
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    positives = float(targets[train].sum())
    loss_fn = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor((len(train) - positives) / max(1, positives))
    )
    best, stale, state, best_epoch = -1.0, 0, None, 0
    for epoch in range(epochs):
        model.train()
        opt.zero_grad()
        loss = loss_fn(model(*tensors)[train], targets[train])
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            p = model(*tensors)[validation].sigmoid().numpy()
        score = average_precision_score(y[validation], p)
        if score > best + 1e-5:
            best, state, stale, best_epoch = score, copy.deepcopy(model.state_dict()), 0, epoch + 1
        else:
            stale += 1
        if stale >= 15:
            break
    model.load_state_dict(state)
    return model, {"best_epoch": best_epoch, "validation_ap": float(best), "seed": seed}


def predict(model, x, edges, relations):
    model.eval()
    with torch.no_grad():
        return (
            model(
                torch.tensor(x, dtype=torch.float32), torch.tensor(edges), torch.tensor(relations)
            )
            .sigmoid()
            .numpy()
            .astype(np.float64)
        )
