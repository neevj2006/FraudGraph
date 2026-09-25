"""Bounded graph scoring for the full-history staging bundle."""

import hashlib
import json
from collections import defaultdict, deque
from types import SimpleNamespace

import numpy as np

from ml.data.dataset import ENTITIES
from research.history import build_features_fast
from scaling.batched import predict_batched
from scaling.experiment import logit


def verify_assets(path):
    freeze = json.loads((path / "freeze.json").read_text())
    for name, expected in freeze.get("assets", {}).items():
        target = (path / name).resolve()
        if not target.is_relative_to(path.resolve()):
            raise ValueError("Artifact path escapes bundle")
        h = hashlib.sha256()
        with target.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        if h.hexdigest() != expected:
            raise ValueError(f"Artifact integrity check failed: {name}")


def tail_neighbors(frame, history_rows):
    """Reconstruct only the new rows' neighbors; frozen rows reuse cached tensors."""
    history = defaultdict(lambda: deque(maxlen=8))
    table = np.full((len(frame) - history_rows, 5, 8), -1, dtype=np.int32)
    pending, previous = [], None
    for idx, row in enumerate(frame[["time", *ENTITIES]].itertuples(index=False, name=None)):
        timestamp, *entities = row
        if previous is not None and timestamp < previous:
            raise ValueError("Events must be chronological")
        if timestamp != previous:
            for key, old in pending:
                history[key].append(old)
            pending.clear()
            previous = timestamp
        for relation, value in enumerate(entities):
            if value is None:
                continue
            key = (relation, value)
            old = history[key]
            if idx >= history_rows and old:
                table[idx - history_rows, relation, : len(old)] = old
            pending.append((key, idx))
    return table


def cached_graph(path, frame, scaler, raw):
    folder = path / "cache"
    old_x = np.load(folder / "x.npy", mmap_mode="r")
    old_n = np.load(folder / "neighbors.npy", mmap_mode="r")
    old_p = np.load(folder / "pooled_means.npy", mmap_mode="r")
    history_rows = len(old_x)
    if len(frame) < history_rows:
        raise ValueError("Scoring frame omits frozen history")
    if len(frame) == history_rows:
        return SimpleNamespace(x=old_x, neighbors=old_n, pooled=old_p)
    x = np.concatenate([old_x, scaler.transform(raw[history_rows:]).astype(np.float32)])
    new_n = tail_neighbors(frame, history_rows)
    valid = new_n >= 0
    summed = (x[np.maximum(new_n, 0)] * valid[..., None]).sum(axis=(1, 2))
    pooled = summed / np.maximum(valid.sum(axis=(1, 2))[:, None], 1)
    return SimpleNamespace(
        x=x,
        neighbors=np.concatenate([old_n, new_n]),
        pooled=np.concatenate([old_p, pooled.astype(np.float32)]),
    )


def score_scaled(bundle, path, frame, indices):
    raw = build_features_fast(frame)
    x = bundle["scaler"].transform(raw[indices]).astype(np.float32)
    p = bundle["models"]["xgboost_graph"].predict_proba(x)[:, 1]
    calibrated = bundle["calibrator"].predict_proba(logit(p))[:, 1]
    baseline = bundle["models"]["logistic"].predict_proba(x[:, :4])[:, 1]
    cache = cached_graph(path, frame, bundle["scaler"], raw)
    graph = predict_batched(bundle["models"]["sage"], cache, indices)
    rows = []
    for j, index in enumerate(indices):
        tx = frame.iloc[index]
        rows.append(
            {
                "id": tx.id,
                "time": float(tx.time),
                "amount": float(tx.amount),
                "score": float(calibrated[j]),
                "baseline_score": float(baseline[j]),
                "graph_score": float(graph[j]),
                "model_version": bundle["manifest"]["version"],
                "model": bundle["selected"],
                "dataset": bundle["manifest"]["dataset"],
                "cutoff": float(tx.time),
                "input_statistics": {"missing_identifiers": sum(tx[c] is None for c in ENTITIES)},
                "confidence": "Validation-calibrated estimate; no individual confidence interval",
                "entity_types": [c for c in ENTITIES if tx[c] is not None],
                "status": "open",
                "graph_model": "sage",
            }
        )
    return rows
