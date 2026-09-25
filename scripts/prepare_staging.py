"""Generate local-only credentials and isolated organization database bootstrap."""

import json
import secrets
from pathlib import Path


def main():
    out = Path("artifacts/staging-v2")
    if out.exists():
        raise ValueError(
            "Staging credentials exist; keep them or explicitly choose a new environment"
        )
    out.mkdir(parents=True)
    (out / "postgres-password").write_text(secrets.token_hex(32), encoding="utf-8")
    organizations, credentials, sql = [], [], []
    for name in ["north", "south"]:
        password = secrets.token_hex(32)
        database = f"fraudgraph_{name}"
        sql.extend(
            [
                f"CREATE ROLE {database} LOGIN PASSWORD '{password}';",
                f"CREATE DATABASE {database} OWNER {database};",
                f"REVOKE ALL ON DATABASE {database} FROM PUBLIC;",
                f"GRANT CONNECT ON DATABASE {database} TO {database};",
            ]
        )
        organizations.append(
            {
                "id": name,
                "name": f"{name.title()} Research",
                "database_url": f"postgresql+psycopg://{database}:{password}@db:5432/{database}",
                "artifact_dir": "/app/artifacts/model",
            }
        )
        for subject, role in [("alice", "analyst"), ("reviewer", "viewer")]:
            credentials.append(
                {
                    "token": secrets.token_urlsafe(36),
                    "subject": subject,
                    "organization": name,
                    "roles": [role],
                }
            )
    registry = {
        "environment": "staging",
        "organizations": organizations,
        "credentials": credentials,
    }
    (out / "organizations.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    (out / "bootstrap.sql").write_text("\n".join(sql) + "\n", encoding="utf-8")
    print("Generated local staging credentials in artifacts/staging-v2; values are not printed")


if __name__ == "__main__":
    main()
