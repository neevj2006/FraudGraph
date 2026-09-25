"""Tuple-based equivalent of the original nineteen causal history features."""

from collections import defaultdict

import numpy as np

from ml.data.dataset import ENTITIES


def build_features_fast(frame):
    """Process each timestamp together; labels never enter feature state."""
    times = frame.time.to_numpy()
    if len(times) and np.any(times[1:] < times[:-1]):
        raise ValueError("Feature input must be chronological")
    values = np.zeros((len(frame), 19), dtype=np.float64)
    hour = times / 3600 % 24
    values[:, 0] = np.log1p(frame.amount.to_numpy())
    values[:, 1], values[:, 2] = np.sin(hour * np.pi / 12), np.cos(hour * np.pi / 12)
    counts, first, accounts = defaultdict(int), {}, defaultdict(set)
    pending, previous = [], None

    def flush():
        for timestamp, entities in pending:
            account = entities[0]
            for relation, value in enumerate(entities):
                if value is not None:
                    key = (relation, value)
                    counts[key] += 1
                    first.setdefault(key, timestamp)
                    if account is not None:
                        accounts[key].add(account)
        pending.clear()

    for idx, row in enumerate(frame[["time", *ENTITIES]].itertuples(index=False, name=None)):
        timestamp, *entities = row
        if timestamp != previous:
            flush()
            previous = timestamp
        values[idx, 3] = sum(value is None for value in entities)
        for relation, value in enumerate(entities):
            if value is not None:
                key = (relation, value)
                start = 4 + 3 * relation
                values[idx, start : start + 3] = (
                    counts[key],
                    timestamp - first[key] if key in first else 0,
                    len(accounts[key]),
                )
        pending.append((timestamp, entities))
    values[:, 4:] = np.log1p(values[:, 4:])
    return values.astype(np.float32)
