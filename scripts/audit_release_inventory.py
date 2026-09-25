"""Read-only release inventory, artifact integrity and clean-source checks."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path.cwd()
CLEAN = ROOT / "artifacts/release-audit-20260914"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    files = [
        p
        for p in subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
        if p
    ]
    forbidden = [
        p
        for p in files
        if p.startswith(("data/", "artifacts/", "mlruns/"))
        or p == ".env"
        or "/test-results/" in p
        or "/node_modules/" in p
    ]
    if forbidden:
        raise ValueError(f"Private/generated files eligible for Git: {forbidden}")
    runtime = [
        p
        for p in files
        if p.startswith(("ml/", "scaling/", "services/", "apps/web/"))
        or p in ("pyproject.toml", "uv.lock", "infrastructure/Dockerfile.api", "compose.yaml")
    ]
    mismatches = [p for p in runtime if not (CLEAN / p).exists() or sha(ROOT / p) != sha(CLEAN / p)]
    if mismatches:
        raise ValueError(f"Runtime source differs from clean build: {mismatches}")
    integrity = {}
    for name in ["release", "ieee-cohort-10000", "ieee-full-tabular", "scaling/full-gnn"]:
        folder = ROOT / "artifacts" / name
        freeze_path = folder / "freeze.json"
        if not freeze_path.exists():
            raise ValueError(f"Required experiment not frozen: {name}")
        freeze = json.loads(freeze_path.read_text())
        actual = sha(folder / "bundle.joblib")
        if actual != freeze["bundle_sha256"]:
            raise ValueError(f"Bundle mismatch: {name}")
        integrity[name] = {"bundle_sha256": actual, "verified": True}
    required = [
        "README.md",
        "model-card.md",
        "architecture.md",
        "docs/completion.md",
        "docs/operations.md",
        "docs/demo.webm",
        "docs/screenshots/workspace.png",
        "docs/ieee-results.md",
        "docs/ieee-full-tabular.md",
        "docs/scaled-gnn-results.md",
        "docs/results/scaled-gnn/release-selection.json",
    ]
    if not all((ROOT / p).is_file() for p in required):
        raise ValueError("Required delivery artifact missing")
    result = {
        "eligible_files": len(files),
        "runtime_files_compared": len(runtime),
        "clean_runtime_matches": True,
        "private_generated_files_eligible": forbidden,
        "frozen_bundle_integrity": integrity,
        "required_delivery_files_present": True,
        "git_remotes": subprocess.check_output(["git", "remote"]).decode().splitlines(),
        "scope": "Source/artifact inventory, not a comprehensive secret or vulnerability scan",
    }
    Path("docs/results/release-inventory.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
