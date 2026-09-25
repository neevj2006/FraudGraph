"""Mirror frozen local runs to an optional MLflow tracking store."""

import argparse
import json


def main():
    from pathlib import Path

    import mlflow

    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts/release"))
    parser.add_argument("--tracking-uri", default="sqlite:///artifacts/mlflow.db")
    args = parser.parse_args()
    manifest = json.loads((args.artifacts / "manifest.json").read_text())
    runs = json.loads((args.artifacts / "experiments.json").read_text())["runs"]
    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment("FraudGraph")
    for run in runs:
        with mlflow.start_run(run_name=f"{manifest['version']}-{run['model']}-{run['seed']}"):
            mlflow.log_params(
                {
                    "model": run["model"],
                    "seed": run["seed"],
                    "dataset": manifest["dataset"],
                    "dataset_sha256": manifest["dataset_sha256"],
                    "code_sha256": manifest["code_sha256"],
                    "version": manifest["version"],
                    "split": manifest["split_version"],
                }
            )
            mlflow.log_metrics(
                {k: v for k, v in run.items() if isinstance(v, (int, float)) and k != "seed"}
            )
            mlflow.log_artifact(str(args.artifacts / "manifest.json"))
    print(f"Logged {len(runs)} runs to {args.tracking_uri}")


if __name__ == "__main__":
    main()
