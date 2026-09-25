"""Exact batch algebra for the repository's fixed two-layer SAGE and R-GCN.

R-GCN entity snapshots start at zero and only carry prior transaction features
through the first layer. Means therefore do not depend on learned weights.
SAGE computes first-layer states for each batch's complete one-hop sources.
"""

import numpy as np
import torch


def tensor(a):
    return torch.from_numpy(np.array(a, dtype=np.float32, copy=True))


def forward_batch(model, cache, ids):
    ids = np.asarray(ids, dtype=np.int64)
    x = tensor(cache.x[ids])
    if model.kind == "rgcn":
        first, second = model.conv1, model.conv2
        if first.num_bases is not None or first.num_blocks is not None or first.aggr != "mean":
            raise ValueError("Only the frozen unregularized mean R-GCN architecture is supported")
        own = torch.relu(x @ first.root + first.bias)
        h = own @ second.root + second.bias
        means = tensor(cache.means[ids])
        present = tensor(cache.counts[ids] > 0)
        for relation in range(5):
            entity = torch.relu(means[:, relation] @ first.weight[2 * relation] + first.bias)
            h = h + (entity @ second.weight[2 * relation + 1]) * present[:, relation, None]
    elif model.kind == "sage":
        if model.conv1.normalize or model.conv1.project or model.conv1.aggr != "mean":
            raise ValueError("Only the frozen mean GraphSAGE architecture is supported")
        neighbors = np.asarray(cache.neighbors[ids]).reshape(len(ids), -1)
        valid = neighbors >= 0
        sources, inverse = np.unique(neighbors[valid], return_inverse=True)
        own = torch.relu(model.conv1.lin_l(tensor(cache.pooled[ids])) + model.conv1.lin_r(x))
        source_h = torch.relu(
            model.conv1.lin_l(tensor(cache.pooled[sources]))
            + model.conv1.lin_r(tensor(cache.x[sources]))
        )
        destination = torch.from_numpy(np.nonzero(valid)[0].astype(np.int64))
        aggregate = torch.zeros((len(ids), source_h.shape[1]), dtype=x.dtype)
        aggregate.index_add_(0, destination, source_h[torch.from_numpy(inverse)])
        aggregate = aggregate / tensor(np.maximum(valid.sum(axis=1), 1))[:, None]
        h = model.conv2.lin_l(aggregate) + model.conv2.lin_r(own)
    else:
        raise ValueError(f"Unsupported model {model.kind}")
    return model.head(torch.relu(h)).squeeze(-1)


def predict_batched(model, cache, ids, batch_size=1024):
    model.eval()
    output = np.empty(len(ids), dtype=np.float64)
    with torch.no_grad():
        for start in range(0, len(ids), batch_size):
            output[start : start + batch_size] = (
                forward_batch(model, cache, ids[start : start + batch_size]).sigmoid().numpy()
            )
    return output
