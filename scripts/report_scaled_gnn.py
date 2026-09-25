"""Publish aggregate scaling evidence after the once-only final comparison."""

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np


def main():
    folder = Path("artifacts/scaling/full-gnn")
    target = Path("docs/results/scaled-gnn")
    final = json.loads((folder / "final.json").read_text())
    validation = json.loads((folder / "validation.json").read_text())
    resources = json.loads((folder / "train-resources.json").read_text())
    tabular = json.loads(Path("artifacts/ieee-full-tabular/final.json").read_text())
    tab_val = json.loads(Path("artifacts/ieee-full-tabular/validation.json").read_text())
    selection_path = Path("artifacts/scaling/release-selection.json")
    selection = json.loads(selection_path.read_text())
    for name, expected in selection["input_sha256"].items():
        if hashlib.sha256(Path(name.replace("\\", "/")).read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen validation comparison changed")
    final_resources = json.loads((folder / "final-resources.json").read_text())
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(selection_path, target / "release-selection.json")
    for name in [
        "protocol.json",
        "validation.json",
        "freeze.json",
        "final.json",
        "train-resources.json",
        "final-resources.json",
    ]:
        shutil.copyfile(folder / name, target / name)
    capacity = {}
    for rows in [10000, 50000, 100000, 590540]:
        base = Path("artifacts/scaling")
        capacity[str(rows)] = {
            "prepare": json.loads((base / f"cache-{rows}" / "prepare-resources.json").read_text()),
            "benchmark": json.loads(
                (base / f"benchmark-{rows}" / "benchmark-resources.json").read_text()
            ),
            "runs": json.loads((base / f"benchmark-{rows}" / "benchmark.json").read_text())["runs"],
        }
    (target / "capacity.json").write_text(json.dumps(capacity, indent=2), encoding="utf-8")
    lines = [
        "# Full-dataset graph comparison",
        "",
        "Both graph families were trained on all 355,520 training transactions, selected using the separate 117,667-row validation window, and evaluated in batches on the 117,353-row held-out window. All 590,540 source transactions participate in the chronological protocol. This window was previously inspected for tabular results; this is a subsequent held-out comparison, not a newly blind evaluation.",
        "",
        "The optimized CPU implementation retains complete capped-eight temporal neighborhoods and the original full-batch objective through gradient accumulation. Small-graph predictions and gradients passed equivalence tests. No test-based tuning changed the frozen graph runs.",
        "",
        "| Model | Validation AP mean | Final AP | Precision@100 | Recall@100 | Value fraction |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ["logistic", "xgboost", "xgboost_graph"]:
        m = tabular["metrics"][name]
        lines.append(
            f"| {name} | {tab_val['mean_ap'][name]:.4f} | {m['pr_auc']:.4f} | {m['precision_at_k']:.2%} | {m['recall_at_k']:.2%} | {m['fraud_value_fraction']:.2%} |"
        )
    for name in ["sage", "rgcn"]:
        m = final["metrics"][name]
        lines.append(
            f"| {name} | {validation['mean_ap'][name]:.4f} | {m['pr_auc']:.4f} | {m['precision_at_k']:.2%} | {m['recall_at_k']:.2%} | {m['fraud_value_fraction']:.2%} |"
        )
    graph = final["metrics"][final["selected"]]
    tree = tabular["metrics"]["xgboost_graph"]
    relation = "lower" if graph["pr_auc"] < tree["pr_auc"] else "higher"
    lines += [
        "",
        f"The validation-selected graph has **{relation} held-out AP** than the history-feature tree: {graph['pr_auc']:.4f} versus {tree['pr_auc']:.4f}. At the top-100 budget its precision is {graph['precision_at_k']:.0%}, versus {tree['precision_at_k']:.0%} for the tree. This closes the scaling experiment, but does not establish that GNN complexity improves this task. AP, value capture and review-budget precision must be read separately; the frozen validation choice is retained without test-based reselection.",
        "",
        f"The graph-family selection rule chose **{final['selected']}**, using three-seed validation means and the 0.005 simplicity margin. Serving-seed comparisons use predeclared seed 11. The previously frozen tabular experiment remains a separate comparator. These results do not silently replace the cohort model used by the investigator application.",
        "",
        f"The overall five-family comparison chose **{selection['selected']}** from validation before graph final evaluation, using the same 0.005 simplicity margin. The input validation hashes and decision are recorded in [release-selection.json](results/scaled-gnn/release-selection.json). This is the offline research choice; production deployment requires a separate serving integration and acceptance decision.",
        "",
        "| Graph family | Validation AP population SD | Best epochs, seeds 11/29/42 |",
        "|---|---:|---|",
    ]
    for name in ["sage", "rgcn"]:
        runs = [r for r in validation["runs"] if r["model"] == name]
        lines.append(
            f"| {name} | {np.std([r['validation_ap'] for r in runs]):.4f} | {', '.join(str(r['best_epoch']) for r in runs)} |"
        )
    m = final["metrics"]["calibrated"]
    limit = json.loads((folder / "protocol.json").read_text())["epochs"]
    at_limit = sum(r["epochs_completed"] == limit for r in validation["runs"])
    lines += [
        "",
        f"{at_limit} of {len(validation['runs'])} runs reached the predeclared {limit}-epoch limit. Checkpoint epochs are reported above. This measures the declared training budget, not proven optimizer convergence, and no extra epochs were chosen after viewing held-out metrics.",
        "",
        f"The selected graph's calibrated AP is {m['pr_auc']:.4f}, Brier score {m['brier']:.4f}, ECE {m['ece']:.4f}, and recall at 1% FPR {m['recall_at_1pct_fpr']:.2%}. The final window contains {m['positives']:,} labeled frauds. Top-100 is a total-window review budget, not a daily alert rate.",
        "",
        f"The row-bootstrap AP interval is {final['bootstrap']['lower']:.4f}–{final['bootstrap']['upper']:.4f}. It ignores temporal/entity dependence. Neither this interval nor a graph connection establishes causality, identity or operational suitability.",
        "",
        f"The six-run training command took {resources['elapsed_seconds']:.1f} seconds and sampled {resources['sampled_peak_rss_bytes'] / 2**20:.1f} MiB peak process RSS. The container was capped at 2 GiB without additional swap. Final evaluation including full-history cache preparation took {final['elapsed_seconds']:.1f} seconds. Resource readings are host observations, not production service guarantees.",
        "",
        f"The entire final command, including integrity checks, took {final_resources['elapsed_seconds']:.1f} seconds and sampled {final_resources['sampled_peak_rss_bytes'] / 2**20:.1f} MiB peak process RSS under the same container limit. Monitoring begins after imports, samples every 20 ms, and excludes OS filesystem cache.",
        "",
        "| Unseen signature | Rows | Frauds | Calibrated AP |",
        "|---|---:|---:|---:|",
    ]
    for name, m in final["unseen"].items():
        ap = "unavailable" if m["pr_auc"] is None else f"{m['pr_auc']:.4f}"
        lines.append(f"| {name} | {m['n']} | {m.get('positives', 0)} | {ap} |")
    lines += [
        "",
        "Full-dataset graph training and evaluation are now measured. Production-scale API loading, streaming updates, independently measured analyst utility and automated adverse decisions remain outside this research release. Source data, cached vectors and model weights remain local and excluded from Git.",
    ]
    Path("docs/scaled-gnn-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Published aggregate full-data GNN comparison")


if __name__ == "__main__":
    main()
