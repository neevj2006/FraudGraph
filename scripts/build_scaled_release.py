"""Package the research-selected tree and frozen comparators for local staging."""

import hashlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.data.dataset import digest, validate
from ml.features.history import FEATURES
from research.run import source_hash, write
from scaling.experiment import file_hash
from services.inference.evidence import EvidenceIndex
from services.inference.scaled import score_scaled


def trusted_bundle(folder):
    freeze = json.loads((folder / "freeze.json").read_text())
    if file_hash(folder / "bundle.joblib") != freeze["bundle_sha256"]:
        raise ValueError("Source model integrity mismatch")
    return joblib.load(folder / "bundle.joblib")


def main():
    out = Path("artifacts/staging-model-v2")
    if out.exists():
        raise ValueError("Staging artifact already exists; do not overwrite")
    decision = json.loads(Path("artifacts/research-v2/decision.json").read_text())
    if decision["source_sha256"] != source_hash() or decision["selected"] != "tree_reference":
        raise ValueError("This packager requires the frozen reference-tree research choice")
    tab = trusted_bundle(Path("artifacts/ieee-full-tabular"))
    graph = trusted_bundle(Path("artifacts/scaling/full-gnn"))
    cache = Path("artifacts/scaling/cache-590540")
    manifest = json.loads((cache / "manifest.json").read_text())
    for name in [
        "events.csv",
        "splits.npz",
        "scaler.joblib",
        "x.npy",
        "neighbors.npy",
        "pooled_means.npy",
    ]:
        if file_hash(cache / name) != manifest["cache_sha256"][name]:
            raise ValueError("Source cache integrity mismatch")
    scaler = joblib.load(cache / "scaler.joblib")
    np.testing.assert_allclose(scaler.mean_, tab["scaler"].mean_, atol=1e-12)
    np.testing.assert_allclose(scaler.scale_, tab["scaler"].scale_, atol=1e-12)
    split = dict(np.load(cache / "splits.npz"))
    frame = validate(pd.read_csv(cache / "events.csv")).iloc[: split["validation"][-1] + 1].copy()
    out.mkdir(parents=True)
    (out / "cache").mkdir()
    for name in ["x.npy", "neighbors.npy", "pooled_means.npy"]:
        shutil.copyfile(cache / name, out / "cache" / name)
    frame.to_csv(out / "events.csv", index=False)
    provenance = {
        "schema_version": "1",
        "dataset": "IEEE-CIS full training/validation history; local staging benchmark",
        "dataset_sha256": digest(frame),
        "code_sha256": source_hash(),
        "features": FEATURES,
        "graph_schema": "temporal-entity-snapshots-v2",
        "split_version": "research-v2-rolling-development",
        "seeds": [11, 29, 42],
        "selected": "xgboost_graph",
        "serving_seed": 11,
        "policy": {"top_k": 100},
        "calibration": "Frozen full-data tabular Platt fit on later validation half",
        "label_policy": "offline targets only; no label histories",
        "format": "scaled-v2",
        "graph_comparator": "Frozen full-data GraphSAGE seed 11",
        "research_decision_sha256": file_hash(Path("artifacts/research-v2/decision.json")),
        "history_rows": len(frame),
        "history_cutoff": float(frame.time.max()),
        "use": "Local multi-organization staging; not independently validated production use",
    }
    provenance["version"] = hashlib.sha256(
        json.dumps(provenance, sort_keys=True).encode()
    ).hexdigest()[:16]
    bundle = {
        "format": "scaled-v2",
        "models": {
            **{k: tab["models"][k] for k in ["logistic", "xgboost_graph"]},
            "sage": graph["models"]["sage"],
        },
        "selected": "xgboost_graph",
        "scaler": tab["scaler"],
        "calibrator": tab["calibrator"],
        "manifest": provenance,
    }
    # Queue is a documented 200-row validation fixture, never final-test predictions.
    indices = split["validation"][:200]
    scores = score_scaled(bundle, out, frame, indices)
    index = EvidenceIndex(frame)
    graphs = {row["id"]: index.get(row["id"]) for row in scores}
    joblib.dump(bundle, out / "bundle.joblib")
    write(out / "manifest.json", provenance)
    write(out / "scores.json", scores)
    write(out / "graphs.json", graphs)
    write(
        out / "splits.json", {k: frame.id.iloc[split[k]].tolist() for k in ["train", "validation"]}
    )
    write(
        out / "freeze.json",
        {
            "bundle_sha256": file_hash(out / "bundle.joblib"),
            "dataset_sha256": provenance["dataset_sha256"],
            "assets": {
                p.relative_to(out).as_posix(): file_hash(p)
                for p in out.rglob("*")
                if p.is_file() and p.name != "bundle.joblib"
            },
        },
    )
    print(
        f"Packaged staging model {provenance['version']} with {len(frame)} history rows and {len(scores)} validation alerts"
    )


if __name__ == "__main__":
    main()
