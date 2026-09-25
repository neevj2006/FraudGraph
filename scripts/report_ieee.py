"""Publish aggregate IEEE cohort evidence without source rows or identifiers."""

import json
import shutil
from pathlib import Path

source = Path("artifacts/ieee-cohort-10000")
target = Path("docs/results/ieee-cohort-10000")
target.mkdir(parents=True, exist_ok=True)
for name in [
    "manifest.json",
    "freeze.json",
    "cohort-protocol.json",
    "audit.json",
    "experiments.json",
    "final-evaluation.json",
    "calibration.json",
    "graph-quality.json",
    "drift.json",
    "edge-sensitivity.json",
    "robustness.json",
    "diagnostics.png",
]:
    shutil.copyfile(source / name, target / name)


def load(name):
    return json.loads((source / name).read_text())


final, experiments, diagnostics = (
    load("final-evaluation.json"),
    load("experiments.json"),
    load("validation-diagnostics.json"),
)
lines = [
    "# IEEE-CIS cohort results",
    "",
    "This experiment uses the first 10,000 chronological transactions (about 2.6 days) from the 590,540-row labeled dataset. It is a small public-data cohort benchmark, not full-dataset or production validation. The cohort was chosen for local memory capacity before fitting models. Raw records and identifier signatures are excluded from this report.",
    "",
    f"Frozen version: `{final['version']}`. The unchanged selection policy chose R-GCN from three-seed validation means; serving uses predeclared seed 11. The final holdout was evaluated once.",
    "",
    "| Model | Validation AP mean ± SD | Final AP | Precision@100 | Recall@100 | Fraud value fraction |",
    "|---|---:|---:|---:|---:|---:|",
]
for name, stats in experiments["aggregate"].items():
    m = final["metrics"][name]
    lines.append(
        f"| {name} | {stats['mean_ap']:.4f} ± {stats['std_ap']:.4f} | {m['pr_auc']:.4f} | {m['precision_at_k']:.2%} | {m['recall_at_k']:.2%} | {m['fraud_value_fraction']:.2%} |"
    )
m = final["metrics"]["calibrated"]
lines += [
    "",
    f"The final window has {m['n']:,} transactions and {m['positives']} frauds. The selected model catches 20 frauds in 100 alerts, missing 56; 80 reviewed alerts are false positives. Recall at 1% false-positive rate is {m['recall_at_1pct_fpr']:.2%}. Its amount-weighted capture is only {m['fraud_value_fraction']:.2%}. This is insufficient evidence for operational deployment.",
    "",
    "The history-feature tree beats the selected GNN on final AP. Logistic regression captures more fraud value despite poor ranking. These negative comparisons are retained without changing the frozen selection or retuning on the holdout. Three-seed GNN variation is material; deterministic tree configurations have zero seed variation because subsampling is disabled.",
    "",
    f"Calibration reduces R-GCN Brier score from {final['metrics']['rgcn']['brier']:.4f} to {m['brier']:.4f}; calibrated ECE is {m['ece']:.4f}. Calibration used only 16 positive cases in its fit window, limiting confidence. The 400-repeat row-bootstrap AP interval is {final['calibrated_ap_interval']['lower']:.4f}–{final['calibrated_ap_interval']['upper']:.4f}; it ignores temporal/entity dependence.",
    "",
    "## Validation error review",
    "",
    "The following review covers the first 25 chronological errors of each class at the fixed top-100 budget. It describes observed missingness and prior device activity, not causal explanations or a human investigator study. Full case details remain in the ignored local artifact.",
    "",
]
review = {}
for name, group in diagnostics["error_review"].items():
    examples = group["examples"]
    empty = sum(e["device_history_count"] == 0 for e in examples)
    review[name] = {
        "available": group["available"],
        "reviewed": len(examples),
        "zero_prior_device_events": empty,
    }
    lines += [
        f"### {name.replace('_', ' ').title()}",
        "",
        f"Available: {group['available']}; reviewed: {len(examples)}. {empty} reviewed cases have no prior device events. Missing merchant information affects every case; additional missing signatures further limit observable relationships.",
        "",
        "| Review case | Prior device events | Missing signature fields | Interpretation |",
        "|---|---:|---:|---|",
    ]
    for i, e in enumerate(examples, 1):
        interpretation = (
            "No prior device evidence; inspect other signatures and external context"
            if e["device_history_count"] == 0
            else "Device history exists; coarse sharing alone does not establish fraud"
        )
        lines.append(
            f"| {i} | {e['device_history_count']} | {e['missing_identifiers']} | {interpretation} |"
        )
    lines.append("")
lines += [
    "## Robustness and scale",
    "",
    "Validation-only perturbations reduce AP from 0.0743 to 0.0542 with 20% additional missing signatures, and to 0.0482 when 10% of devices are mapped to a shared hub. Amount and one-hour time shifts have smaller effects. These diagnostics include calibration-fit rows and do not select new models.",
    "",
    "Scoring all five models over 10,000 graph rows took about 4.0 seconds in this run. Validation perturbation process RSS after calls was approximately 493–518 MiB, including libraries and all models; this is not peak memory or a production latency guarantee. The full 590,540-row dataset was imported and audited, but full-scale GNN training and a longer temporal evaluation have not been performed.",
    "",
    "Unseen-account AP is 0.0837 across 1,155 cases (43 frauds). Unseen-card and unseen-device slices contain only 5 and 6 frauds respectively; they do not support a strong generalization claim.",
    "",
    "The model code and original synthetic freeze are unchanged. The public-data result is a reproducible research baseline with explicit limitations.",
]
Path("docs/ieee-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
(target / "validation-summary.json").write_text(
    json.dumps(
        {"slices": diagnostics["slices"], "error_review": review, "caveat": diagnostics["caveat"]},
        indent=2,
    )
)
print("Wrote aggregate report and 50-case diagnostic review")
