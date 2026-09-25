"""Real PostgreSQL integration; enabled by CI's dedicated test database."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from services.api.config import Settings
from services.api.main import create_app
from services.api.storage import AuditEvent
from services.inference.worker import run_one


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not configured"
)
def test_postgres_case_and_durable_job(artifacts):
    url = make_url(os.environ["TEST_POSTGRES_URL"])
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("Use a dedicated database whose name ends in _test")
    schema = "fg_test_" + uuid.uuid4().hex
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    test_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    try:
        settings = Settings(
            database_url=test_url.render_as_string(hide_password=False),
            artifact_dir=artifacts,
            api_token="test-token",
        )
        app = create_app(settings)
        with TestClient(app) as client:
            client.headers["Authorization"] = "Bearer test-token"
            assert client.get("/ready").status_code == 200
            aid = client.get("/v1/alerts").json()["items"][0]["id"]
            case = client.post(f"/v1/alerts/{aid}/case", json={"note": "PostgreSQL integration"})
            assert case.status_code == 200
            assert client.get(f"/v1/cases/{case.json()['id']}/export").status_code == 200
            job = client.post(
                "/v1/jobs", json={"events": [{"id": "PG-1", "time": 999999, "amount": 100}]}
            ).json()
            assert run_one(settings, app.state.sessions)
            assert client.get(f"/v1/jobs/{job['id']}").json()["status"] == "completed"
            from concurrent.futures import ThreadPoolExecutor

            settings.max_pending_jobs = 1

            def submit(index):
                return client.post(
                    "/v1/jobs",
                    json={"events": [{"id": f"PG-quota-{index}", "time": 999999, "amount": 100}]},
                ).status_code

            with ThreadPoolExecutor(max_workers=4) as pool:
                assert sorted(pool.map(submit, range(4))) == [202, 429, 429, 429]
            with app.state.sessions() as session:
                assert session.scalar(
                    select(AuditEvent).where(AuditEvent.action == "batch_completed")
                )
    finally:
        # Only the generated, isolated test schema is removed; never the database.
        assert schema.startswith("fg_test_") and len(schema) == 40
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        engine.dispose()
