"""Export aggregate rolling research evidence, never raw events or predictions."""

import json
import shutil
from pathlib import Path

import numpy as np


def main():
    source = Path("artifacts/research-v2")
    decision = json.loads((source / "decision.json").read_text())
    runs = json.loads((source / "progress.json").read_text())
    target = Path("docs/results/research-v2")
    target.mkdir(exist_ok=True, parents=True)
    for name in ["protocol.json", "cache.json", "progress.json", "decision.json", "resources.json"]:
        shutil.copyfile(source / name, target / name)
    lines = [
        "# Research improvement: rolling development validation",
        "",
        "This experiment uses only the original 355,520-row training prefix. It does not reopen or rescore the previously inspected final window. The three rolling assessment blocks are development validation, not newly blind tests. The [protocol](research-v2-protocol.md) was fixed before fitting.",
        "",
        "| Candidate | Fold 1 AP | Fold 2 AP | Fold 3 AP | Mean AP | Mean precision@100 | Seeds per fold |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, folds in decision["fold_metrics"].items():
        seeds = sorted({r["seed"] for r in runs if r["candidate"] == name})
        aps = [f["pr_auc"] for f in folds]
        precision = np.mean([f["precision_at_k"] for f in folds])
        lines.append(
            f"| {name} | {aps[0]:.4f} | {aps[1]:.4f} | {aps[2]:.4f} | {np.mean(aps):.4f} | {precision:.2%} | {', '.join(map(str, seeds))} |"
        )
    lines += [
        "",
        f"The predeclared gates selected **{decision['selected']}** as the staging candidate after {decision['run_count']} fitted runs. Eligibility required an AP gain of 0.005, no loss in mean top-100 precision, improvement in at least two folds and no fold AP loss greater than 10%. A graph candidate screened with only seed 11 cannot be promoted without the two confirmation seeds.",
        "",
        "A failed promotion is retained as a negative research result, not followed by extra unrecorded tuning. The graph screen uses a 40-epoch budget and may underfit; it does not establish that longer or different GNN training can never help. The regularized tree changes several parameters together, so its differences cannot be attributed to one parameter.",
        "",
        "| Candidate | Mean calibrated Brier | Mean ECE | Total fit seconds |",
        "|---|---:|---:|---:|",
    ]
    for name, folds in decision["fold_metrics"].items():
        seconds = sum(r["fit_seconds"] for r in runs if r["candidate"] == name)
        lines.append(
            f"| {name} | {np.mean([f['brier'] for f in folds]):.4f} | {np.mean([f['ece'] for f in folds]):.4f} | {seconds:.1f} |"
        )
    lines += [
        "",
        "Calibration fits only on each fold's separate calibration block. Individual results, seeds, checkpoint epochs and metric records are retained in [progress.json](results/research-v2/progress.json). The original release metrics remain unchanged. These development outcomes support a local staging choice; new labeled time periods and independent analyst acceptance remain live-use gates.",
        "",
        "The tuple-based feature builder passed original-feature equivalence, tied-time, missing-identifier, label-invariance and future-row checks. A separate [same-prefix timing measurement](results/history-benchmark.json) records its measured preprocessing improvement without changing the feature definition.",
    ]
    Path("docs/research-v2-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Aggregate research report written")


if __name__ == "__main__":
    main()
