"""Version entity state at each prediction to prevent future-to-past paths."""

import torch
from torch_geometric.data import HeteroData

from ml.data.dataset import ENTITIES


def temporal_heterodata(x, edges, relations):
    data = HeteroData()
    data["transaction"].x = x
    for relation, kind in enumerate(ENTITIES):
        selected = edges[:, relations == relation]
        destinations, inverse = torch.unique(selected[1], sorted=True, return_inverse=True)
        # Each entity is a separate historical snapshot for one prediction cutoff.
        # Zero initial features: first layer learns solely from earlier transactions.
        data[kind].x = x.new_zeros((len(destinations), x.shape[1]))
        data[kind].prediction_index = destinations
        data["transaction", f"history_{kind}", kind].edge_index = torch.stack(
            [selected[0], inverse]
        )
        data[kind, f"context_{kind}", "transaction"].edge_index = torch.stack(
            [torch.arange(len(destinations), device=x.device), destinations]
        )
    data.validate(raise_on_error=True)
    return data
