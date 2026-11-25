"""Esquema SQLite (SQLAlchemy 2). WAL activado para lecturas concurrentes con la API."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import (
    JSON, Boolean, Column, Float, ForeignKey, Index, Integer, MetaData, String, Table, Text,
    UniqueConstraint, create_engine, event, text,
)
from sqlalchemy.engine import Engine

SCHEMA_VERSION = 4

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

# ---------------------------------------------------------------- proveedores (v2)
provider_configs = Table(
    "provider_configs", metadata,
    Column("id", String, primary_key=True),  # identificador de la instancia, p. ej. "tts_piper"
    Column("adapter", String, nullable=False),  # nombre del adaptador en el catálogo
    Column("category", String, nullable=False, index=True),
    Column("display_name", String, nullable=False),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("priority", Integer, nullable=False, default=100),  # menor = preferente; el menor activo es el principal
    Column("params", JSON, nullable=False, default=dict),
    Column("monthly_budget_eur", Float),  # None = sin límite propio (aplica el global)
    Column("max_generations_per_project", Integer),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

credentials = Table(
    "credentials", metadata,
    Column("provider_id", String, ForeignKey("provider_configs.id", ondelete="CASCADE"), primary_key=True),
    Column("key", String, primary_key=True),
    Column("ciphertext", Text, nullable=False),
    Column("hint", String, nullable=False),  # últimos 4 caracteres, para mostrar enmascarado
    Column("updated_at", String, nullable=False),
)

provider_status = Table(
    "provider_status", metadata,
    Column("provider_id", String, ForeignKey("provider_configs.id", ondelete="CASCADE"), primary_key=True),
    Column("last_check_at", String),
    Column("healthy", Boolean),
    Column("message", Text),
    Column("last_error", Text),
    Column("last_error_at", String),
    Column("error_count", Integer, nullable=False, default=0),
    Column("success_count", Integer, nullable=False, default=0),
    Column("last_used_at", String),
    Column("rate_limited_until", Float),
)

cost_ledger = Table(
    "cost_ledger", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String, index=True),
    Column("provider_id", String, nullable=False, index=True),
    Column("category", String, nullable=False),
    Column("operation", String, nullable=False),
    Column("scene_index", Integer),
    Column("estimated_eur", Float, nullable=False, default=0.0),
    Column("actual_eur", Float),
    Column("status", String, nullable=False),  # reserved | committed | failed
    Column("month", String, nullable=False, index=True),  # AAAA-MM
    Column("at", String, nullable=False),
)

# ---------------------------------------------------------------- licencias de Claude (v3)
# Cada canal tiene sus licencias (sesiones de Claude Code con su propia carpeta de configuración o claves
# de la API de Anthropic). El secreto se guarda cifrado; la API solo devuelve una pista enmascarada.
licenses = Table(
    "licenses", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("channel_id", String, nullable=False, index=True),
    Column("kind", String, nullable=False),  # claude_session | api_key
    Column("plan", String, nullable=False, default=""),  # Pro, Max 5x, Max 20x, API...
    Column("config_dir", String),  # CLAUDE_CONFIG_DIR de la sesión (claude_session)
    Column("secret_cipher", Text),  # ANTHROPIC_API_KEY cifrada (api_key)
    Column("secret_hint", String),
    Column("monthly_token_limit", Integer),  # referencia para el % de uso (None = sin referencia)
    Column("enabled", Boolean, nullable=False, default=True),
    Column("limited_until", Float),  # epoch; límite de uso alcanzado
    Column("limited_reason", Text),
    Column("is_limited", Boolean, nullable=False, default=False),
    Column("last_used_at", String),
    Column("notes", Text),
    Column("created_at", String, nullable=False),
    # v4 · límites de gasto (frenan la licencia al alcanzarlos) y el límite real observado cuando Claude la cortó
    Column("budget_5h_tokens", Integer),
    Column("budget_week_tokens", Integer),
    Column("budget_month_usd", Float),
    Column("observed_5h_tokens", Integer),
)

# Columnas añadidas a tablas que ya existían: create_all no las añade en bases antiguas.
ADDED_COLUMNS = {"licenses": [("budget_5h_tokens", "INTEGER"), ("budget_week_tokens", "INTEGER"),
                              ("budget_month_usd", "FLOAT"), ("observed_5h_tokens", "INTEGER")]}

app_settings = Table(
    "app_settings", metadata,
    Column("key", String, primary_key=True),
    Column("value", JSON),
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
        for table, cols in ADDED_COLUMNS.items():
            have = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, kind in cols:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))
        row = conn.execute(text("SELECT value FROM meta WHERE key='schema_version'")).fetchone()
        if row is None:
            conn.execute(meta.insert().values(key="schema_version", value=str(SCHEMA_VERSION)))
        elif int(row[0]) > SCHEMA_VERSION:
            raise RuntimeError(f"La base de datos es de una versión más nueva ({row[0]}) que el código ({SCHEMA_VERSION})")
        elif int(row[0]) < SCHEMA_VERSION:
            # v1 → v4: tablas nuevas (create_all) y columnas nuevas (ADDED_COLUMNS); se actualiza la versión.
            conn.execute(meta.update().where(meta.c.key == "schema_version").values(value=str(SCHEMA_VERSION)))
