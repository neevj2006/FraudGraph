"""Resumable, protocol-locked rolling validation without reopening the old test."""

import argparse
import copy
import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from ml.data.dataset import digest, validate
from ml.data.splits import chronological
from ml.evaluation.metrics import metrics
from ml.models.gnn import GraphClassifier
from research.history import build_features_fast
from research.protocol import CANDIDATES, FOLD_FRACTIONS, SEEDS, qualifies, rolling_folds
from scaling.batched import forward_batch, predict_batched
from scaling.cache import GraphCache, build_aggregates, build_neighbors
from scaling.experiment import file_hash, logit
from scaling.monitor import MemoryMonitor


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def source_hash():
    h = hashlib.sha256()
    for path in sorted(
        [*Path("ml").rglob("*.py"), *Path("scaling").rglob("*.py"), *Path("research").glob("*.py")]
    ):
        h.update(path.as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def prepare(out, frame):
    start = time.perf_counter()
    raw = build_features_fast(frame)
    np.save(out / "raw.npy", raw)
    neighbors = build_neighbors(frame, out / "neighbors.npy")
    records = []
    for number, split in enumerate(rolling_folds(frame.time.to_numpy()), 1):
        folder = out / f"fold-{number}"
        folder.mkdir(exist_ok=True)
        end = split["assessment"][-1] + 1
        scaler = StandardScaler().fit(raw[split["train"]])
        x = scaler.transform(raw[:end]).astype(np.float32)
        np.save(folder / "x.npy", x)
        np.save(folder / "neighbors.npy", neighbors[:end])
        np.savez(folder / "splits.npz", **split)
        joblib.dump(scaler, folder / "scaler.joblib")
        build_aggregates(x, neighbors[:end], folder)
        records.append(
            {
                "fold": number,
                "rows": {k: len(v) for k, v in split.items()},
                "time_bounds": {
                    k: [float(frame.time.iloc[v[0]]), float(frame.time.iloc[v[-1]])]
                    for k, v in split.items()
                },
                "checksums": {
                    p.name: file_hash(p)
                    for p in [
                        *folder.glob("*.npy"),
                        folder / "splits.npz",
                        folder / "scaler.joblib",
                    ]
                },
            }
        )
    write(out / "cache.json", {"folds": records, "prepare_seconds": time.perf_counter() - start})


def fit_graph(name, seed, cache, y, split):
    torch.manual_seed(seed)
    model = GraphClassifier(cache.x.shape[1], "sage")
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    train, selection = split["train"], split["selection"]
    weight = (len(train) - y[train].sum()) / y[train].sum() if name == "sage_reference" else 1.0
    best, stale, state, best_epoch = -1.0, 0, None, 0
    for epoch in range(40):
        model.train()
        optimizer.zero_grad()
        for start in range(0, len(train), 1024):
            ids = train[start : start + 1024]
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                forward_batch(model, cache, ids),
                torch.tensor(y[ids], dtype=torch.float32),
                pos_weight=torch.tensor(float(weight)),
                reduction="sum",
            ) / len(train)
            loss.backward()
        optimizer.step()
        score = average_precision_score(y[selection], predict_batched(model, cache, selection))
        if score > best + 1e-5:
            best, stale, state, best_epoch = score, 0, copy.deepcopy(model.state_dict()), epoch + 1
        else:
            stale += 1
        if epoch % 10 == 9 or stale >= 10:
            print(f"{name} seed={seed} epoch={epoch + 1} checkpoint AP={score:.4f}", flush=True)
        if stale >= 10:
            break
    model.load_state_dict(state)
    return model, {"best_epoch": best_epoch, "epochs_completed": epoch + 1}


def fit_run(out, number, name, seed, frame):
    folder = out / f"fold-{number}"
    run_dir = folder / f"{name}-{seed}"
    result_path = run_dir / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text())
        if file_hash(run_dir / "bundle.joblib") != result["bundle_sha256"]:
            raise ValueError("Saved run bundle changed")
        return result
    run_dir.mkdir(exist_ok=True)
    split = dict(np.load(folder / "splits.npz"))
    cache = GraphCache(folder)
    y = frame.label.to_numpy()
    amount = frame.amount.to_numpy()
    start = time.perf_counter()
    if name.startswith("tree"):
        config = {"n_estimators": 100, "max_depth": 3, "learning_rate": 0.06}
        if name == "tree_regularized":
            config.update(
                n_estimators=250,
                max_depth=4,
                learning_rate=0.04,
                min_child_weight=20,
                reg_lambda=5,
                subsample=0.8,
                colsample_bytree=0.8,
            )
        model = XGBClassifier(**config, n_jobs=2, random_state=seed, eval_metric="logloss")
        model.fit(cache.x[split["train"]], y[split["train"]])
        training = {"trees": config["n_estimators"]}

        def predict(ids):
            return model.predict_proba(cache.x[ids])[:, 1]
    else:
        model, training = fit_graph(name, seed, cache, y, split)

        def predict(ids):
            return predict_batched(model, cache, ids)

    fit_seconds = time.perf_counter() - start
    cal, assessment = split["calibration"], split["assessment"]
    calibrator = LogisticRegression(C=1.0).fit(logit(predict(cal)), y[cal])
    start = time.perf_counter()
    raw = predict(assessment)
    p = calibrator.predict_proba(logit(raw))[:, 1]
    prediction_seconds = time.perf_counter() - start
    joblib.dump({"model": model, "calibrator": calibrator}, run_dir / "bundle.joblib")
    np.savez(run_dir / "predictions.npz", rows=assessment, raw=raw, calibrated=p)
    result = {
        "fold": number,
        "candidate": name,
        "seed": seed,
        "training": training,
        "fit_seconds": fit_seconds,
        "prediction_seconds": prediction_seconds,
        "raw_metrics": metrics(y[assessment], raw, amount[assessment]),
        "metrics": metrics(y[assessment], p, amount[assessment]),
        "bundle_sha256": file_hash(run_dir / "bundle.joblib"),
    }
    write(result_path, result)
    print(
        f"fold={number} {name} seed={seed}: assessment AP={result['metrics']['pr_auc']:.4f}, "
        f"P@100={result['metrics']['precision_at_k']:.2f}",
        flush=True,
    )
    return result


def aggregate(runs, name):
    return [
        {
            metric: float(
                np.mean(
                    [
                        r["metrics"][metric]
                        for r in runs
                        if r["candidate"] == name and r["fold"] == fold
                    ]
                )
            )
            for metric in ["pr_auc", "precision_at_k", "brier", "ece"]
        }
        for fold in [1, 2, 3]
    ]


def run(out, resume):
    frame = validate(pd.read_csv("data/ieee/canonical.csv"))
    # Only the original training prefix enters research; later labels are never scored.
    frame = frame.iloc[chronological(frame)["train"]].copy()
    if out.exists() and not resume:
        raise ValueError("Research directory exists; use --resume for the same frozen protocol")
    protocol = {
        "source_sha256": source_hash(),
        "research_dataset_sha256": digest(frame),
        "rows": len(frame),
        "scope": "Retrospective rolling development validation within original training only",
        "candidates": CANDIDATES,
        "seeds": SEEDS,
        "fold_fractions": FOLD_FRACTIONS,
        "graph_screen_epochs": 40,
        "graph_patience": 10,
        "graph_confirmation": "Only screen qualifiers receive seeds 29 and 42",
        "promotion": "Mean AP +0.005, nondecreasing mean P@100, AP wins >=2 folds, no AP loss >10%",
        "independent_test": "Unavailable; original final window not rescored",
    }
    if out.exists():
        if json.loads((out / "protocol.json").read_text()) != protocol:
            raise ValueError("Research code, data or protocol changed; refusing resume")
        if (out / "decision.json").exists():
            raise ValueError("Research already completed; no repeat selection")
    else:
        out.mkdir(parents=True)
        write(out / "protocol.json", protocol)
    if not (out / "cache.json").exists():
        prepare(out, frame)
    for fold in json.loads((out / "cache.json").read_text())["folds"]:
        for name, expected in fold["checksums"].items():
            if file_hash(out / f"fold-{fold['fold']}" / name) != expected:
                raise ValueError("Research cache changed")
    runs = []
    for number in [1, 2, 3]:
        for name in CANDIDATES:
            for seed in SEEDS if name.startswith("tree") else [11]:
                runs.append(fit_run(out, number, name, seed, frame))
                write(out / "progress.json", runs)
    reference = aggregate(runs, "tree_reference")
    tree = (
        "tree_regularized"
        if qualifies(aggregate(runs, "tree_regularized"), reference)
        else "tree_reference"
    )
    tree_metrics = aggregate(runs, tree)
    eligible = [tree]
    confirmation = []
    for name in ["sage_reference", "sage_unweighted"]:
        if qualifies(aggregate(runs, name), tree_metrics):
            confirmation.append(name)
            for number in [1, 2, 3]:
                for seed in [29, 42]:
                    runs.append(fit_run(out, number, name, seed, frame))
                    write(out / "progress.json", runs)
            if qualifies(aggregate(runs, name), tree_metrics):
                eligible.append(name)
    means = {
        name: float(np.mean([m["pr_auc"] for m in aggregate(runs, name)])) for name in eligible
    }
    selected = next(name for name in eligible if means[name] >= max(means.values()) - 0.005)
    write(
        out / "decision.json",
        {
            "selected": selected,
            "tree_choice": tree,
            "confirmed_graph_candidates": confirmation,
            "eligible": eligible,
            "fold_metrics": {name: aggregate(runs, name) for name in CANDIDATES},
            "run_count": len(runs),
            "source_sha256": source_hash(),
            "scope": "Development choice for staging; not independent production acceptance",
        },
    )
    print(f"Research complete: staging candidate {selected}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("artifacts/research-v2"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    torch.set_num_threads(2)
    with MemoryMonitor() as monitor:
        run(args.out, args.resume)
    write(args.out / "resources.json", monitor.result)


if __name__ == "__main__":
    main()
