"""Data Access Object for Jobs."""
from __future__ import annotations

import json

import aiosqlite

from flow_mcp.db.connection import get_db_connection
from flow_mcp.models.job import Job, JobPhase, JobSpec, JobStatus, TaskType


def _row_to_job(row: aiosqlite.Row) -> Job:
    spec = JobSpec(
        job_id=row["job_id"],
        task_type=TaskType(row["task_type"]),
        project_alias=row["project_alias"],
        params=json.loads(row["params_json"] or "{}"),
        required_assets=json.loads(row["required_assets"] or "[]"),
        cost_credits=row["cost_credits"],
        target_worker_id=row["target_worker_id"],
        parent_job_id=row["parent_job_id"],
        retry_count=row["retry_count"],
        max_retries=row["max_retries"],
        created_at=row["created_at"],
    )
    status = JobStatus(
        job_id=row["job_id"],
        phase=JobPhase(row["phase"]),
        worker_id=row["worker_id"] or "",
        progress_percent=row["progress_percent"],
        progress_text=row["progress_text"] or "",
        elapsed_seconds=row["elapsed_seconds"],
        queue_position=row["queue_position"],
        message=row["message"] or "",
        is_finished=bool(row["is_finished"]),
        result=json.loads(row["result_json"] or "{}"),
        error=row["error"] or "",
        produced_assets=json.loads(row["produced_assets"] or "[]"),
        broadcast_results=json.loads(row["broadcast_results"] or "{}"),
        updated_at=row["updated_at"],
    )
    return Job(spec=spec, status=status)


class JobDAO:
    """Async DAO for managing jobs in SQLite."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    async def insert_job(self, job: Job) -> None:
        """Insert a newly created job into the database."""
        query = """
        INSERT INTO jobs (
            job_id, task_type, project_alias, params_json, required_assets,
            cost_credits, target_worker_id, parent_job_id, retry_count, max_retries,
            phase, worker_id, progress_percent, progress_text, elapsed_seconds,
            queue_position, message, is_finished, result_json, error,
            produced_assets, broadcast_results, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        """
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                query,
                (
                    job.spec.job_id,
                    job.spec.task_type.value,
                    job.spec.project_alias,
                    json.dumps(job.spec.params, ensure_ascii=False),
                    json.dumps(job.spec.required_assets, ensure_ascii=False),
                    job.spec.cost_credits,
                    job.spec.target_worker_id,
                    job.spec.parent_job_id,
                    job.spec.retry_count,
                    job.spec.max_retries,
                    job.status.phase.value,
                    job.status.worker_id,
                    job.status.progress_percent,
                    job.status.progress_text,
                    job.status.elapsed_seconds,
                    job.status.queue_position,
                    job.status.message,
                    1 if job.status.is_finished else 0,
                    json.dumps(job.status.result, ensure_ascii=False),
                    job.status.error,
                    json.dumps(job.status.produced_assets, ensure_ascii=False),
                    json.dumps(job.status.broadcast_results, ensure_ascii=False),
                    job.spec.created_at,
                    job.status.updated_at,
                ),
            )
            await db.commit()

    async def update_status(self, status: JobStatus) -> None:
        """Update mutable status fields of a job."""
        query = """
        UPDATE jobs SET
            phase = ?,
            worker_id = ?,
            progress_percent = ?,
            progress_text = ?,
            elapsed_seconds = ?,
            queue_position = ?,
            message = ?,
            is_finished = ?,
            result_json = ?,
            error = ?,
            produced_assets = ?,
            broadcast_results = ?,
            updated_at = ?
        WHERE job_id = ?
        """
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                query,
                (
                    status.phase.value,
                    status.worker_id,
                    status.progress_percent,
                    status.progress_text,
                    status.elapsed_seconds,
                    status.queue_position,
                    status.message,
                    1 if status.is_finished else 0,
                    json.dumps(status.result, ensure_ascii=False),
                    status.error,
                    json.dumps(status.produced_assets, ensure_ascii=False),
                    json.dumps(status.broadcast_results, ensure_ascii=False),
                    status.updated_at,
                    status.job_id,
                ),
            )
            await db.commit()

    async def get_job(self, job_id: str) -> Job | None:
        """Retrieve full job by job_id."""
        query = "SELECT * FROM jobs WHERE job_id = ?"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (job_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return _row_to_job(row)

    async def get_status(self, job_id: str) -> JobStatus | None:
        """Retrieve only job status by job_id."""
        job = await self.get_job(job_id)
        return job.status if job else None

    async def list_active_jobs(self) -> list[Job]:
        """List all unfinished jobs."""
        query = "SELECT * FROM jobs WHERE is_finished = 0 ORDER BY created_at ASC"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_job(r) for r in rows]

    async def list_broadcast_children(self, parent_job_id: str) -> list[Job]:
        """List all broadcast child jobs for a given parent job."""
        query = "SELECT * FROM jobs WHERE parent_job_id = ? ORDER BY created_at ASC"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (parent_job_id,)) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_job(r) for r in rows]

    async def list_recent_jobs(self, limit: int = 100) -> list[Job]:
        """List most recent jobs."""
        query = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_job(r) for r in rows]

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job by job_id."""
        query = "DELETE FROM jobs WHERE job_id = ?"
        async with get_db_connection(self.db_path) as db:
            cursor = await db.execute(query, (job_id,))
            await db.commit()
            return cursor.rowcount > 0
