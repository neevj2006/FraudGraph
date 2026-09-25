import hashlib
import json
from pathlib import Path

import pandas as pd

from ml.data.dataset import audit, ieee

root = Path("data/ieee")
root.mkdir(parents=True, exist_ok=True)
source = Path.home() / "Downloads"
columns = [
    "TransactionID",
    "TransactionDT",
    "TransactionAmt",
    "isFraud",
    "card1",
    "card2",
    "card3",
    "card5",
    "addr1",
    "addr2",
    "P_emaildomain",
]
records = []
for name, cols in [
    ("train_transaction.csv", columns),
    ("train_identity.csv", ["TransactionID", "DeviceType", "DeviceInfo"]),
]:
    original = source / name
    h = hashlib.sha256()
    with original.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    target = root / ("projected-" + name)
    first = True
    for chunk in pd.read_csv(original, usecols=cols, chunksize=50000):
        chunk.to_csv(target, index=False, mode="w" if first else "a", header=first)
        first = False
    records.append(
        {
            "name": name,
            "size": original.stat().st_size,
            "sha256": h.hexdigest(),
            "projection_columns": cols,
        }
    )
    print("Projected", name, flush=True)
frame = ieee(root / "projected-train_transaction.csv", root / "projected-train_identity.csv")
frame.to_csv(root / "canonical.csv", index=False)
manifest = {
    "source": "https://www.kaggle.com/competitions/ieee-fraud-detection/data",
    "retrieved_date": "2026-09-13",
    "license": "Subject to Kaggle competition rules; locally acquired source files; no redistribution",
    "files": records,
    "transformation": "Read only mapped columns in bounded chunks before applying the unchanged IEEE adapter",
    "audit": audit(frame),
}
(root / "source-manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest["audit"], indent=2), flush=True)
