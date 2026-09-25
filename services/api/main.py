from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager

import joblib
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import String, and_, cast, func, select, text
from sqlalchemy import case as sql_case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from ml.data.dataset import digest, validate
from ml.graph.build import evidence
from services.api.config import Settings
from services.api.contracts import (
    AlertDetail,
    AlertQueue,
    AlertScore,
    Batch,
    CaseChange,
    CaseList,
    CaseRecord,
    EvidenceGraph,
)
from services.api.storage import (
    Alert,
    AuditEvent,
    Case,
    EntityAlert,
    Job,
    database,
    index_alert,
    now,
)
from services.inference.scaled import verify_assets

logger = logging.getLogger("fraudgraph")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


def record(session, actor, action, subject):
    session.add(AuditEvent(id=str(uuid.uuid4()), actor=actor, action=action, subject=subject))


def case_json(case):
    return {
        "id": case.id,
        "alert_id": case.alert_id,
        "owner": case.owner,
        "status": case.status,
        "notes": case.notes,
        "updated": case.updated.isoformat(),
        "revision": case.revision,
    }


def stamp_provenance(payload, manifest):
    return {
        **payload,
        "graph_manifest": manifest["graph_schema"],
        "feature_manifest": manifest["version"],
        "dataset_sha256": manifest["dataset_sha256"],
        "calibration_method": "Platt scaling",
        "schema_version": "1",
        "latency_ms": payload.get("latency_ms") or None,
        "latency_scope": "amortized batch scoring per new event"
        if payload.get("latency_ms")
        else "not measured for seeded offline queue",
    }


def create_app(settings=None):
    settings = settings or Settings()
    settings.validate_deployment()

    @asynccontextmanager
    async def lifespan(app):
        settings.artifact_dir.parent.mkdir(parents=True, exist_ok=True)
        engine, sessions = database(settings.database_url)
        app.state.sessions = sessions
        app.state.manifest = None
        path = settings.artifact_dir
        if (path / "manifest.json").exists() and (path / "scores.json").exists():
            manifest = json.loads((path / "manifest.json").read_text())
            df = validate(pd.read_csv(path / "events.csv"))
            freeze = json.loads((path / "freeze.json").read_text())
            if digest(df) != manifest["dataset_sha256"]:
                raise ValueError("Dataset integrity check failed")
            if (
                hashlib.sha256((path / "bundle.joblib").read_bytes()).hexdigest()
                != freeze["bundle_sha256"]
            ):
                raise ValueError("Model integrity check failed")
            bundle = joblib.load(path / "bundle.joblib")
            if bundle["manifest"]["version"] != manifest["version"]:
                raise ValueError("Model version mismatch")
            app.state.bundle = bundle
            graphs = {}
            if bundle.get("format") == "scaled-v2":
                verify_assets(path)
                graphs = json.loads((path / "graphs.json").read_text())
            scores = json.loads((path / "scores.json").read_text())
            with sessions.begin() as session:
                for payload in scores:
                    payload = stamp_provenance(payload, manifest)
                    AlertScore.model_validate(payload)
                    existing = session.get(Alert, payload["id"])
                    if existing is None:
                        graph_payload = (
                            graphs[payload["id"]]
                            if bundle.get("format") == "scaled-v2"
                            else evidence(df, payload["id"])
                        )
                        session.add(
                            Alert(
                                id=payload["id"],
                                payload=payload,
                                graph=graph_payload,
                            )
                        )
                        index_alert(session, payload["id"], graph_payload)
                    elif existing.payload["model_version"] == manifest["version"]:
                        existing.payload = stamp_provenance(existing.payload, manifest)
                record(session, "system", "model_loaded", manifest["version"])
            app.state.manifest = manifest
            del df, scores, graphs
        yield
        engine.dispose()

    app = FastAPI(title="FraudGraph", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.request_metrics = {"requests": 0, "errors": 0, "recent_latency_ms": []}

    @app.exception_handler(StaleDataError)
    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse(
            {"detail": "This record changed concurrently. Refresh and retry."}, status_code=409
        )

    def analyst(request: Request, authorization: str | None = Header(default=None)):
        if settings.require_gateway:
            principal = getattr(request.state, "principal", None)
            if principal is None or principal["organization"] != settings.organization_id:
                raise HTTPException(401, "Organization authentication required")
            return principal["subject"]
        token = authorization.removeprefix("Bearer ") if authorization else ""
        if not token:
            raise HTTPException(401, "Bearer token required")
        for name, expected in {"analyst": settings.api_token, **settings.analyst_tokens}.items():
            if secrets.compare_digest(token, expected):
                return name
        raise HTTPException(401, "Invalid credentials")

    @app.middleware("http")
    async def telemetry(request: Request, call_next):
        start, request_id = time.perf_counter(), str(uuid.uuid4())
        response = await call_next(request)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        counters = app.state.request_metrics
        counters["requests"] += 1
        counters["errors"] += int(response.status_code >= 500)
        counters["recent_latency_ms"] = [*counters["recent_latency_ms"][-999:], elapsed]
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "status": response.status_code,
                    "latency_ms": elapsed,
                    "model_version": (getattr(app.state, "manifest", None) or {}).get("version"),
                }
            )
        )
        return response

    @app.get("/health")
    def health():
        return {"status": "alive", "schema_version": "1"}

    @app.get("/ready")
    def ready():
        with app.state.sessions() as session:
            session.execute(text("SELECT 1"))
        if app.state.manifest is None:
            raise HTTPException(503, "No scored model artifacts; run the training pipeline")
        return {"status": "ready", "version": app.state.manifest["version"]}

    @app.get("/v1/model")
    def model(actor=Depends(analyst)):
        if app.state.manifest is None:
            raise HTTPException(503, "Model unavailable")
        return app.state.manifest

    @app.get("/v1/session")
    def session_identity(actor=Depends(analyst)):
        return {
            "subject": actor,
            "organization": settings.organization_id,
            "organization_name": "Local workspace",
            "roles": ["analyst"],
        }

    @app.get("/v1/metrics")
    def operational_metrics(actor=Depends(analyst)):
        with app.state.sessions() as session:
            alerts_count = session.scalar(select(func.count()).select_from(Alert))
            queued = session.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.owner == actor, Job.status == "queued")
            )
            failed = session.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.owner == actor, Job.status == "failed")
            )
        counters = app.state.request_metrics
        latencies = sorted(counters["recent_latency_ms"])
        return {
            "schema_version": "1",
            "alerts": alerts_count,
            "your_queued_jobs": queued,
            "your_failed_jobs": failed,
            "process_requests": counters["requests"],
            "process_5xx": counters["errors"],
            "recent_p95_ms": latencies[int((len(latencies) - 1) * 0.95)] if latencies else None,
            "latency_samples": len(latencies),
            "scope": "current API process, latest 1000 responses",
        }

    @app.get("/v1/alerts", response_model=AlertQueue)
    def alerts(
        min_score: float = Query(0, ge=0, le=1),
        min_amount: float = Query(0, ge=0),
        after: float | None = None,
        before: float | None = None,
        entity_type: str | None = Query(None, pattern="^(account|card|device|address|merchant)$"),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        actor=Depends(analyst),
    ):
        score = Alert.payload["score"].as_float()
        amount = Alert.payload["amount"].as_float()
        event_time = Alert.payload["time"].as_float()
        conditions = [score >= min_score, amount >= min_amount]
        if after is not None:
            conditions.append(event_time >= after)
        if before is not None:
            conditions.append(event_time <= before)
        if entity_type is not None:
            conditions.append(
                cast(Alert.payload["entity_types"], String).contains(f'"{entity_type}"')
            )
        join = and_(Case.alert_id == Alert.id, Case.owner == actor)
        with app.state.sessions() as session:
            rows = session.execute(
                select(Alert.payload, Case.status)
                .outerjoin(Case, join)
                .where(*conditions)
                .order_by(score.desc(), Alert.id)
                .offset(offset)
                .limit(limit)
            )
            items = [dict(payload, status=status or "open") for payload, status in rows]
            total, opened, high, value = session.execute(
                select(
                    func.count(Alert.id),
                    func.sum(sql_case((Case.id.is_(None), 1), else_=0)),
                    func.sum(sql_case((score >= 0.5, 1), else_=0)),
                    func.sum(sql_case((score >= 0.5, amount), else_=0)),
                )
                .select_from(Alert)
                .outerjoin(Case, join)
                .where(*conditions)
            ).one()
        return {
            "schema_version": "1",
            "total": total,
            "items": items,
            "summary": {
                "open": opened or 0,
                "flagged_value": value or 0,
                "high_risk": high or 0,
            },
        }

    def get_alert(session, alert_id):
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(404, "Alert not found")
        return alert

    @app.get("/v1/alerts/{alert_id}", response_model=AlertDetail)
    def detail(alert_id: str, actor=Depends(analyst)):
        with app.state.sessions() as session:
            alert = get_alert(session, alert_id)
            case = session.scalar(
                select(Case).where(Case.alert_id == alert_id, Case.owner == actor)
            )
            return {
                **alert.payload,
                "case": case_json(case) if case else None,
                "notice": "Scores and shared identifiers support investigation; they do not prove fraud.",
            }

    @app.get("/v1/alerts/{alert_id}/graph", response_model=EvidenceGraph)
    def graph(alert_id: str, actor=Depends(analyst)):
        with app.state.sessions() as session:
            return get_alert(session, alert_id).graph

    @app.post("/v1/alerts/{alert_id}/case", response_model=CaseRecord)
    def change_case(alert_id: str, change: CaseChange, actor=Depends(analyst)):
        with app.state.sessions.begin() as session:
            get_alert(session, alert_id)
            case = session.scalar(
                select(Case).where(Case.alert_id == alert_id, Case.owner == actor).with_for_update()
            )
            if case is None:
                case = Case(
                    id=str(uuid.uuid4()),
                    alert_id=alert_id,
                    owner=actor,
                    status=change.status,
                    notes=[],
                    updated=now(),
                )
                session.add(case)
            case.status, case.updated = change.status, now()
            case.notes = [
                *case.notes,
                {"text": change.note, "actor": actor, "time": now().isoformat()},
            ]
            record(session, actor, "case_updated", case.id)
            session.flush()
            return case_json(case)

    @app.get("/v1/cases", response_model=CaseList)
    def cases(actor=Depends(analyst)):
        with app.state.sessions() as session:
            return {
                "items": [
                    case_json(c) for c in session.scalars(select(Case).where(Case.owner == actor))
                ]
            }

    @app.get("/v1/cases/{case_id}/export")
    def export(case_id: str, actor=Depends(analyst)):
        with app.state.sessions.begin() as session:
            case = session.get(Case, case_id)
            if case is None or case.owner != actor:
                raise HTTPException(404, "Case not found")
            alert = get_alert(session, case.alert_id)
            record(session, actor, "case_exported", case_id)
            return JSONResponse(
                {
                    "schema_version": "1",
                    "case": case_json(case),
                    "alert": alert.payload,
                    "evidence": alert.graph,
                    "notice": "Investigation aid, not proof of fraud.",
                },
                headers={"Content-Disposition": f'attachment; filename="case-{case_id}.json"'},
            )

    @app.get("/v1/audit")
    def audit(actor=Depends(analyst)):
        with app.state.sessions() as session:
            rows = session.scalars(
                select(AuditEvent)
                .where(AuditEvent.actor == actor)
                .order_by(AuditEvent.created.desc())
                .limit(100)
            )
            return {
                "items": [
                    {"action": r.action, "subject": r.subject, "time": r.created.isoformat()}
                    for r in rows
                ]
            }

    @app.get("/v1/entities/{entity_id}")
    def entity(
        entity_id: str,
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0),
        actor=Depends(analyst),
    ):
        with app.state.sessions() as session:
            query = (
                select(Alert.payload)
                .join(EntityAlert, EntityAlert.alert_id == Alert.id)
                .where(EntityAlert.entity_id == entity_id)
            )
            related = list(
                session.scalars(
                    query.order_by(Alert.payload["score"].as_float().desc(), Alert.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            total, maximum = session.execute(
                select(func.count(), func.max(Alert.payload["score"].as_float()))
                .select_from(Alert)
                .join(EntityAlert, EntityAlert.alert_id == Alert.id)
                .where(EntityAlert.entity_id == entity_id)
            ).one()
        if not total:
            raise HTTPException(404, "Entity not found")
        return {
            "id": entity_id,
            "max_associated_risk": maximum,
            "alerts": related,
            "total": total,
            "offset": offset,
            "limit": limit,
            "notice": "Association summary, not an independent entity probability",
        }

    @app.post("/v1/jobs", status_code=202)
    def submit(batch: Batch, actor=Depends(analyst)):
        if app.state.manifest is None:
            raise HTTPException(503, "Model unavailable")
        ids = [e.id for e in batch.events]
        if len(ids) != len(set(ids)):
            raise HTTPException(422, "Duplicate event IDs")
        payload = {
            "events": [e.model_dump() for e in batch.events],
            "version": app.state.manifest["version"],
        }
        job_id = hashlib.sha256(json.dumps([actor, payload], sort_keys=True).encode()).hexdigest()
        try:
            with app.state.sessions.begin() as session:
                if session.bind.dialect.name == "postgresql":
                    session.execute(text("SELECT pg_advisory_xact_lock(7349251)"))
                elif session.bind.dialect.name == "sqlite":
                    session.execute(text("BEGIN IMMEDIATE"))
                existing = session.get(Job, job_id)
                if existing:
                    return {"id": job_id, "status": existing.status}
                total, stored = session.execute(
                    select(
                        func.count(Job.id),
                        func.coalesce(func.sum(func.length(cast(Job.payload, String))), 0),
                    )
                ).one()
                pending = session.scalar(
                    select(func.count()).select_from(Job).where(Job.status == "queued")
                )
                owned = session.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(Job.status == "queued", Job.owner == actor)
                )
                size = len(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
                if (
                    pending >= settings.max_pending_jobs
                    or owned >= settings.max_owner_pending_jobs
                    or total >= settings.max_retained_jobs
                    or stored + size > settings.max_job_payload_bytes
                ):
                    raise HTTPException(
                        429,
                        "Scoring capacity reached; wait for pending jobs or ask the operator to archive retained jobs",
                        headers={"Retry-After": "60"},
                    )
                session.add(
                    Job(id=job_id, owner=actor, payload=payload, status="queued", result={})
                )
                record(session, actor, "batch_submitted", job_id)
        except IntegrityError:
            with app.state.sessions() as session:
                return {"id": job_id, "status": session.get(Job, job_id).status}
        return {"id": job_id, "status": "queued"}

    @app.get("/v1/jobs/{job_id}")
    def job(job_id: str, actor=Depends(analyst)):
        with app.state.sessions() as session:
            row = session.get(Job, job_id)
            if row is None or row.owner != actor:
                raise HTTPException(404, "Job not found")
            return {"id": row.id, "status": row.status, "result": row.result}

    return app


app = create_app()
