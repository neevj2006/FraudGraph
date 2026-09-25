import json

import pytest
from fastapi.testclient import TestClient

from ml.pipeline import final_evaluate
from services.api.config import Settings
from services.api.main import create_app
from services.api.storage import Case, now
from services.inference.worker import run_one


def test_entity_pagination_and_index(client):
    from sqlalchemy import event

    aid = client.get("/v1/alerts").json()["items"][0]["id"]
    node = client.get(f"/v1/alerts/{aid}/graph").json()["nodes"][0]["id"]
    statements = []
    engine = client.app.state.sessions.kw["bind"]

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = client.get(f"/v1/entities/{node}", params={"limit": 1}).json()
        assert len(result["alerts"]) == 1
        assert result["total"] >= 1
        assert (
            client.get(f"/v1/entities/{node}", params={"offset": result["total"]}).json()["alerts"]
            == []
        )
        assert client.get("/v1/entities/missing").status_code == 404
        assert all("alerts.graph" not in statement for statement in statements)
        assert any("entity_alerts" in statement for statement in statements)
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_job_quotas_and_retry(client):
    settings = client.app.state.settings
    settings.max_owner_pending_jobs = 1
    first = {"events": [{"id": "quota-1", "time": 999999, "amount": 10}]}
    second = {"events": [{"id": "quota-2", "time": 999999, "amount": 10}]}
    assert client.post("/v1/jobs", json=first).status_code == 202
    assert client.post("/v1/jobs", json=first).status_code == 202
    assert client.post("/v1/jobs", json=second).status_code == 429
    assert run_one(settings, client.app.state.sessions)
    assert client.post("/v1/jobs", json=second).status_code == 202
    settings.max_retained_jobs = 2
    third = {"events": [{"id": "quota-3", "time": 999999, "amount": 10}]}
    assert (
        client.post(
            "/v1/jobs", json=third, headers={"Authorization": "Bearer other-secret"}
        ).status_code
        == 429
    )


def test_concurrent_job_admission(client):
    from concurrent.futures import ThreadPoolExecutor

    client.app.state.settings.max_pending_jobs = 1

    def submit(index):
        return client.post(
            "/v1/jobs",
            json={"events": [{"id": f"concurrent-{index}", "time": 999999, "amount": 10}]},
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(submit, range(4)))
    assert sorted(statuses) == [202, 429, 429, 429]


def test_entity_index_migration(artifacts, tmp_path):
    from sqlalchemy import text

    from services.api.storage import EntityAlert, database

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'migration.db'}", artifact_dir=artifacts
    )
    with TestClient(create_app(settings)) as app:
        before = app.get(
            "/v1/alerts", headers={"Authorization": "Bearer local-demo-token-change-me"}
        ).json()["total"]
    engine, _ = database(settings.database_url)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE entity_alerts"))
    engine.dispose()
    engine, sessions = database(settings.database_url)
    from sqlalchemy import func, select

    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(EntityAlert)) >= before
    engine.dispose()


@pytest.fixture
def client(artifacts, tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        artifact_dir=artifacts,
        api_token="test-secret",
        analyst_tokens={"other": "other-secret"},
    )
    app = create_app(settings)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test-secret"
        yield client


def test_full_investigation_and_auth(client):
    assert client.get("/ready").status_code == 200
    assert client.get("/health").json()["status"] == "alive"
    assert client.get("/v1/alerts", headers={"Authorization": ""}).status_code == 401
    queue = client.get("/v1/alerts").json()
    scores = [r["score"] for r in queue["items"]]
    assert scores == sorted(scores, reverse=True)
    aid = queue["items"][0]["id"]
    detail = client.get(f"/v1/alerts/{aid}").json()
    assert detail["graph_manifest"] == "temporal-entity-snapshots-v2"
    assert detail["dataset_sha256"]
    graph = client.get(f"/v1/alerts/{aid}/graph").json()
    assert all(e["time"] <= detail["cutoff"] for e in graph["edges"])
    changed = client.post(
        f"/v1/alerts/{aid}/case",
        json={"status": "investigating", "note": "Shared device needs context."},
    )
    assert changed.status_code == 200
    case_id = changed.json()["id"]
    assert (
        client.get(f"/v1/cases/{case_id}/export").json()["case"]["notes"][0]["text"]
        == "Shared device needs context."
    )
    assert (
        client.get(
            f"/v1/cases/{case_id}/export", headers={"Authorization": "Bearer other-secret"}
        ).status_code
        == 404
    )
    assert (
        client.get("/v1/cases", headers={"Authorization": "Bearer other-secret"}).json()["items"]
        == []
    )
    assert len(client.get("/v1/audit").json()["items"]) == 2
    assert (
        client.post(f"/v1/alerts/{aid}/case", json={"status": "blocked", "note": "x"}).status_code
        == 422
    )
    assert client.get("/v1/alerts/absent").status_code == 404
    assert client.post(f"/v1/alerts/{aid}/case", json={"note": "   "}).status_code == 422


def test_filters_and_pagination(client):
    response = client.get(
        "/v1/alerts?min_score=.5&min_amount=100&entity_type=device&limit=3"
    ).json()
    assert len(response["items"]) <= 3
    assert all(
        r["score"] >= 0.5 and r["amount"] >= 100 and "device" in r["entity_types"]
        for r in response["items"]
    )
    assert client.get("/v1/alerts?min_score=2").status_code == 422
    telemetry = client.get("/v1/metrics").json()
    assert telemetry["alerts"] > 0 and telemetry["process_requests"] >= 2
    empty = client.get("/v1/alerts?min_amount=1000000000000").json()
    assert empty["total"] == 0 and empty["summary"]["flagged_value"] == 0
    page = client.get("/v1/alerts?limit=2&offset=2").json()
    all_rows = client.get("/v1/alerts?limit=4").json()
    assert [r["id"] for r in page["items"]] == [r["id"] for r in all_rows["items"]][2:]


def test_durable_idempotent_scoring(client):
    batch = {
        "events": [
            {"id": "NEW-1", "time": 999999, "amount": 89, "account": "new", "device": "shared-1"}
        ]
    }
    first = client.post("/v1/jobs", json=batch)
    assert first.status_code == 202
    job_id = first.json()["id"]
    assert client.post("/v1/jobs", json=batch).json()["id"] == job_id
    assert (
        client.get(
            f"/v1/jobs/{job_id}", headers={"Authorization": "Bearer other-secret"}
        ).status_code
        == 404
    )
    assert run_one(client.app.state.settings, client.app.state.sessions)
    result = client.get(f"/v1/jobs/{job_id}").json()
    assert result["status"] == "completed", result
    assert client.get("/v1/alerts/NEW-1").status_code == 200
    assert not run_one(client.app.state.settings, client.app.state.sessions)
    assert client.post("/v1/jobs", json=batch).json()["status"] == "completed"
    bad = {"events": [dict(batch["events"][0], id="OLD-1", time=1)]}
    bad_id = client.post("/v1/jobs", json=bad).json()["id"]
    run_one(client.app.state.settings, client.app.state.sessions)
    assert client.get(f"/v1/jobs/{bad_id}").json()["status"] == "failed"
    assert client.get("/v1/alerts/OLD-1").status_code == 404


def test_label_injection_rejected(client):
    event = {"id": "x", "time": 999999, "amount": 1, "label": 1}
    assert client.post("/v1/jobs", json={"events": [event]}).status_code == 422


def test_sealed_final_evaluation(artifacts):
    result = final_evaluate(artifacts)
    assert result["metrics"]["calibrated"]["n"] == 180
    with pytest.raises(ValueError, match="already exists"):
        final_evaluate(artifacts)
    assert json.loads((artifacts / "freeze.json").read_text())["version"] == result["version"]


def test_missing_model_is_not_ready(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}", artifact_dir=tmp_path / "absent"
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503


def test_concurrent_assessments_do_not_lose_notes(client):
    from sqlalchemy.orm.exc import StaleDataError

    aid = client.get("/v1/alerts").json()["items"][0]["id"]
    case = client.post(f"/v1/alerts/{aid}/case", json={"note": "Original"}).json()
    sessions = client.app.state.sessions
    with sessions() as one, sessions() as two:
        first, second = one.get(Case, case["id"]), two.get(Case, case["id"])
        first.notes = [*first.notes, {"text": "First writer"}]
        first.updated = now()
        one.commit()
        second.notes = [*second.notes, {"text": "Stale writer"}]
        second.updated = now()
        with pytest.raises(StaleDataError):
            two.commit()
