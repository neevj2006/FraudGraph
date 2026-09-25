"""Predeclared capacity ladder; each stage runs in a fresh Python process."""

import subprocess
import sys
from pathlib import Path

for rows in (10000, 50000, 100000, 590540):
    folder = Path(f"artifacts/scaling/cache-{rows}")
    out = Path(f"artifacts/scaling/benchmark-{rows}")
    base = [sys.executable, "-u", "-m", "scaling.experiment"]
    if not (folder / "manifest.json").exists():
        subprocess.run([*base, "prepare", "--cache", str(folder), "--rows", str(rows)], check=True)
    if not (out / "benchmark.json").exists():
        subprocess.run(
            [
                *base,
                "benchmark",
                "--cache",
                str(folder),
                "--out",
                str(out),
                "--epochs",
                "1",
                "--batch-size",
                "1024",
            ],
            check=True,
        )
    print(f"Capacity stage complete: {rows}", flush=True)
