"""Compact causal neighbor indexes and fixed feature aggregates on disk."""

from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.dataset import ENTITIES


def build_neighbors(frame, path):
    path = Path(path)
    table = np.lib.format.open_memmap(path, mode="w+", dtype=np.int32, shape=(len(frame), 5, 8))
    table[:] = -1
    history = defaultdict(lambda: deque(maxlen=8))
    pending = []
    previous = None
    for idx, row in enumerate(frame[["time", *ENTITIES]].itertuples(index=False, name=None)):
        timestamp, *values = row
        if previous is not None and timestamp < previous:
            raise ValueError("Events must be chronologically ordered")
        if timestamp != previous:
            for key, old in pending:
                history[key].append(old)
            pending.clear()
            previous = timestamp
        for relation, value in enumerate(values):
            if pd.isna(value):
                continue
            key = (relation, value)
            earlier = history[key]
            if earlier:
                table[idx, relation, : len(earlier)] = earlier
            pending.append((key, idx))
    table.flush()
    return table


def build_aggregates(x, neighbors, folder, block=2048):
    folder = Path(folder)
    means = np.lib.format.open_memmap(
        folder / "relation_means.npy", mode="w+", dtype=np.float32, shape=(len(x), 5, x.shape[1])
    )
    pooled = np.lib.format.open_memmap(
        folder / "pooled_means.npy", mode="w+", dtype=np.float32, shape=x.shape
    )
    counts = np.lib.format.open_memmap(
        folder / "counts.npy", mode="w+", dtype=np.uint8, shape=(len(x), 5)
    )
    for start in range(0, len(x), block):
        end = min(len(x), start + block)
        ids = neighbors[start:end]
        valid = ids >= 0
        count = valid.sum(axis=2)
        summed = (x[np.maximum(ids, 0)] * valid[..., None]).sum(axis=2)
        means[start:end] = summed / np.maximum(count[..., None], 1)
        pooled[start:end] = summed.sum(axis=1) / np.maximum(count.sum(axis=1)[:, None], 1)
        counts[start:end] = count
    for array in (means, pooled, counts):
        array.flush()


class GraphCache:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.x = np.load(self.folder / "x.npy", mmap_mode="r")
        self.neighbors = np.load(self.folder / "neighbors.npy", mmap_mode="r")
        self.means = np.load(self.folder / "relation_means.npy", mmap_mode="r")
        self.pooled = np.load(self.folder / "pooled_means.npy", mmap_mode="r")
        self.counts = np.load(self.folder / "counts.npy", mmap_mode="r")
