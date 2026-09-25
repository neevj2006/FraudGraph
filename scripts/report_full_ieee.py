"""Copy aggregate full-data tabular results and write the evaluation report."""

import json
import shutil
from pathlib import Path

source = Path("artifacts/ieee-full-tabular")
target = Path("docs/results/ieee-full-tabular")


def main():
    protocol = json.loads((source / "protocol.json").read_text())
    validation = json.loads((source / "validation.json").read_text())
    final = json.loads((source / "final.json").read_text())
    target.mkdir(parents=True, exist_ok=True)
    for name in ["protocol.json", "validation.json", "freeze.json", "final.json"]:
        shutil.copyfile(source / name, target / name)
    lines = [
        "# Full IEEE-CIS tabular evaluation",
        "",
        "This separate experiment uses all 590,540 labeled transactions and evaluates tabular models only. The public-cohort GNN results remain separate and frozen. No full-dataset GNN performance is claimed.",
        "",
        f"Chronological split: {protocol['split_rows']['train']:,} training, {protocol['split_rows']['validation']:,} validation and {protocol['split_rows']['test']:,} final-test transactions. Earlier validation selects models; later validation fits Platt calibration. The three seeded runs are deterministic for these configurations; zero variation is not statistical certainty.",
        "",
        "| Model | Validation AP | Final AP | Precision@100 | Recall@100 | Fraud value fraction |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, ap in validation["mean_ap"].items():
        m = final["metrics"][name]
        lines.append(
            f"| {name} | {ap:.4f} | {m['pr_auc']:.4f} | {m['precision_at_k']:.2%} | {m['recall_at_k']:.2%} | {m['fraud_value_fraction']:.2%} |"
        )
    m = final["metrics"]["calibrated"]
    lines += [
        "",
        f"The frozen selection is {final['selected']}. Its calibrated final AP is {m['pr_auc']:.4f}; Brier score is {m['brier']:.4f} and ECE is {m['ece']:.4f}. There are {m['positives']:,} fraud cases in the holdout. Recall at 1% false-positive rate is {m['recall_at_1pct_fpr']:.2%}.",
        "",
        "Top-100 metrics describe a fixed total review budget over this entire holdout, not a daily alert rate. This is much more selective than top-100 on the small cohort, so the two experiments are not directly comparable on recall. Scores do not establish identity, guilt or causal evidence.",
        "",
        f"The row-bootstrap AP interval is {final['bootstrap']['lower']:.4f} to {final['bootstrap']['upper']:.4f}. The 400-repeat bootstrap ignores temporal and entity dependence and is only a descriptive uncertainty estimate.",
        "",
        f"Training plus validation preprocessing and fitting took {validation['elapsed_seconds']:.1f} seconds. Final evaluation including history feature reconstruction and uncertainty calculation took {final['elapsed_seconds']:.1f} seconds. These are batch observations, not API latency benchmarks or peak memory measurements.",
        "",
        "| Unseen signature slice | Rows | Frauds | Calibrated AP |",
        "|---|---:|---:|---:|",
    ]
    for kind, result in final["unseen"].items():
        ap = "unavailable" if result["pr_auc"] is None else f"{result['pr_auc']:.4f}"
        lines.append(f"| {kind} | {result['n']} | {result.get('positives', 0)} | {ap} |")
    lines += [
        "",
        "This closes the full-dataset tabular comparison and longer-horizon evaluation. It does not establish that the full-batch graph implementation fits local memory. The exact graph-size assessment and the small public GNN cohort remain the evidence for that separate scale limitation. The source schema omits many original IEEE-CIS attributes; these are deliberately simple project baselines, not competition-leading models.",
        "",
        "The final was opened once after verifying model, data and code checksums. No subsequent model selection or tuning used the final outcomes. The full baseline bundle is an offline experiment; the serving application continues to use its compatible frozen cohort bundle.",
    ]
    Path("docs/ieee-full-tabular.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Published aggregate full-data tabular report")


if __name__ == "__main__":
    main()
