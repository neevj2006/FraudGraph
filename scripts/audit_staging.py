"""Verify shipped API source and immutable bundles without reopening model evaluation."""

import hashlib
import json
import subprocess
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    eligible = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
    )
    assert not any(p.startswith(("artifacts/", "data/")) or p == ".env" for p in eligible)
    code = "import pathlib,hashlib,json; print(json.dumps({str(p.relative_to('/app')):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('services','ml','scaling','research') for p in pathlib.Path('/app',folder).rglob('*.py')}))"
    image_sources = json.loads(
        subprocess.check_output(
            ["docker", "run", "--rm", "fraudgraph-staging-api:v2", "python", "-c", code]
        )
    )
    assert all(sha(Path(name)) == digest for name, digest in image_sources.items()), (
        "Image source mismatch"
    )
    bundles = {}
    for name in (
        "release",
        "ieee-cohort-10000",
        "ieee-full-tabular",
        "scaling/full-gnn",
        "staging-model-v2",
    ):
        folder = Path("artifacts") / name
        freeze = json.loads((folder / "freeze.json").read_text())
        value = sha(folder / "bundle.joblib")
        assert value == freeze["bundle_sha256"]
        for relative, expected in freeze.get("assets", {}).items():
            assert sha(folder / relative) == expected
        bundles[name] = value
    result = {
        "api_image_source_files_verified": len(image_sources),
        "frozen_bundle_sha256": bundles,
        "private_files_eligible": False,
        "git_remotes": subprocess.check_output(["git", "remote"]).decode().splitlines(),
    }
    result["images"] = {
        name: subprocess.check_output(
            ["docker", "image", "inspect", name, "--format", "{{.Id}}"], text=True
        ).strip()
        for name in ("fraudgraph-staging-api:v2", "fraudgraph-staging-web:v2")
    }
    Path("docs/results/staging-inventory.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
