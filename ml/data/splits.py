import numpy as np
import pandas as pd

from ml.data.dataset import ENTITIES


def chronological(df: pd.DataFrame) -> dict[str, np.ndarray]:
    times = np.sort(df.time.unique())
    if len(times) < 10:
        raise ValueError("At least ten distinct event times are required")
    t1, t2 = times[int(len(times) * 0.6)], times[int(len(times) * 0.8)]
    return {
        "train": np.flatnonzero(df.time.to_numpy() < t1),
        "validation": np.flatnonzero((df.time.to_numpy() >= t1) & (df.time.to_numpy() < t2)),
        "test": np.flatnonzero(df.time.to_numpy() >= t2),
    }


def unseen(df, train, subset):
    return {
        c: (
            ~df.iloc[subset][c].isin(set(df.iloc[train][c].dropna())) & df.iloc[subset][c].notna()
        ).to_numpy()
        for c in ENTITIES
    }
