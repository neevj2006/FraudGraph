import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_curve


def metrics(y, p, amount, k=100):
    y, p, amount = np.asarray(y), np.asarray(p), np.asarray(amount)
    if not len(y):
        return {"n": 0, "pr_auc": None}
    order = np.argsort(-p, kind="stable")[: min(k, len(y))]
    fpr, tpr, _ = (
        roc_curve(y, p) if len(np.unique(y)) == 2 else (np.array([0]), np.array([0]), None)
    )
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(
        np.mean(bins == b) * abs(float(y[bins == b].mean()) - float(p[bins == b].mean()))
        for b in range(10)
        if (bins == b).any()
    )
    return {
        "n": len(y),
        "positives": int(y.sum()),
        "pr_auc": float(average_precision_score(y, p)) if y.sum() else None,
        "precision_at_k": float(y[order].mean()),
        "k": len(order),
        "recall_at_k": float(y[order].sum() / max(1, y.sum())),
        "recall_at_1pct_fpr": float(tpr[fpr <= 0.01].max()),
        "fraud_value_captured": float((y[order] * amount[order]).sum()),
        "fraud_value_fraction": float(
            (y[order] * amount[order]).sum() / max(1, (y * amount).sum())
        ),
        "brier": float(brier_score_loss(y, p)),
        "ece": float(ece),
    }
