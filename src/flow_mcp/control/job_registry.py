"""JobRegistry: Single Source of Truth (SSOT) for Job lifecycle and state."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from loguru import logger

from flow_mcp.db.job_dao import JobDAO
from flow_mcp.models.job import (
    Job,
    JobPhase,
    JobSpec,
    JobStatus,
    FINISHED_PHASES,
)
from flow_mcp.utils.errors import ResourceNotFoundError


class JobRegistry:
    """
    Job Registry combines in-memory cache for fast progress queries with SQLite WAL persistence.
    """

    def __init__(self, job_dao: JobDAO | None = None):
        self.dao = job_dao or JobDAO()
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Load unfinished active jobs from SQLite into memory cache on startup."""
        active = await self.dao.list_active_jobs()
        async with self._lock:
            for job in active:
                self._jobs[job.job_id] = job
        logger.info(f"JobRegistry initialized with {len(active)} active jobs from database.")

    async def register_job(self, spec: JobSpec) -> Job:
        """Register a new job."""
        job = Job.create(spec)
        async with self._lock:
            self._jobs[job.job_id] = job

        await self.dao.insert_job(job)
        logger.info(f"Registered job {job.job_id} ({spec.task_type.value}) for project {spec.project_alias}")
        return job

    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID (memory cache -> DB fallback)."""
        async with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]

        db_job = await self.dao.get_job(job_id)
        if db_job:
            async with self._lock:
                self._jobs[job_id] = db_job
        return db_job

    async def get_status(self, job_id: str) -> JobStatus | None:
        """Get job status."""
        job = await self.get_job(job_id)
        return job.status if job else None

    async def update_status(self, job_id: str, **kwargs: Any) -> JobStatus:
        """Update mutable status fields of a job and persist to DB."""
        job = await self.get_job(job_id)
        if not job:
            raise ResourceNotFoundError(f"Job {job_id} not found in registry.")

        async with self._lock:
            status = job.status
            for key, val in kwargs.items():
                if hasattr(status, key):
                    setattr(status, key, val)

            # Auto-compute is_finished if phase transitioned
            if status.phase in FINISHED_PHASES:
                status.is_finished = True

            status.updated_at = time.time()

        await self.dao.update_status(status)
        return status

    async def mark_completed(
        self,
        job_id: str,
        result: dict[str, Any] | None = None,
        produced_assets: list[dict[str, Any]] | None = None,
    ) -> JobStatus:
        """Transition job to COMPLETED."""
        return await self.update_status(
            job_id,
            phase=JobPhase.COMPLETED,
            is_finished=True,
            progress_percent=100,
            progress_text="100%",
            message="Task completed successfully.",
            result=result or {},
            produced_assets=produced_assets or [],
        )

    async def mark_failed(self, job_id: str, error: str) -> JobStatus:
        """Transition job to FAILED."""
        return await self.update_status(
            job_id,
            phase=JobPhase.FAILED,
            is_finished=True,
            error=error,
            message=f"Task failed: {error}",
        )

    async def list_active_jobs(self) -> list[Job]:
        """List all unfinished jobs."""
        async with self._lock:
            return [j for j in self._jobs.values() if not j.is_finished]

    async def list_broadcast_children(self, parent_job_id: str) -> list[Job]:
        """List all broadcast child jobs for a parent image/character task."""
        return await self.dao.list_broadcast_children(parent_job_id)
