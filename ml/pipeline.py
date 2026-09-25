"""Reproducible offline experiments. Only final-evaluate opens test metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from ml.data.dataset import audit, digest, ieee, synthetic, validate
from ml.data.splits import chronological, unseen
from ml.evaluation.metrics import metrics
from ml.evaluation.reporting import bootstrap_ap, drift, graph_quality, validation_diagnostics
from ml.features.history import FEATURES, build_features
from ml.graph.build import causal_edges
from ml.models.gnn import predict, train_gnn


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def code_digest():
    h = hashlib.sha256()
    for path in sorted(Path("ml").rglob("*.py")):
        h.update(path.as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def probabilities(bundle, df, omit=None):
    x = bundle["scaler"].transform(build_features(df)).astype(np.float32)
    edges, rel = causal_edges(df, omit=omit)
    p = {}
    for name, model in bundle["models"].items():
        if name in ("sage", "rgcn"):
            p[name] = predict(model, x, edges, rel)
        else:
            p[name] = model.predict_proba(x[:, :4] if name in ("logistic", "xgboost") else x)[:, 1]
    selected = p[bundle["selected"]]
    p["calibrated"] = bundle["calibrator"].predict_proba(logit(selected).reshape(-1, 1))[:, 1]
    return p


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def train(df, out: Path, source="synthetic", epochs=100, seeds=(11, 29, 42)):
    out.mkdir(parents=True, exist_ok=True)
    if (out / "freeze.json").exists():
        raise ValueError("Experiment is frozen. Use a new output directory for a new experiment.")
    split = chronological(df)
    tr, va = split["train"], split["validation"]
    # Validation's earlier half chooses models; later half fits calibration.
    vt = np.sort(df.iloc[va].time.unique())
    middle = vt[len(vt) // 2]
    select = va[df.iloc[va].time.to_numpy() < middle]
    cal = va[df.iloc[va].time.to_numpy() >= middle]
    for name, idx in (("training", tr), ("selection", select), ("calibration", cal)):
        if len(np.unique(df.iloc[idx].label)) != 2:
            raise ValueError(f"{name} window needs both classes; use more data")
    # No test rows, labels, or edges are loaded into the training tensors.
    working = df.iloc[: va[-1] + 1].copy()
    raw_x = build_features(working)
    scaler = StandardScaler().fit(raw_x[tr])
    x = scaler.transform(raw_x).astype(np.float32)
    y = working.label.to_numpy()
    edges, rel = causal_edges(working)
    runs, model_candidates = [], {}
    for seed in seeds:
        models = {
            "logistic": LogisticRegression(
                class_weight="balanced", max_iter=500, random_state=seed
            ),
            "xgboost": XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.06,
                n_jobs=2,
                random_state=seed,
                eval_metric="logloss",
            ),
            "xgboost_graph": XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.06,
                n_jobs=2,
                random_state=seed,
                eval_metric="logloss",
            ),
        }
        for kind in ("logistic", "xgboost", "xgboost_graph", "sage", "rgcn"):
            start = time.perf_counter()
            if kind in ("sage", "rgcn"):
                model, details = train_gnn(x, y, edges, rel, tr, select, kind, seed, epochs)
                p = predict(model, x, edges, rel)
            else:
                model, details = models[kind], {}
                xx = x[:, :4] if kind != "xgboost_graph" else x
                model.fit(xx[tr], y[tr])
                p = model.predict_proba(xx)[:, 1]
            result = {
                "model": kind,
                "seed": seed,
                "runtime_seconds": time.perf_counter() - start,
                **details,
                **metrics(y[select], p[select], working.amount.to_numpy()[select]),
            }
            runs.append(result)
            print(f"{kind} seed={seed}: validation AP={result['pr_auc']:.4f}", flush=True)
            if seed == seeds[0]:
                model_candidates[kind] = model
    aggregate = {
        kind: {
            "mean_ap": float(np.mean([r["pr_auc"] for r in runs if r["model"] == kind])),
            "std_ap": float(np.std([r["pr_auc"] for r in runs if r["model"] == kind])),
        }
        for kind in model_candidates
    }
    # Simplicity tie-break: within .005 AP of the best mean, prefer lower-complexity model.
    best = max(v["mean_ap"] for v in aggregate.values())
    selected = next(k for k in model_candidates if aggregate[k]["mean_ap"] >= best - 0.005)
    bundle = {"models": model_candidates, "scaler": scaler, "selected": selected}
    xx = x[:, :4] if selected in ("logistic", "xgboost") else x
    p = (
        predict(model_candidates[selected], x, edges, rel)
        if selected in ("sage", "rgcn")
        else model_candidates[selected].predict_proba(xx)[:, 1]
    )
    calibrator = LogisticRegression(C=1.0).fit(logit(p[cal]).reshape(-1, 1), y[cal])
    bundle["calibrator"] = calibrator
    manifest = {
        "schema_version": "1",
        "dataset": source,
        "dataset_sha256": digest(df),
        "code_sha256": code_digest(),
        "features": FEATURES,
        "graph_schema": "temporal-entity-snapshots-v2",
        "split_version": "chronological-60-20-20-v1",
        "seeds": list(seeds),
        "epochs": epochs,
        "neighbors_per_relation": 8,
        "selected": selected,
        "serving_seed": seeds[0],
        "policy": {"top_k": 100},
        "python": platform.python_version(),
        "label_policy": "offline targets only; no label histories",
        "calibration": "Platt on later validation half; diagnostic fit metrics only",
    }
    version = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    manifest["version"] = version
    bundle["manifest"] = manifest
    df.to_csv(out / "events.csv", index=False)
    joblib.dump(bundle, out / "bundle.joblib")
    write_json(out / "manifest.json", manifest)
    write_json(out / "audit.json", audit(df))
    write_json(out / "splits.json", {k: df.iloc[v].id.tolist() for k, v in split.items()})
    write_json(
        out / "experiments.json",
        {
            "runs": runs,
            "aggregate": aggregate,
            "selected": selected,
            "rule_amount": metrics(
                y[select],
                np.clip(working.amount.to_numpy()[select] / working.amount.iloc[tr].max(), 0, 1),
                working.amount.to_numpy()[select],
            ),
        },
    )
    preds = probabilities(bundle, working)
    score_rows(bundle, working, preds, va).to_json(out / "scores.json", orient="records", indent=2)
    write_json(
        out / "calibration.json",
        {
            "raw": metrics(y[cal], p[cal], working.amount.to_numpy()[cal]),
            "calibrated_fit_diagnostic": metrics(
                y[cal], preds["calibrated"][cal], working.amount.to_numpy()[cal]
            ),
        },
    )
    plots(out, working, preds, cal)
    write_json(out / "graph-quality.json", graph_quality(working))
    write_json(
        out / "validation-diagnostics.json",
        validation_diagnostics(working, {"train": tr, "validation": va}, preds["calibrated"]),
    )
    write_json(out / "drift.json", drift(working.iloc[tr], working.iloc[va]))
    # Edge ablations are evaluation-time perturbations, explicitly not retrained ablations.
    from ml.data.dataset import ENTITIES

    ablations = {}
    for kind in ENTITIES:
        ep, er = causal_edges(working, omit=kind)
        ablations[kind] = {
            model: metrics(
                y[select],
                predict(model_candidates[model], x, ep, er)[select],
                working.amount.to_numpy()[select],
            )
            for model in ("sage", "rgcn")
        }
    write_json(out / "edge-sensitivity.json", ablations)
    write_json(
        out / "freeze.json",
        {
            "version": version,
            "code_sha256": code_digest(),
            "bundle_sha256": hashlib.sha256((out / "bundle.joblib").read_bytes()).hexdigest(),
            "dataset_sha256": digest(df),
        },
    )
    return manifest


def score_rows(bundle, df, preds, indices, latency_ms=0):
    rows = []
    for i in indices:
        tx = df.iloc[i]
        rows.append(
            {
                "id": tx.id,
                "time": float(tx.time),
                "amount": float(tx.amount),
                "score": float(preds["calibrated"][i]),
                "baseline_score": float(preds["logistic"][i]),
                "graph_score": float(preds["rgcn"][i]),
                "model_version": bundle["manifest"]["version"],
                "model": bundle["selected"],
                "dataset": bundle["manifest"]["dataset"],
                "cutoff": float(tx.time),
                "latency_ms": latency_ms,
                "input_statistics": {"missing_identifiers": int(tx.isna().sum())},
                "confidence": "Validation-calibrated estimate; no individual confidence interval",
                "entity_types": [
                    c
                    for c in ("account", "card", "device", "address", "merchant")
                    if tx[c] is not None
                ],
                "status": "open",
            }
        )
    return pd.DataFrame(rows)


def plots(out, df, preds, cal):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    bins = pd.cut(df.time, 12)
    df.groupby(bins, observed=True).label.mean().plot.bar(ax=axes[0], color="#4d8579")
    axes[0].set(
        title="Observed prevalence by time bin", xlabel="Chronological bin", ylabel="Fraud fraction"
    )
    axes[0].set_xticklabels(range(12), rotation=0)
    for name in (bundle_name := "calibrated", "logistic"):
        yy, pp = calibration_curve(df.label.to_numpy()[cal], preds[name][cal], n_bins=8)
        axes[1].plot(pp, yy, "o-", label=name)
    axes[1].plot([0, 1], [0, 1], "--", color="gray")
    axes[1].set(
        title=f"{bundle_name.title()} fit diagnostic (validation)",
        xlabel="Predicted",
        ylabel="Observed",
    )
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(out / "diagnostics.png", dpi=150)
    plt.close(fig)


def final_evaluate(out):
    target = out / "final-evaluation.json"
    if target.exists():
        raise ValueError("Final evaluation already exists; refusing to reopen the holdout")
    freeze = json.loads((out / "freeze.json").read_text())
    if freeze["code_sha256"] != code_digest():
        raise ValueError("ML code changed since freeze; create a new experiment")
    if freeze["bundle_sha256"] != hashlib.sha256((out / "bundle.joblib").read_bytes()).hexdigest():
        raise ValueError("Frozen model checksum mismatch")
    df = validate(pd.read_csv(out / "events.csv"))
    if freeze["dataset_sha256"] != digest(df):
        raise ValueError("Frozen dataset checksum mismatch")
    bundle = joblib.load(out / "bundle.joblib")
    splits = chronological(df)
    idx = splits["test"]
    start = time.perf_counter()
    preds = probabilities(bundle, df)
    latency = (time.perf_counter() - start) * 1000
    result = {
        "version": freeze["version"],
        "dataset": bundle["manifest"]["dataset"],
        "all_model_batch_latency_ms": latency,
        "rows_in_graph": len(df),
        "calibrated_ap_interval": bootstrap_ap(df.label.to_numpy()[idx], preds["calibrated"][idx]),
        "metrics": {
            name: metrics(df.label.to_numpy()[idx], p[idx], df.amount.to_numpy()[idx])
            for name, p in preds.items()
        },
        "unseen": {
            kind: metrics(
                df.label.to_numpy()[idx][mask],
                preds["calibrated"][idx][mask],
                df.amount.to_numpy()[idx][mask],
            )
            for kind, mask in unseen(df, splits["train"], idx).items()
        },
    }
    write_json(target, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["demo", "train", "import-ieee", "final-evaluate", "audit"]
    )
    parser.add_argument("--out", type=Path, default=Path("artifacts/demo"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--rows", type=int, default=1800)
    parser.add_argument("--epochs", type=int, default=100)
    args = parser.parse_args()
    if args.command == "final-evaluate":
        print(json.dumps(final_evaluate(args.out), indent=2))
    elif args.command == "import-ieee":
        frame = ieee(args.input, args.identity)
        args.out.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.out / "canonical.csv", index=False)
        write_json(
            args.out / "source-manifest.json",
            {
                "source": "https://www.kaggle.com/c/ieee-fraud-detection/data",
                "license": "Subject to accepted Kaggle competition rules; no redistribution",
                "files": [
                    {
                        "name": p.name,
                        "size": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    }
                    for p in (args.input, args.identity)
                    if p
                ],
                "audit": audit(frame),
            },
        )
    elif args.command == "audit":
        print(json.dumps(audit(validate(pd.read_csv(args.input))), indent=2))
    else:
        frame = (
            synthetic(args.rows) if args.command == "demo" else validate(pd.read_csv(args.input))
        )
        print(
            json.dumps(
                train(
                    frame,
                    args.out,
                    "synthetic-demo" if args.command == "demo" else "user-supplied-canonical",
                    args.epochs,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
