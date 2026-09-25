"""Measure feature-equivalent preprocessing on a fixed training-only prefix."""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.dataset import validate
from ml.features.history import build_features
from research.history import build_features_fast


def main():
    frame = validate(pd.read_csv("data/ieee/canonical.csv", nrows=10000))
    start = time.perf_counter()
    original = build_features(frame)
    reference_seconds = time.perf_counter() - start
    start = time.perf_counter()
    fast = build_features_fast(frame)
    fast_seconds = time.perf_counter() - start
    np.testing.assert_allclose(fast, original, atol=1e-6, rtol=1e-6)
    result = {
        "rows": len(frame),
        "reference_seconds": reference_seconds,
        "fast_seconds": fast_seconds,
        "speed_ratio": reference_seconds / fast_seconds,
        "maximum_absolute_difference": float(np.max(np.abs(fast - original))),
        "scope": "Same first 10000 chronological training rows, same process; one timing observation",
    }
    Path("docs/results/history-benchmark.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
