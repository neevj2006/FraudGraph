"""Durable SQL job queue: one worker for SQLite, row locks for PostgreSQL."""

import argparse
import hashlib
import json
import time

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select

from ml.data.dataset import validate
from ml.graph.build import evidence
from ml.pipeline import probabilities, score_rows
from services.api.config import Settings
from services.api.main import record, stamp_provenance
from services.api.storage import Alert, Job, database, index_alert
from services.inference.evidence import EvidenceIndex
from services.inference.scaled import score_scaled, verify_assets


def run_one(settings, sessions):
    # Keep the transaction open: a crash rolls back the claim and all scored alerts.
    with sessions.begin() as session:
        job = session.scalar(
            select(Job)
            .where(Job.status == "queued")
            .order_by(Job.created)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        try:
            path = settings.artifact_dir
            freeze = json.loads((path / "freeze.json").read_text())
            if (
                hashlib.sha256((path / "bundle.joblib").read_bytes()).hexdigest()
                != freeze["bundle_sha256"]
            ):
                raise ValueError("Model integrity check failed")
            bundle = joblib.load(path / "bundle.joblib")
            scaled = bundle.get("format") == "scaled-v2"
            if scaled:
                verify_assets(path)
            if bundle["manifest"]["version"] != job.payload["version"]:
                raise ValueError("Requested model version is not loaded")
            history = validate(pd.read_csv(path / "events.csv"))
            splits = json.loads((path / "splits.json").read_text())
            history = history[history.id.isin(splits["train"] + splits["validation"])].copy()
            events = pd.DataFrame([dict(e, label=0) for e in job.payload["events"]])
            if set(events.id) & set(history.id):
                raise ValueError("Event IDs overlap the frozen historical dataset")
            if events.time.min() <= history.time.max():
                raise ValueError("Batch must be later than the frozen history cutoff")
            frame = validate(pd.concat([history, events], ignore_index=True))
            start = time.perf_counter()
            idx = np.flatnonzero(frame.id.isin(events.id))
            if scaled:
                rows = score_scaled(bundle, path, frame, idx)
                evidence_index = EvidenceIndex(frame)
                graphs = {row["id"]: evidence_index.get(row["id"]) for row in rows}
                latency = (time.perf_counter() - start) * 1000
                for row in rows:
                    row["latency_ms"] = latency / len(events)
            else:
                preds = probabilities(bundle, frame)
                latency = (time.perf_counter() - start) * 1000
                rows = score_rows(bundle, frame, preds, idx, latency / len(events)).to_dict(
                    "records"
                )
                graphs = {row["id"]: evidence(frame, row["id"]) for row in rows}
            for row in rows:
                if session.get(Alert, row["id"]):
                    raise ValueError("Event ID already scored by another batch")
            for row in rows:
                index_alert(session, row["id"], graphs[row["id"]])
                session.add(
                    Alert(
                        id=row["id"],
                        payload=stamp_provenance(row, bundle["manifest"]),
                        graph=graphs[row["id"]],
                    )
                )
            job.status, job.result = (
                "completed",
                {
                    "alert_ids": [r["id"] for r in rows],
                    "latency_ms": latency,
                    "history_policy": "frozen training/validation plus this batch",
                },
            )
            record(session, job.owner, "batch_completed", job.id)
        except (ValueError, OSError, KeyError) as exc:
            job.status, job.result = "failed", {"error": str(exc)}
            record(session, job.owner, "batch_failed", job.id)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    settings.validate_deployment()
    engine, sessions = database(settings.database_url)
    try:
        while True:
            worked = run_one(settings, sessions)
            if args.once:
                break
            if not worked:
                time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
