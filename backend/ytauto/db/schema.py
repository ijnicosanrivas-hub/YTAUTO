"""Esquema SQLite (SQLAlchemy 2). WAL activado para lecturas concurrentes con la API."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import (
    JSON, Boolean, Column, Float, ForeignKey, Index, Integer, MetaData, String, Table, Text,
    UniqueConstraint, create_engine, event, text,
)
from sqlalchemy.engine import Engine

SCHEMA_VERSION = 1

metadata = MetaData()

projects = Table(
    "projects", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("spec", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("correction_rounds", Integer, nullable=False, default=0),
    Column("blocked_reason", Text),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

phases = Table(
    "phases", metadata,
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("phase", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("error", Text),
    Column("blocked_code", String),
    Column("retryable", Boolean, nullable=False, default=False),
    Column("summary", Text),
    Column("result", JSON),
    Column("scene_filter", JSON),
    Column("corrections", JSON),
    Column("started_at", String),
    Column("finished_at", String),
)

approvals = Table(
    "approvals", metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("gate", String, nullable=False),
    Column("approved", Boolean, nullable=False),
    Column("by", String, nullable=False),
    Column("note", Text),
    Column("at", String, nullable=False),
    Column("expires_at", String),
)

llm_usage = Table(
    "llm_usage", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String, nullable=False, index=True),
    Column("agent", String, nullable=False),
    Column("phase", String, nullable=False),
    Column("at", String, nullable=False),
    Column("data", JSON, nullable=False),
)

tasks = Table(
    "tasks", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String, nullable=False),
    Column("phase", String, nullable=False),
    Column("lane", String, nullable=False),  # claude | media | none
    Column("status", String, nullable=False),  # queued | leased | done | failed | cancelled
    Column("idempotency_key", String, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("max_attempts", Integer, nullable=False, default=3),
    Column("next_run_at", Float, nullable=False, default=0.0),
    Column("lease_owner", String),
    Column("lease_until", Float),
    Column("outcome", String),
    Column("error", Text),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    UniqueConstraint("idempotency_key", name="uq_task_idempotency"),
)
Index("ix_tasks_status_lane", tasks.c.status, tasks.c.lane, tasks.c.next_run_at)
# Como mucho UNA tarea activa (en cola o en ejecución) por proyecto y fase: evita duplicados
# aunque se llame a `schedule` varias veces o desde varios procesos.
Index("uq_tasks_active_phase", tasks.c.project_id, tasks.c.phase, unique=True,
      sqlite_where=text("status IN ('queued', 'leased')"))

queue_control = Table(
    "queue_control", metadata,
    Column("lane", String, primary_key=True),
    Column("paused", Boolean, nullable=False, default=False),
    Column("reason", Text),
    Column("resume_at", Float),  # epoch; None = reanudación manual
    Column("concurrency", Integer, nullable=False, default=1),
)

events_log = Table(
    "events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type", String, nullable=False),
    Column("project_id", String, index=True),
    Column("agent", String),
    Column("phase", String),
    Column("data", JSON),
    Column("at", String, nullable=False),
)

meta = Table(
    "meta", metadata,
    Column("key", String, primary_key=True),
    Column("value", String),
)


def make_engine(db_path: Path | str) -> Engine:
    url = "sqlite:///:memory:" if str(db_path) == ":memory:" else f"sqlite:///{Path(db_path)}"
    if url != "sqlite:///:memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return engine


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT value FROM meta WHERE key='schema_version'")).fetchone()
        if row is None:
            conn.execute(meta.insert().values(key="schema_version", value=str(SCHEMA_VERSION)))
        elif int(row[0]) > SCHEMA_VERSION:
            raise RuntimeError(f"La base de datos es de una versión más nueva ({row[0]}) que el código ({SCHEMA_VERSION})")
