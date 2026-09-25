"""Separate full-IEEE tabular baseline; never modifies the frozen cohort models."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from ml.data.dataset import digest, validate
from ml.data.splits import chronological, unseen
from ml.evaluation.metrics import metrics
from ml.evaluation.reporting import bootstrap_ap
from ml.features.history import build_features

OUT = Path("artifacts/ieee-full-tabular")


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def code_hash():
    h = hashlib.sha256()
    for p in [*sorted(Path("ml").rglob("*.py")), Path(__file__)]:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["train", "final"])
    args = parser.parse_args()
    if args.command == "train" and OUT.exists():
        raise ValueError("Experiment already exists; do not overwrite")
    if args.command == "final" and (OUT / "final.json").exists():
        raise ValueError("Final already opened; refusing repeat")
    frame = validate(pd.read_csv("data/ieee/canonical.csv"))
    split = chronological(frame)
    tr, va, te = (split[k] for k in ["train", "validation", "test"])
    if args.command == "train":
        OUT.mkdir(parents=True)
        write(
            "protocol.json",
            {
                "scope": "Full IEEE-CIS tabular baseline only; not GNN validation",
                "rows": len(frame),
                "dataset_sha256": digest(frame),
                "split_rows": {k: len(v) for k, v in split.items()},
                "epochs_or_trees": 100,
                "seeds": [11, 29, 42],
                "selection": "Earlier validation mean AP, .005 simplicity margin; serve seed 11",
                "calibration": "Later validation Platt fit",
                "final": "Once-only final after freeze; no tuning from test",
                "note": "The previous early cohort lies within this experiment training window; its evaluation is not reused as this holdout",
            },
        )
        working = frame.iloc[: va[-1] + 1].copy()
        del frame
        start = time.perf_counter()
        raw = build_features(working)
        scaler = StandardScaler().fit(raw[tr])
        x = scaler.transform(raw).astype(np.float32)
        del raw
        times = np.sort(working.iloc[va].time.unique())
        middle = times[len(times) // 2]
        selection = va[working.iloc[va].time.to_numpy() < middle]
        cal = va[working.iloc[va].time.to_numpy() >= middle]
        y = working.label.to_numpy()
        runs, models = [], {}
        for seed in [11, 29, 42]:
            for name in ["logistic", "xgboost", "xgboost_graph"]:
                model = (
                    LogisticRegression(class_weight="balanced", max_iter=500, random_state=seed)
                    if name == "logistic"
                    else XGBClassifier(
                        n_estimators=100,
                        max_depth=3,
                        learning_rate=0.06,
                        n_jobs=2,
                        random_state=seed,
                        eval_metric="logloss",
                    )
                )
                xx = x if name == "xgboost_graph" else x[:, :4]
                model.fit(xx[tr], y[tr])
                p = model.predict_proba(xx[selection])[:, 1]
                result = {
                    "model": name,
                    "seed": seed,
                    **metrics(y[selection], p, working.amount.to_numpy()[selection]),
                }
                runs.append(result)
                if seed == 11:
                    models[name] = model
                print(f"{name} seed {seed}: validation AP={result['pr_auc']:.4f}", flush=True)
        means = {
            name: float(np.mean([r["pr_auc"] for r in runs if r["model"] == name]))
            for name in models
        }
        selected = next(name for name in models if means[name] >= max(means.values()) - 0.005)
        p = models[selected].predict_proba(x[cal] if selected == "xgboost_graph" else x[cal, :4])[
            :, 1
        ]
        calibrator = LogisticRegression(C=1.0).fit(logit(p), y[cal])
        joblib.dump(
            {"models": models, "scaler": scaler, "selected": selected, "calibrator": calibrator},
            OUT / "bundle.joblib",
        )
        write(
            "validation.json",
            {
                "runs": runs,
                "mean_ap": means,
                "selected": selected,
                "elapsed_seconds": time.perf_counter() - start,
                "calibration_rows": len(cal),
                "calibration_positives": int(y[cal].sum()),
            },
        )
        write(
            "freeze.json",
            {
                "code_sha256": code_hash(),
                "bundle_sha256": hashlib.sha256((OUT / "bundle.joblib").read_bytes()).hexdigest(),
                "dataset_sha256": json.loads((OUT / "protocol.json").read_text())["dataset_sha256"],
            },
        )
        print("Full tabular experiment frozen; test remains closed", flush=True)
    else:
        freeze = json.loads((OUT / "freeze.json").read_text())
        if (
            freeze["code_sha256"] != code_hash()
            or freeze["dataset_sha256"] != digest(frame)
            or freeze["bundle_sha256"]
            != hashlib.sha256((OUT / "bundle.joblib").read_bytes()).hexdigest()
        ):
            raise ValueError("Frozen artifact integrity mismatch")
        bundle = joblib.load(OUT / "bundle.joblib")
        start = time.perf_counter()
        x = bundle["scaler"].transform(build_features(frame)).astype(np.float32)
        predictions = {
            name: model.predict_proba(x[te] if name == "xgboost_graph" else x[te, :4])[:, 1]
            for name, model in bundle["models"].items()
        }
        predictions["calibrated"] = bundle["calibrator"].predict_proba(
            logit(predictions[bundle["selected"]])
        )[:, 1]
        y, amount = frame.label.to_numpy()[te], frame.amount.to_numpy()[te]
        result = {
            "selected": bundle["selected"],
            "metrics": {name: metrics(y, p, amount) for name, p in predictions.items()},
            "unseen": {
                kind: metrics(y[mask], predictions["calibrated"][mask], amount[mask])
                for kind, mask in unseen(frame, tr, te).items()
            },
            "bootstrap": bootstrap_ap(y, predictions["calibrated"]),
            "elapsed_seconds": time.perf_counter() - start,
            "scope": "Full dataset tabular only; historical feature construction included in elapsed time",
        }
        write("final.json", result)
        print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
