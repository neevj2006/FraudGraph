"""All historical aggregates exclude the entire current timestamp group."""

from collections import defaultdict

import numpy as np

from ml.data.dataset import ENTITIES

FEATURES = ["log_amount", "hour_sin", "hour_cos", "missing_identifiers"] + [
    f"{c}_{stat}" for c in ENTITIES for stat in ("log_prior_count", "log_age", "log_accounts")
]


def assert_cutoff(source_time: float, prediction_time: float):
    if source_time >= prediction_time:
        raise ValueError("Leakage: history must be strictly earlier than prediction time")


def build_features(df):
    counts, first, accounts = defaultdict(int), {}, defaultdict(set)
    values = np.zeros((len(df), len(FEATURES)), dtype=np.float32)
    for timestamp, group in df.groupby("time", sort=True):
        for idx, row in group.iterrows():
            hour = timestamp / 3600 % 24
            v = [
                np.log1p(row.amount),
                np.sin(hour * np.pi / 12),
                np.cos(hour * np.pi / 12),
                sum(row[c] is None for c in ENTITIES),
            ]
            for c in ENTITIES:
                key = (c, row[c])
                exists = row[c] is not None
                v.extend(
                    [
                        np.log1p(counts[key]) if exists else 0,
                        np.log1p(timestamp - first[key]) if exists and key in first else 0,
                        np.log1p(len(accounts[key])) if exists else 0,
                    ]
                )
            values[idx] = v
        for _, row in group.iterrows():
            for c in ENTITIES:
                if row[c] is not None:
                    key = (c, row[c])
                    counts[key] += 1
                    first.setdefault(key, timestamp)
                    if row.account is not None:
                        accounts[key].add(row.account)
    return values
