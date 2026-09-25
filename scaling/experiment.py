"""Disk-cached, bounded-memory graph experiments. Existing releases stay immutable."""

import argparse
import copy
import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

from ml.data.dataset import digest, validate
from ml.data.splits import chronological, unseen
from ml.evaluation.metrics import metrics
from ml.evaluation.reporting import bootstrap_ap
from ml.features.history import build_features
from ml.models.gnn import GraphClassifier
from scaling.batched import forward_batch, predict_batched
from scaling.cache import GraphCache, build_aggregates, build_neighbors
from scaling.monitor import MemoryMonitor


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def code_hash():
    h = hashlib.sha256()
    for path in sorted([*Path("ml").rglob("*.py"), *Path("scaling").rglob("*.py")]):
        h.update(path.as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def cache_code_hash():
    h = hashlib.sha256()
    for path in sorted(
        [*Path("ml/data").glob("*.py"), *Path("ml/features").glob("*.py"), Path("scaling/cache.py")]
    ):
        h.update(path.as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def prepare(folder, rows):
    if folder.exists():
        raise ValueError("Cache exists; choose a new path to avoid overwriting")
    frame = validate(pd.read_csv("data/ieee/canonical.csv"))
    if rows < len(frame):
        frame = frame[frame.time <= frame.iloc[rows - 1].time].copy()
    split = chronological(frame)
    va = split["validation"]
    times = np.sort(frame.iloc[va].time.unique())
    middle = times[len(times) // 2]
    split["selection"] = va[frame.iloc[va].time.to_numpy() < middle]
    split["calibration"] = va[frame.iloc[va].time.to_numpy() >= middle]
    working = frame.iloc[: va[-1] + 1].copy()
    folder.mkdir(parents=True)
    frame.to_csv(folder / "events.csv", index=False)
    np.savez(folder / "splits.npz", **split)
    start = time.perf_counter()
    raw = build_features(working)
    scaler = StandardScaler().fit(raw[split["train"]])
    x = scaler.transform(raw).astype(np.float32)
    del raw
    np.save(folder / "x.npy", x)
    np.save(folder / "labels.npy", working.label.to_numpy())
    joblib.dump(scaler, folder / "scaler.joblib")
    neighbors = build_neighbors(working, folder / "neighbors.npy")
    build_aggregates(x, neighbors, folder)
    write(
        folder / "manifest.json",
        {
            "rows": len(frame),
            "working_rows": len(working),
            "dataset_sha256": digest(frame),
            "code_sha256": cache_code_hash(),
            "prepare_seconds": time.perf_counter() - start,
            "scope": "Cache contains training/validation features and neighbors only; no test tensors",
            "cache_sha256": {
                p.name: file_hash(p)
                for p in [
                    *folder.glob("*.npy"),
                    folder / "scaler.joblib",
                    folder / "splits.npz",
                    folder / "events.csv",
                ]
            },
        },
    )
    print(f"Prepared {len(frame)} rows; training/validation cache {len(working)}", flush=True)


def fit(kind, seed, cache, labels, split, epochs, batch_size):
    torch.manual_seed(seed)
    model = GraphClassifier(cache.x.shape[1], kind)
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    tr, selection = split["train"], split["selection"]
    positives = float(labels[tr].sum())
    if positives == 0 or positives == len(tr):
        raise ValueError("Training requires both classes")
    weight = torch.tensor((len(tr) - positives) / positives)
    best, stale, state, best_epoch = -1.0, 0, None, 0
    start = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        opt.zero_grad()
        # Sum gradients over every target; one optimizer step matches full-batch training.
        for offset in range(0, len(tr), batch_size):
            ids = tr[offset : offset + batch_size]
            logits = forward_batch(model, cache, ids)
            target = torch.tensor(labels[ids], dtype=torch.float32)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                logits, target, pos_weight=weight, reduction="sum"
            ) / len(tr)
            loss.backward()
        opt.step()
        p = predict_batched(model, cache, selection, batch_size)
        ap = float(average_precision_score(labels[selection], p))
        if ap > best + 1e-5:
            best, stale, state, best_epoch = ap, 0, copy.deepcopy(model.state_dict()), epoch + 1
        else:
            stale += 1
        print(f"{kind} seed={seed} epoch={epoch + 1} selection AP={ap:.5f}", flush=True)
        if stale >= 15:
            break
    model.load_state_dict(state)
    return model, {
        "model": kind,
        "seed": seed,
        "best_epoch": best_epoch,
        "epochs_completed": epoch + 1,
        "validation_ap": best,
        "seconds": time.perf_counter() - start,
        "rss_after_bytes": psutil.Process().memory_info().rss,
    }


def train(folder, out, epochs, batch_size, benchmark):
    if out.exists():
        raise ValueError("Output already exists; do not overwrite experiments")
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest["code_sha256"] != cache_code_hash():
        raise ValueError("Cache code version mismatch")
    for name, expected in manifest["cache_sha256"].items():
        if file_hash(folder / name) != expected:
            raise ValueError(f"Cache integrity failure: {name}")
    cache = GraphCache(folder)
    labels = np.load(folder / "labels.npy", mmap_mode="r")
    split = dict(np.load(folder / "splits.npz"))
    out.mkdir(parents=True)
    protocol = {
        "cache": str(folder),
        "dataset_sha256": manifest["dataset_sha256"],
        "rows": manifest["rows"],
        "epochs": epochs,
        "batch_size": batch_size,
        "seeds": [11] if benchmark else [11, 29, 42],
        "optimizer": "Full-training-target gradient accumulation; one Adam step per epoch",
        "test_disclosure": "Full-data tabular test has previously been inspected; graph training/selection uses training and validation only; final comparison is not a newly blind holdout",
        "code_sha256": code_hash(),
        "benchmark_only": benchmark,
    }
    write(out / "protocol.json", protocol)
    runs, candidates = [], {}
    for seed in protocol["seeds"]:
        for kind in ("sage", "rgcn"):
            model, result = fit(kind, seed, cache, labels, split, epochs, batch_size)
            runs.append(result)
            if seed == 11:
                candidates[kind] = model
            write(out / "progress.json", runs)
    if benchmark:
        write(
            out / "benchmark.json",
            {"runs": runs, "scope": "Capacity measurement only; not final model selection"},
        )
        return
    means = {
        kind: float(np.mean([r["validation_ap"] for r in runs if r["model"] == kind]))
        for kind in candidates
    }
    selected = next(kind for kind in candidates if means[kind] >= max(means.values()) - 0.005)
    cal = split["calibration"]
    p = predict_batched(candidates[selected], cache, cal, batch_size)
    calibrator = LogisticRegression(C=1.0).fit(logit(p), labels[cal])
    joblib.dump(
        {"models": candidates, "selected": selected, "calibrator": calibrator},
        out / "bundle.joblib",
    )
    write(out / "validation.json", {"runs": runs, "mean_ap": means, "selected": selected})
    write(
        out / "freeze.json",
        {
            "code_sha256": code_hash(),
            "bundle_sha256": file_hash(out / "bundle.joblib"),
            "dataset_sha256": manifest["dataset_sha256"],
        },
    )
    print("Frozen scaled graph experiment; no final metrics opened", flush=True)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def final(folder, out, batch_size):
    if (out / "final.json").exists():
        raise ValueError("Final already evaluated; refusing repeat")
    freeze = json.loads((out / "freeze.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, expected in manifest["cache_sha256"].items():
        if file_hash(folder / name) != expected:
            raise ValueError(f"Cache integrity failure: {name}")
    if freeze["code_sha256"] != code_hash() or freeze["bundle_sha256"] != file_hash(
        out / "bundle.joblib"
    ):
        raise ValueError("Frozen model/code integrity mismatch")
    frame = validate(pd.read_csv(folder / "events.csv"))
    if digest(frame) != freeze["dataset_sha256"]:
        raise ValueError("Dataset checksum mismatch")
    destination = out / "inference-cache"
    if destination.exists():
        raise ValueError("Inference cache already exists; inspect incomplete prior run")
    destination.mkdir()
    start = time.perf_counter()
    scaler = joblib.load(folder / "scaler.joblib")
    x = scaler.transform(build_features(frame)).astype(np.float32)
    np.save(destination / "x.npy", x)
    neighbors = build_neighbors(frame, destination / "neighbors.npy")
    build_aggregates(x, neighbors, destination)
    del x, neighbors
    cache = GraphCache(destination)
    split = dict(np.load(folder / "splits.npz"))
    te = split["test"]
    bundle = joblib.load(out / "bundle.joblib")
    p = {
        kind: predict_batched(model, cache, te, batch_size)
        for kind, model in bundle["models"].items()
    }
    p["calibrated"] = bundle["calibrator"].predict_proba(logit(p[bundle["selected"]]))[:, 1]
    y, amount = frame.label.to_numpy()[te], frame.amount.to_numpy()[te]
    write(
        out / "final.json",
        {
            "selected": bundle["selected"],
            "metrics": {kind: metrics(y, values, amount) for kind, values in p.items()},
            "unseen": {
                kind: metrics(y[mask], p["calibrated"][mask], amount[mask])
                for kind, mask in unseen(frame, split["train"], te).items()
            },
            "bootstrap": bootstrap_ap(y, p["calibrated"]),
            "elapsed_seconds": time.perf_counter() - start,
            "rss_after_bytes": psutil.Process().memory_info().rss,
            "test_disclosure": "Same held-out window as previously inspected tabular comparison; not a newly blind evaluation",
        },
    )
    print("Scaled graph final comparison complete", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "benchmark", "train", "final"])
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--rows", type=int, default=590540)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=1024)
    args = parser.parse_args()
    if args.rows < 10 or args.epochs < 1 or args.batch_size < 1:
        raise ValueError("Positive sizes and at least ten rows required")
    torch.set_num_threads(2)
    if args.command != "prepare" and args.out is None:
        parser.error("--out is required")
    with MemoryMonitor() as monitor:
        if args.command == "prepare":
            prepare(args.cache, args.rows)
        elif args.command == "final":
            final(args.cache, args.out, args.batch_size)
        else:
            train(args.cache, args.out, args.epochs, args.batch_size, args.command == "benchmark")
    destination = args.cache if args.command == "prepare" else args.out
    write(destination / f"{args.command}-resources.json", monitor.result)


if __name__ == "__main__":
    main()
