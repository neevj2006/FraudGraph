"""Indexed retrieval retaining the original evidence payload semantics."""

from collections import defaultdict

import numpy as np

from ml.data.dataset import ENTITIES
from ml.graph.build import evidence


class EvidenceIndex:
    def __init__(self, frame):
        self.frame = frame
        self.by_id = {value: idx for idx, value in enumerate(frame.id)}
        self.times = frame.time.to_numpy()
        self.accounts = frame.account.to_numpy()
        self.groups = defaultdict(list)
        for idx, row in enumerate(frame[list(ENTITIES)].itertuples(index=False, name=None)):
            for kind, value in zip(ENTITIES, row, strict=True):
                if value is not None:
                    self.groups[kind, value].append(idx)

    def get(self, transaction_id, limit=60):
        index = self.by_id[transaction_id]
        row = self.frame.iloc[index]
        matched, patterns = set(), []
        for kind in ENTITIES:
            if row[kind] is None:
                continue
            ids = np.asarray(self.groups[kind, row[kind]], dtype=np.int64)
            ids = ids[: np.searchsorted(self.times[ids], row.time, side="left")]
            matched.update(ids.tolist())
            if len(ids):
                accounts = {a for a in self.accounts[ids] if a is not None}
                patterns.append(
                    f"{kind.title()} signature appears in {len(ids)} earlier transactions "
                    f"across {len(accounts)} account signatures."
                )
        ordered = sorted(
            matched, key=lambda i: (self.times[i], self.frame.id.iloc[i]), reverse=True
        )
        small = self.frame.iloc[[index, *ordered[:limit]]]
        result = evidence(small, transaction_id, limit)
        result["patterns"] = patterns or ["No earlier shared identifiers were observed."]
        result["truncated"] = len(ordered) > limit
        result["historical_transactions"] = len(ordered)
        return result
