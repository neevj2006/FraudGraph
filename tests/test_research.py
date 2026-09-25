import numpy as np
import pytest

from ml.data.dataset import synthetic, validate
from ml.features.history import build_features
from research.history import build_features_fast
from research.protocol import qualifies, rolling_folds


def test_fast_history_matches_reference_and_preserves_cutoffs():
    frame = synthetic(150)
    frame["time"] = np.arange(len(frame)) // 3
    frame.loc[::4, "device"] = None
    frame = validate(frame)
    actual = build_features_fast(frame)
    np.testing.assert_allclose(actual, build_features(frame), atol=1e-6, rtol=1e-6)
    np.testing.assert_array_equal(actual[:90], build_features_fast(frame.iloc[:90]))
    frame["label"] = 1 - frame.label
    np.testing.assert_array_equal(actual, build_features_fast(frame))
    with pytest.raises(ValueError, match="chronological"):
        build_features_fast(frame.iloc[::-1])


def test_rolling_windows_are_strict_and_assessments_disjoint():
    times = np.repeat(np.arange(1000), 3)
    folds = rolling_folds(times)
    seen = set()
    for fold in folds:
        parts = list(fold.values())
        for left, right in zip(parts[:-1], parts[1:], strict=True):
            assert times[left].max() < times[right].min()
        assert not seen.intersection(fold["assessment"])
        seen.update(fold["assessment"])
    assert max(seen) == len(times) - 1


def test_promotion_rejects_budget_loss_and_catastrophic_fold():
    reference = [{"pr_auc": 0.2, "precision_at_k": 0.3}] * 3
    better = [{"pr_auc": 0.22, "precision_at_k": 0.31}] * 3
    assert qualifies(better, reference)
    assert not qualifies([{"pr_auc": 0.25, "precision_at_k": 0.29}] * 3, reference)
    assert not qualifies([*better[:2], {"pr_auc": 0.1, "precision_at_k": 0.4}], reference)
