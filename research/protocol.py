"""Predeclared retrospective folds and deployment-candidate selection gates."""

import numpy as np

SEEDS = [11, 29, 42]
CANDIDATES = ["tree_reference", "tree_regularized", "sage_reference", "sage_unweighted"]
FOLD_FRACTIONS = [(0.4, 0.45, 0.5, 0.6), (0.6, 0.65, 0.7, 0.8), (0.8, 0.85, 0.9, 1.0)]


def rolling_folds(times):
    times = np.asarray(times)
    unique = np.unique(times)
    if len(unique) < 100 or np.any(times[1:] < times[:-1]):
        raise ValueError("At least 100 ordered distinct times required")
    result = []
    for fractions in FOLD_FRACTIONS:
        bounds = [unique[min(int(len(unique) * f), len(unique) - 1)] for f in fractions]
        end = times <= bounds[3] if fractions[3] == 1 else times < bounds[3]
        result.append(
            {
                "train": np.flatnonzero(times < bounds[0]),
                "selection": np.flatnonzero((times >= bounds[0]) & (times < bounds[1])),
                "calibration": np.flatnonzero((times >= bounds[1]) & (times < bounds[2])),
                "assessment": np.flatnonzero((times >= bounds[2]) & end),
            }
        )
    return result


def qualifies(candidate, reference):
    """Rows are three fold aggregates, never final-holdout outcomes."""
    aps = np.array([r["pr_auc"] for r in candidate])
    base = np.array([r["pr_auc"] for r in reference])
    precision = np.array([r["precision_at_k"] for r in candidate])
    bp = np.array([r["precision_at_k"] for r in reference])
    return bool(
        np.mean(aps) >= np.mean(base) + 0.005
        and np.mean(precision) >= np.mean(bp)
        and np.sum(aps > base) >= 2
        and np.all(aps >= 0.9 * base)
    )
