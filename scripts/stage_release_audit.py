"""Stage only version-control-eligible files for a clean release build."""

import shutil
import subprocess
from pathlib import Path

root = Path.cwd().resolve()
output = root / "artifacts" / "release-audit-20260914"
if output.exists():
    raise SystemExit("Audit folder already exists; preserve earlier evidence")
files = (
    subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    .decode()
    .split("\0")
)
for name in filter(None, files):
    original = (root / name).resolve()
    target = (output / name).resolve()
    if not original.is_relative_to(root) or not target.is_relative_to(output):
        raise ValueError("File outside workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, target)
print(f"Staged {len(list(filter(None, files)))} files in {output}")
