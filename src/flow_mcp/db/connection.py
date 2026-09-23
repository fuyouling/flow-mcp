"""Database connection and schema initialization."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
import aiosqlite
from loguru import logger

from flow_mcp.config import get_settings

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    job_id              TEXT PRIMARY KEY,
    task_type           TEXT NOT NULL,
    project_alias       TEXT NOT NULL DEFAULT '',
    params_json         TEXT NOT NULL DEFAULT '{}',
    required_assets     TEXT NOT NULL DEFAULT '[]',
    cost_credits        INTEGER NOT NULL DEFAULT 0,
    target_worker_id    TEXT,
    parent_job_id       TEXT,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    max_retries         INTEGER NOT NULL DEFAULT 2,
    phase               TEXT NOT NULL DEFAULT 'pending',
    worker_id           TEXT NOT NULL DEFAULT '',
    progress_percent    INTEGER NOT NULL DEFAULT 0,
    progress_text       TEXT NOT NULL DEFAULT '',
    elapsed_seconds     REAL NOT NULL DEFAULT 0.0,
    queue_position      INTEGER NOT NULL DEFAULT 0,
    message             TEXT NOT NULL DEFAULT '',
    is_finished         INTEGER NOT NULL DEFAULT 0,
    result_json         TEXT NOT NULL DEFAULT '{}',
    error               TEXT NOT NULL DEFAULT '',
    produced_assets     TEXT NOT NULL DEFAULT '[]',
    broadcast_results   TEXT NOT NULL DEFAULT '{}',
    created_at          REAL NOT NULL,
    updated_at          REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_phase ON jobs(phase);
CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_job_id);

-- Accounts table
CREATE TABLE IF NOT EXISTS accounts (
    email                   TEXT PRIMARY KEY,
    worker_id               TEXT NOT NULL DEFAULT '',
    balance                 INTEGER,
    daily_free_remaining    INTEGER NOT NULL DEFAULT 50,
    daily_cycle_date        TEXT NOT NULL DEFAULT '',
    updated_at              TEXT NOT NULL DEFAULT ''
);

-- Credit reservations table
CREATE TABLE IF NOT EXISTS credit_reservations (
    reservation_id   TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL,
    account          TEXT NOT NULL,
    reserved_free    INTEGER NOT NULL DEFAULT 0,
    reserved_balance INTEGER NOT NULL DEFAULT 0,
    state            TEXT NOT NULL DEFAULT 'pending',
    created_at       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_res_job ON credit_reservations(job_id);
CREATE INDEX IF NOT EXISTS idx_res_state ON credit_reservations(state);

-- Project alias mapping table
CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_alias TEXT NOT NULL,
    worker_id     TEXT NOT NULL,
    local_uuid    TEXT NOT NULL,
    flow_url      TEXT NOT NULL DEFAULT '',
    last_accessed TEXT NOT NULL DEFAULT '',
    UNIQUE(project_alias, worker_id)
);
CREATE INDEX IF NOT EXISTS idx_proj_alias ON projects(project_alias);

-- Assets registry table
CREATE TABLE IF NOT EXISTS assets (
    name              TEXT PRIMARY KEY,
    kind              TEXT NOT NULL,
    file_name         TEXT NOT NULL,
    file_path         TEXT NOT NULL,
    file_size         INTEGER NOT NULL DEFAULT 0,
    sha256            TEXT NOT NULL DEFAULT '',
    created_by_worker TEXT NOT NULL DEFAULT '',
    source_job_id     TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);
"""


@asynccontextmanager
async def get_db_connection(db_path: str | None = None) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an aiosqlite connection with WAL mode and row_factory."""
    if db_path is None:
        db_path = get_settings().db_path
    
    path_obj = Path(db_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(path_obj)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        yield db


async def init_db(db_path: str | None = None) -> None:
    """Initialize database schemas and tables."""
    if db_path is None:
        db_path = get_settings().db_path
    logger.info(f"Initializing database schema at {db_path}")
    async with get_db_connection(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    logger.info("Database schema initialized successfully")
