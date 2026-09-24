"""WorkerPool: Manages worker registry, heartbeats, health status, and routing."""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from loguru import logger

from flow_mcp.models.job import JobSpec
from flow_mcp.models.worker import WorkerInfo, WorkerPhase
from flow_mcp.utils.errors import WorkerNotFoundError


class WorkerPool:
    """
    WorkerPool tracks connected workers (Worker 0 and remote workers) and performs credit-aware routing.
    """

    def __init__(self, heartbeat_timeout: float = 30.0):
        self.heartbeat_timeout = heartbeat_timeout
        self._workers: dict[str, WorkerInfo] = {}
        self._lock = asyncio.Lock()

    async def register_worker(
        self,
        worker_id: str,
        account: str = "",
        project_mappings: dict[str, str] | None = None,
        cached_assets: list[str] | None = None,
        daily_free: int | None = None,
        balance: Optional[int] = None,
    ) -> WorkerInfo:
        """Register or re-connect a worker."""
        async with self._lock:
            effective_account = account or f"{worker_id}@cluster.local"
            if worker_id in self._workers:
                worker = self._workers[worker_id]
                worker.phase = WorkerPhase.IDLE
                worker.last_heartbeat = time.time()
                if account:
                    worker.account = account
                if project_mappings:
                    worker.project_mappings.update(project_mappings)
                if cached_assets:
                    worker.cached_assets.update(cached_assets)
                if balance is not None:
                    worker.balance = balance
                if daily_free is not None:
                    worker.daily_free = daily_free
                logger.info(f"Worker {worker_id} re-registered / reconnected.")
            else:
                from flow_mcp.models.credit import DAILY_FREE_GRANT
                worker = WorkerInfo(
                    worker_id=worker_id,
                    phase=WorkerPhase.IDLE,
                    account=effective_account,
                    daily_free=daily_free if daily_free is not None else DAILY_FREE_GRANT,
                    balance=balance,
                    project_mappings=project_mappings or {},
                    cached_assets=set(cached_assets or []),
                    last_heartbeat=time.time(),
                )
                self._workers[worker_id] = worker
                logger.info(f"Worker {worker_id} registered into pool.")
            return worker

    async def heartbeat(self, worker_id: str) -> None:
        """Update last heartbeat timestamp for worker."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.last_heartbeat = time.time()
                if worker.phase == WorkerPhase.DISCONNECTED:
                    worker.phase = WorkerPhase.IDLE

    async def mark_busy(self, worker_id: str, job_id: str) -> None:
        """Mark worker busy with a job."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                raise WorkerNotFoundError(f"Worker {worker_id} not found")
            worker.phase = WorkerPhase.BUSY
            worker.current_job_id = job_id

    async def mark_idle(self, worker_id: str) -> None:
        """Mark worker idle after job completion."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.phase = WorkerPhase.IDLE
                worker.current_job_id = None
                worker.consecutive_failures = 0

    async def mark_failed(self, worker_id: str) -> None:
        """Record a failure for worker and mark idle."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.phase = WorkerPhase.IDLE
                worker.current_job_id = None
                worker.consecutive_failures += 1

    async def update_account_credits(
        self,
        worker_id: str,
        daily_free: Optional[int] = None,
        balance: Optional[int] = None,
    ) -> None:
        """Update credits tracked in WorkerInfo."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                if daily_free is not None:
                    worker.daily_free = daily_free
                if balance is not None:
                    worker.balance = balance

    async def add_cached_asset(self, worker_id: str, asset_name: str) -> None:
        """Record that worker now possesses asset locally in Flow."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker and asset_name not in worker.cached_assets:
                worker.cached_assets.add(asset_name)

    async def update_project_mapping(self, worker_id: str, project_alias: str, local_uuid: str) -> None:
        """Record project mapping for worker."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.project_mappings[project_alias] = local_uuid

    async def check_health(self) -> list[str]:
        """
        Check for timed out workers. Returns list of worker_ids that were marked disconnected.
        """
        now = time.time()
        disconnected: list[str] = []
        async with self._lock:
            for worker_id, worker in self._workers.items():
                if worker_id == "master_local_worker":
                    worker.last_heartbeat = now
                    continue
                if worker.phase != WorkerPhase.DISCONNECTED:
                    if now - worker.last_heartbeat > self.heartbeat_timeout:
                        worker.phase = WorkerPhase.DISCONNECTED
                        disconnected.append(worker_id)
                        logger.warning(
                            f"Worker {worker_id} heartbeat timed out ({now - worker.last_heartbeat:.1f}s), marked DISCONNECTED"
                        )
        return disconnected

    async def select_best(self, spec: JobSpec) -> WorkerInfo | None:
        """
        Select best worker for a video or execution job based on:
        1. Availability (IDLE & connected)
        2. Can afford credit cost (free + balance >= cost)
        3. If target_worker_id is set (e.g. broadcast), must match
        4. Priority routing:
           - Highest daily_free first
           - Highest balance first
           - Lowest consecutive failures first
        """
        cost = spec.cost_credits

        async with self._lock:
            candidates: list[WorkerInfo] = []
            for w in self._workers.values():
                if not w.is_available:
                    continue
                if spec.target_worker_id and w.worker_id != spec.target_worker_id:
                    continue
                if not w.can_afford(cost):
                    continue
                candidates.append(w)

            if not candidates:
                return None

            def score_worker(w: WorkerInfo):
                bal = w.balance or 0
                return (-w.daily_free, -bal, w.consecutive_failures)

            candidates.sort(key=score_worker)
            return candidates[0]

    async def get_worker(self, worker_id: str) -> WorkerInfo | None:
        async with self._lock:
            return self._workers.get(worker_id)

    async def list_workers(self) -> list[WorkerInfo]:
        async with self._lock:
            return list(self._workers.values())

    async def list_idle_workers(self) -> list[WorkerInfo]:
        async with self._lock:
            return [w for w in self._workers.values() if w.is_available]
