"""Freeze the release comparison choice from validation only, before graph final evaluation."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def main():
    destination = Path("artifacts/scaling/release-selection.json")
    if destination.exists():
        raise ValueError("Release comparison selection already frozen")
    graph_path = Path("artifacts/scaling/full-gnn/validation.json")
    if (graph_path.parent / "final.json").exists():
        raise ValueError("Freeze selection before graph final evaluation")
    tab_path = Path("artifacts/ieee-full-tabular/validation.json")
    graph = json.loads(graph_path.read_text())
    tabular = json.loads(tab_path.read_text())
    graph_protocol = json.loads((graph_path.parent / "protocol.json").read_text())
    tab_protocol = json.loads((tab_path.parent / "protocol.json").read_text())
    if graph_protocol["dataset_sha256"] != tab_protocol["dataset_sha256"]:
        raise ValueError("Comparison datasets differ")
    if len(graph["runs"]) != 6 or len(tabular["runs"]) != 9:
        raise ValueError("All predeclared runs must be complete")
    means = {**tabular["mean_ap"], **graph["mean_ap"]}
    order = ["logistic", "xgboost", "xgboost_graph", "sage", "rgcn"]
    selected = next(name for name in order if means[name] >= max(means.values()) - 0.005)
    result = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "selected": selected,
        "validation_mean_ap": means,
        "policy": "Within 0.005 of best mean validation AP, prefer model order logistic, xgboost, xgboost_graph, sage, rgcn",
        "serving_seed": 11,
        "scope": "Offline full-data comparison; does not replace the separately frozen investigator cohort deployment",
        "input_sha256": {
            p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in [graph_path, tab_path]
        },
        "disclosure": "Graph final metrics not read for this selection; the earlier tabular final comparison was previously inspected",
    }
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
