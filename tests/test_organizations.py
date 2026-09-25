import json

import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.storage import Alert, database, index_alert
from services.gateway import create_gateway
from services.inference.worker import run_one
from services.organizations import Registry

NORTH = "north-" + "a" * 40
SOUTH = "south-" + "b" * 40
VIEWER = "viewer-" + "c" * 40


def registry_for(artifacts, tmp_path, **overrides):
    return Registry.model_validate(
        {
            "organizations": [
                {
                    "id": org,
                    "name": org.title(),
                    "database_url": f"sqlite:///{tmp_path / (org + '.db')}",
                    "artifact_dir": str(artifacts),
                }
                for org in ["north", "south"]
            ],
            "credentials": [
                {"token": NORTH, "subject": "alice", "organization": "north", "roles": ["analyst"]},
                {"token": SOUTH, "subject": "alice", "organization": "south", "roles": ["analyst"]},
                {
                    "token": VIEWER,
                    "subject": "viewer",
                    "organization": "north",
                    "roles": ["viewer"],
                },
            ],
            **overrides,
        }
    )


def test_organization_boundaries_all_resource_paths(artifacts, tmp_path):
    registry = registry_for(artifacts, tmp_path)
    app = create_gateway(registry)
    with TestClient(app) as client:
        north = {"Authorization": f"Bearer {NORTH}"}
        south = {"Authorization": f"Bearer {SOUTH}", "X-Organization": "north"}
        assert client.get("/ready").status_code == 200
        assert client.get("/v1/alerts").status_code == 401
        assert client.get("/v1/session", headers=south).json()["organization"] == "south"
        first = client.get("/v1/alerts", headers=north).json()["items"][0]
        aid = first["id"]
        case = client.post(
            f"/v1/alerts/{aid}/case", headers=north, json={"note": "North private note"}
        ).json()
        assert client.get("/v1/cases", headers=south).json()["items"] == []
        assert client.get(f"/v1/cases/{case['id']}/export", headers=south).status_code == 404
        assert client.get(f"/v1/alerts/{aid}", headers=south).json()["case"] is None
        assert client.get("/v1/audit", headers=south).json()["items"] == []
        sessions = app.state.organizations["north"].state.sessions
        with sessions.begin() as session:
            index_alert(session, "NORTHONLY", {"nodes": [{"id": "device:north-only"}]})
            session.add(
                Alert(
                    id="NORTHONLY",
                    payload={**first, "id": "NORTHONLY"},
                    graph={"nodes": [{"id": "device:north-only"}]},
                )
            )
        assert client.get("/v1/alerts/NORTHONLY", headers=south).status_code == 404
        assert client.get("/v1/alerts/NORTHONLY/graph", headers=south).status_code == 404
        assert client.get("/v1/entities/device:north-only", headers=south).status_code == 404
        assert client.get("/v1/entities/device:north-only", headers=north).status_code == 200
        nc = client.get("/v1/metrics", headers=north).json()["alerts"]
        sc = client.get("/v1/metrics", headers=south).json()["alerts"]
        assert nc == sc + 1
        assert client.get("/v1/alerts", headers=north).json()["total"] == nc
        assert client.get("/v1/alerts", headers=south).json()["total"] == sc
        batch = {"events": [{"id": "SAME-BATCH-ID", "time": 999999, "amount": 12}]}
        nj = client.post("/v1/jobs", headers=north, json=batch).json()["id"]
        assert client.get(f"/v1/jobs/{nj}", headers=south).status_code == 404
        sj = client.post("/v1/jobs", headers=south, json=batch).json()["id"]
        # Hashes may be identical because stores are physically independent.
        for organization in registry.organizations:
            settings = registry.settings_for(organization)
            engine, store = database(settings.database_url)
            try:
                assert run_one(settings, store)
            finally:
                engine.dispose()
        assert client.get(f"/v1/jobs/{nj}", headers=north).json()["status"] == "completed"
        assert client.get(f"/v1/jobs/{sj}", headers=south).json()["status"] == "completed"
        assert client.get("/v1/alerts/SAME-BATCH-ID", headers=south).status_code == 200
        assert "North private note" not in json.dumps(client.get("/v1/audit", headers=south).json())


def test_roles_limits_and_direct_gateway_bypass(artifacts, tmp_path):
    registry = registry_for(artifacts, tmp_path, request_limit=5, body_limit=1024)
    with TestClient(create_gateway(registry)) as client:
        viewer = {"Authorization": f"Bearer {VIEWER}"}
        assert client.get("/v1/alerts", headers=viewer).status_code == 200
        assert client.post("/v1/jobs", headers=viewer, json={}).status_code == 403
        assert client.get("/v1/cases/unknown/export", headers=viewer).status_code == 403
        north = {"Authorization": f"Bearer {NORTH}"}
        assert client.post("/v1/jobs", headers=north, content=b"x" * 2048).status_code == 413
        for _ in range(4):
            assert client.get("/v1/session", headers=north).status_code == 200
        assert client.get("/v1/session", headers=north).status_code == 429
    with TestClient(create_app(registry.settings_for(registry.organizations[0]))) as direct:
        assert (
            direct.get("/v1/alerts", headers={"Authorization": f"Bearer {NORTH}"}).status_code
            == 401
        )


def test_registry_rejects_shared_database_and_credentials(artifacts, tmp_path):
    registry = registry_for(artifacts, tmp_path).model_dump()
    registry["organizations"][1]["database_url"] = registry["organizations"][0]["database_url"]
    with pytest.raises(ValueError, match="separate databases"):
        Registry.model_validate(registry)
