"""Canonical event schema, honest synthetic fixture, and IEEE-CIS adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ENTITIES = ("account", "card", "device", "address", "merchant")
REQUIRED = ("id", "time", "amount", "label", *ENTITIES)


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df = frame.loc[:, list(REQUIRED)].copy()
    if df.empty or df.id.isna().any() or df.id.astype(str).duplicated().any():
        raise ValueError("Events must have nonempty, unique IDs")
    df["id"] = df.id.astype(str)
    for col in ("time", "amount", "label"):
        df[col] = pd.to_numeric(df[col], errors="raise")
        if not np.isfinite(df[col]).all():
            raise ValueError(f"{col} must be finite")
    if (df.time < 0).any() or (df.amount < 0).any() or not df.label.isin([0, 1]).all():
        raise ValueError("Invalid time, amount, or binary label")
    for col in ENTITIES:
        df[col] = df[col].map(lambda x: None if pd.isna(x) or str(x).strip() == "" else str(x))
    return df.sort_values(["time", "id"], kind="stable").reset_index(drop=True)


def digest(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False, lineterminator="\n").encode()).hexdigest()


def synthetic(n: int = 1800, seed: int = 42) -> pd.DataFrame:
    """Controlled simulation; labels are never used by the feature builder."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        ring = rng.random() < 0.09
        a = int(rng.integers(0, max(30, 70 + i // 7)))
        device = f"d{a // 2}"
        card = f"c{a}"
        if ring:
            device = f"shared-{int(rng.integers(0, 4))}"
            card = f"pool-{int(rng.integers(0, 8))}"
        elif rng.random() < 0.07:
            device = "public-terminal"  # A legitimate shared hub.
        label = int(rng.random() < (0.72 if ring else 0.016))
        rows.append(
            {
                "id": f"TX-{i:06d}",
                "time": i * 300.0,
                "amount": round(float(rng.lognormal(4.1 + 0.55 * ring, 0.85)), 2),
                "label": label,
                "account": f"a{a}",
                "card": card,
                "device": device if rng.random() > 0.035 else None,
                "address": f"region-{a % 35}",
                "merchant": f"m{rng.integers(0, 24)}",
            }
        )
    return validate(pd.DataFrame(rows))


def ieee(path: Path, identity: Path | None = None, limit: int | None = None) -> pd.DataFrame:
    raw = pd.read_csv(path, nrows=limit)
    if identity:
        raw = raw.merge(
            pd.read_csv(identity), on="TransactionID", how="left", validate="one_to_one"
        )

    # These are ambiguous shared signatures, not asserted person/card/device identities.
    def signature(cols):
        present = [c for c in cols if c in raw]
        if not present:
            return pd.Series(None, index=raw.index)
        return raw[present].apply(
            lambda row: None if row.isna().all() else "|".join(row.fillna("?").astype(str)), axis=1
        )

    return validate(
        pd.DataFrame(
            {
                "id": raw.TransactionID.astype(str),
                "time": raw.TransactionDT,
                "amount": raw.TransactionAmt,
                "label": raw.isFraud,
                "account": signature(["card1", "addr1", "P_emaildomain"]),
                "card": signature(["card1", "card2", "card3", "card5"]),
                "device": signature(["DeviceType", "DeviceInfo"]),
                "address": signature(["addr1", "addr2"]),
                "merchant": None,
            }
        )
    )


def audit(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "sha256": digest(df),
        "time_range": [float(df.time.min()), float(df.time.max())],
        "fraud_rate": float(df.label.mean()),
        "missingness": df.isna().mean().to_dict(),
        "amount_quantiles": {
            str(k): float(v) for k, v in df.amount.quantile([0, 0.5, 0.95, 1]).items()
        },
        "identifiers": {c: int(df[c].nunique()) for c in ENTITIES},
        "label_delay": "Not observed; labels are offline targets and never history features.",
    }
