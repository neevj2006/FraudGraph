"""Write an inspectable review table for the available synthetic validation errors."""

import json
from collections import Counter
from pathlib import Path

import pandas as pd


def main():
    path = Path("artifacts/release")
    diagnostics = json.loads((path / "validation-diagnostics.json").read_text())
    frame = pd.read_csv(path / "events.csv").set_index("id")
    lines = [
        "# Synthetic validation error review",
        "",
        "These are observed synthetic validation errors under the frozen top-100 policy. "
        "The review uses known generator signatures for diagnosis only; those marker strings are not model inputs. "
        "It does not establish the cause of a real-world error or change the model.",
        "",
    ]
    for name, group in diagnostics["error_review"].items():
        counts = Counter()
        lines += [
            f"## {name.replace('_', ' ').title()}",
            "",
            f"Available: {group['available']}. Reviewed below: {len(group['examples'])}.",
            "",
            "| Transaction | Score | Amount | Prior device events | Missing IDs | Observed context |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for example in group["examples"]:
            row = frame.loc[example["id"]]
            if row.device == "public-terminal":
                category = "Legitimate shared terminal"
            elif str(row.card).startswith("pool-") or str(row.device).startswith("shared-"):
                category = "Injected shared-infrastructure cohort"
            elif pd.isna(row.device):
                category = "Missing device signature"
            else:
                category = "Ordinary identifier pattern; outcome requires other evidence"
            counts[category] += 1
            lines.append(
                f"| {example['id']} | {example['score']:.3f} | {example['amount']:.2f} | "
                f"{example['device_history_count']} | {example['missing_identifiers']} | {category} |"
            )
        lines += [
            "",
            "Context counts: " + "; ".join(f"{k}: {v}" for k, v in counts.items()) + ".",
            "",
        ]
        print(
            name,
            "available=",
            group["available"],
            "reviewed=",
            len(group["examples"]),
            dict(counts),
        )
    lines += [
        "## Interpretation and follow-up",
        "",
        "A negative label in the injected shared-infrastructure cohort is deliberately possible in the generator. "
        "Shared infrastructure raises risk without guaranteeing fraud. Public-terminal false positives would "
        "require context about legitimate sharing; do not automatically blacklist the signature.",
        "",
        "Ordinary-pattern false negatives are consistent with the generator's low-rate independent fraud, "
        "which may have little recoverable relational signal. This is a hypothesis based on the simulation, "
        "not a causal explanation. Missing identifiers also remove evidence, matching the separate robustness result.",
        "",
        "Measurable future experiments: evaluate missing-identifier training augmentation on a new validation "
        "window; compare workload and captured value against the historical-feature tree; gather independent "
        "context for shared hubs. Keep the current final holdout closed and the serving model frozen.",
        "",
        "There are fewer than 25 false negatives in this validation window. All available examples are "
        "included rather than manufacturing additional errors or changing the threshold to meet a count. "
        "The public-data review remains outstanding.",
    ]
    Path("docs/error-review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
