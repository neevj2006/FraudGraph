"""Validation diagnostics; these do not select additional hyperparameters."""

import numpy as np
from sklearn.metrics import average_precision_score

from ml.data.dataset import ENTITIES
from ml.data.splits import unseen
from ml.evaluation.metrics import metrics
from ml.features.history import build_features
from ml.graph.build import causal_edges


def validation_diagnostics(df, split, p):
    idx = split["validation"]
    rows = df.iloc[idx]
    scores = p[idx]
    y, amount = rows.label.to_numpy(), rows.amount.to_numpy()
    slice_masks = {
        "amount_below_100": amount < 100,
        "amount_at_least_100": amount >= 100,
        "missing_identifier": rows[list(ENTITIES)].isna().any(axis=1).to_numpy(),
        "complete_identifiers": rows[list(ENTITIES)].notna().all(axis=1).to_numpy(),
        "first_half": rows.time.to_numpy() < rows.time.median(),
        "second_half": rows.time.to_numpy() >= rows.time.median(),
        **{f"unseen_{k}": mask for k, mask in unseen(df, split["train"], idx).items()},
    }
    history = build_features(df)
    slice_masks["sparse_device"] = history[idx, 10] < np.log1p(3)
    slice_masks["dense_device"] = history[idx, 10] >= np.log1p(3)
    slices = {
        name: metrics(y[mask], scores[mask], amount[mask]) for name, mask in slice_masks.items()
    }
    top = np.argsort(-scores, kind="stable")[: min(100, len(idx))]
    predicted = np.zeros(len(idx), dtype=bool)
    predicted[top] = True
    errors = {}
    for name, mask in (
        ("false_positives", predicted & (y == 0)),
        ("false_negatives", ~predicted & (y == 1)),
    ):
        selected = np.flatnonzero(mask)
        errors[name] = {
            "available": len(selected),
            "requested_review_count": 25,
            "examples": [
                {
                    "id": rows.iloc[i].id,
                    "score": float(scores[i]),
                    "amount": float(amount[i]),
                    "missing_identifiers": int(rows.iloc[i][list(ENTITIES)].isna().sum()),
                    "device_history_count": round(float(np.expm1(history[idx[i], 10]))),
                    "review_status": "automated diagnostic; requires analyst interpretation",
                }
                for i in selected[:25]
            ],
        }
    return {
        "slices": slices,
        "error_review": errors,
        "caveat": "Validation includes model-selection and calibration-fit rows; descriptive only.",
    }


def graph_quality(df):
    import networkx as nx

    edge_index, rel = causal_edges(df)
    graph = nx.Graph()
    graph.add_nodes_from(range(len(df)))
    graph.add_edges_from(edge_index.T.tolist())
    degrees = [degree for _, degree in graph.degree]
    return {
        "transaction_nodes": len(df),
        "unique_entity_signatures": {c: int(df[c].nunique()) for c in ENTITIES},
        "causal_projection_edges": edge_index.shape[1],
        "edges_by_relation": {c: int((rel == i).sum()) for i, c in enumerate(ENTITIES)},
        "isolated_transactions": len(list(nx.isolates(graph))),
        "weak_components": nx.number_connected_components(graph),
        "degree_quantiles": {str(q): float(np.quantile(degrees, q)) for q in [0, 0.5, 0.95, 1]},
        "max_source_time_violation": bool(
            (df.time.to_numpy()[edge_index[0]] >= df.time.to_numpy()[edge_index[1]]).any()
        ),
        "highest_degree_transactions": sorted(
            ({"id": df.iloc[i].id, "degree": d} for i, d in graph.degree),
            key=lambda r: -r["degree"],
        )[:10],
    }


def bootstrap_ap(y, p, seed=42, repeats=400):
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(repeats):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) == 2:
            values.append(average_precision_score(y[idx], p[idx]))
    return (
        {
            "lower": float(np.quantile(values, 0.025)),
            "upper": float(np.quantile(values, 0.975)),
            "method": "row bootstrap, 400 repeats; does not account for temporal/entity dependence",
        }
        if values
        else None
    )


def drift(reference, current):
    result = {}
    for col in ("amount", "time"):
        # Time drift is expected; reported separately from amount shift.
        base = reference[col].to_numpy()
        edges = np.unique(np.r_[-np.inf, np.quantile(base, np.arange(0.1, 1, 0.1)), np.inf])
        a = np.histogram(base, bins=edges)[0] / len(base)
        b = np.histogram(current[col], bins=edges)[0] / len(current)
        a, b = np.clip(a, 1e-6, 1), np.clip(b, 1e-6, 1)
        result[col] = {"psi": float(np.sum((b - a) * np.log(b / a)))}
    result["missingness_delta"] = (
        current[list(ENTITIES)].isna().mean() - reference[list(ENTITIES)].isna().mean()
    ).to_dict()
    return result
