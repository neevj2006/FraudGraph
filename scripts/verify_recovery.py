"""Back up local staging and restore into fresh scratch databases, never live databases."""

import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path

CONTAINER = "fraudgraph-staging-v2-db-1"
TABLES = ("alerts", "cases", "audit_events", "jobs", "entity_alerts")


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def sql(database, statement):
    return run(
        "docker",
        "exec",
        CONTAINER,
        "psql",
        "-U",
        "postgres",
        "-d",
        database,
        "-At",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        statement,
    )


def digest(database):
    return {
        table: sql(
            database,
            f"SELECT count(*) || ':' || md5(COALESCE(string_agg(row_to_json(t)::text, '' ORDER BY row_to_json(t)::text), '')) FROM {table} t",
        )
        for table in TABLES
    }


def main():
    suffix = uuid.uuid4().hex[:12]
    output = Path("artifacts/staging-v2/backups") / suffix
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for organization in ("north", "south"):
        source = f"fraudgraph_{organization}"
        target = f"recovery_{organization}_{suffix}"
        assert target.startswith("recovery_") and target != source
        dump = f"/tmp/{target}.dump"
        started = time.monotonic()
        before = digest(source)
        run(
            "docker",
            "exec",
            CONTAINER,
            "pg_dump",
            "-U",
            "postgres",
            "-Fc",
            "--no-owner",
            "--no-acl",
            "-f",
            dump,
            source,
        )
        local = output / f"{organization}.dump"
        run("docker", "cp", f"{CONTAINER}:{dump}", str(local))
        run("docker", "exec", CONTAINER, "createdb", "-U", "postgres", target)
        run(
            "docker",
            "exec",
            CONTAINER,
            "pg_restore",
            "-U",
            "postgres",
            "--exit-on-error",
            "--no-owner",
            "--no-acl",
            "-d",
            target,
            dump,
        )
        restored = digest(target)
        assert before == restored, "Restored data does not match source snapshot"
        assert before == digest(source), "Live source changed during recovery check"
        results.append(
            {
                "organization": organization,
                "tables_verified": list(TABLES),
                "rows": {table: int(value.split(":")[0]) for table, value in before.items()},
                "sha256": hashlib.sha256(local.read_bytes()).hexdigest(),
                "elapsed_seconds": time.monotonic() - started,
                "restored_exactly": True,
            }
        )
    report = {
        "scope": "Local point-in-time backup drill; scratch restore databases retained for inspection",
        "live_databases_unchanged": True,
        "organizations": results,
    }
    Path("docs/results/recovery-v2.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
