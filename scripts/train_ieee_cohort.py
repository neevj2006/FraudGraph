"""Predeclare a chronological public-data cohort, then train without opening test metrics."""

import json
from pathlib import Path

import pandas as pd

from ml.data.dataset import digest, validate
from ml.pipeline import train

root = Path("data/ieee")
output = Path("artifacts/ieee-cohort-10000")
if output.exists():
    raise RuntimeError("Use a new explicit experiment directory; do not overwrite results")
frame = validate(pd.read_csv(root / "canonical.csv"))
# Chosen for local memory capacity before model fitting, never by labels or scores.
cutoff = float(frame.iloc[9999].time)
cohort = frame.loc[frame.time <= cutoff].copy()
output.mkdir(parents=True)
protocol = {
    "dataset": "IEEE-CIS chronological first-10000 cohort including cutoff ties",
    "source_manifest": "data/ieee/source-manifest.json",
    "full_rows": len(frame),
    "cohort_rows": len(cohort),
    "cohort_sha256": digest(cohort),
    "cutoff_time_inclusive": cutoff,
    "selection_rule": "First 10000 chronological rows plus equal-time ties; selected for memory capacity, not labels or performance",
    "scope": "Public-data cohort benchmark, not full-dataset or production-scale validation",
    "seeds": [11, 29, 42],
    "epochs": 100,
    "split": "60/20/20 unique timestamps; earlier validation half selects, later half calibrates",
    "final_policy": "Open final test once after training freezes all models; no test-based tuning",
}
(output / "cohort-protocol.json").write_text(json.dumps(protocol, indent=2))
del frame
print(json.dumps(protocol, indent=2), flush=True)
train(cohort, output, protocol["dataset"], epochs=100)
