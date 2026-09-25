"""Post-freeze diagnostics on validation only; never retunes or opens test labels."""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil

from ml.data.dataset import ENTITIES, validate
from ml.data.splits import chronological
from ml.evaluation.metrics import metrics
from ml.pipeline import probabilities


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("artifacts/release"))
    path = parser.parse_args().out
    frame = validate(pd.read_csv(path / "events.csv"))
    split = chronological(frame)
    idx = split["validation"]
    frame = frame.iloc[: idx[-1] + 1].copy()
    bundle = joblib.load(path / "bundle.joblib")
    rng = np.random.default_rng(42)
    variants = {"unchanged": frame.copy()}
    missing = frame.copy()
    for col in ENTITIES:
        missing.loc[rng.random(len(frame)) < 0.2, col] = None
    variants["20pct_missing_signatures"] = missing
    hubs = frame.copy()
    hubs.loc[rng.random(len(frame)) < 0.1, "device"] = "perturbed-legitimate-hub"
    variants["10pct_shared_device_hub"] = hubs
    shifted = frame.copy()
    shifted["amount"] *= 1.5
    variants["50pct_amount_shift"] = shifted
    timing = frame.copy()
    timing["time"] += 3600
    variants["one_hour_time_shift"] = timing
    results = {}
    for name, data in variants.items():
        start = time.perf_counter()
        p = probabilities(bundle, data)["calibrated"]
        results[name] = {
            **metrics(data.label.to_numpy()[idx], p[idx], data.amount.to_numpy()[idx]),
            "all_model_batch_ms": (time.perf_counter() - start) * 1000,
            "process_rss_bytes_after_call": psutil.Process().memory_info().rss,
        }
    result = {
        "version": bundle["manifest"]["version"],
        "window": "validation (descriptive, includes calibration fit)",
        "note": "RSS includes Python, imported libraries and all loaded models; not incremental model memory or a peak measurement.",
        "perturbations": results,
    }
    (path / "robustness.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
