from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, String, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.schema import CreateIndex


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    graph: Mapped[dict] = mapped_column(JSON)


class EntityAlert(Base):
    __tablename__ = "entity_alerts"
    entity_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(128), primary_key=True)


def index_alert(session, alert_id, graph):
    session.add_all(
        EntityAlert(entity_id=value, alert_id=alert_id)
        for value in {node["id"] for node in graph["nodes"]}
    )


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (Index("uq_case_alert_owner", "alert_id", "owner", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(128), index=True)
    owner: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32))
    notes: Mapped[list] = mapped_column(JSON)
    updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


Index("ix_alerts_score", Alert.payload["score"].as_float(), Alert.id)
Index("ix_alerts_time", Alert.payload["time"].as_float())
Index("ix_alerts_amount", Alert.payload["amount"].as_float())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(128))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def database(url):
    engine = create_engine(
        url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
    )
    # The additive index migration is transactional and restartable.
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        elif engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(7349252)"))
        needs_entity_index = not inspect(connection).has_table("entity_alerts")
        Base.metadata.create_all(connection)
        if needs_entity_index:
            rows = connection.execute(
                select(Alert.id, Alert.graph).execution_options(yield_per=100)
            )
            for alert_id, graph in rows:
                values = [
                    {"entity_id": n, "alert_id": alert_id}
                    for n in {node["id"] for node in graph["nodes"]}
                ]
                if values:
                    connection.execute(EntityAlert.__table__.insert(), values)
    if "revision" not in {column["name"] for column in inspect(engine).get_columns("cases")}:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE cases ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"
            )
    # Idempotent first-release migration for local databases created before the index.
    with engine.begin() as connection:
        for model in (Case, Alert):
            for index in model.__table__.indexes:
                connection.execute(CreateIndex(index, if_not_exists=True))
    return engine, sessionmaker(engine, expire_on_commit=False)
