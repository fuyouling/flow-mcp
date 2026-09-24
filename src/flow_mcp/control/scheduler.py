"""Scheduler: FIFO queue, task assignment, credit reservation, and failover orchestration."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from google.protobuf.struct_pb2 import Struct
from loguru import logger

from flow_mcp.control.credit_manager import CreditManager
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.control.worker_pool import WorkerPool
from flow_mcp.models.job import JobPhase, JobSpec
from flow_mcp.proto import flow_pb2
from flow_mcp.utils.errors import InsufficientCreditsError


class Scheduler:
    """
    Scheduler manages task queuing, worker selection, credit reservation, and dispatching.
    """

    def __init__(
        self,
        worker_pool: WorkerPool,
        job_registry: JobRegistry,
        credit_manager: CreditManager,
        poll_interval: float = 1.0,
    ):
        self.worker_pool = worker_pool
        self.job_registry = job_registry
        self.credit_manager = credit_manager
        self.poll_interval = poll_interval

        self._queue: list[JobSpec] = []
        self._queue_lock = asyncio.Lock()
        self._running = False
        self._task: asyncio.Task | None = None

        # Dispatch handlers
        self._remote_dispatcher: Optional[Callable[[str, flow_pb2.ExecuteTask], Awaitable[bool]]] = None
        self._local_dispatcher: Optional[Callable[[JobSpec], Awaitable[None]]] = None

    def set_dispatchers(
        self,
        remote_dispatcher: Callable[[str, flow_pb2.ExecuteTask], Awaitable[bool]],
        local_dispatcher: Callable[[JobSpec], Awaitable[None]],
    ) -> None:
        """Register dispatch callbacks for remote workers and local Worker 0."""
        self._remote_dispatcher = remote_dispatcher
        self._local_dispatcher = local_dispatcher

    async def submit(self, spec: JobSpec, priority_front: bool = False) -> None:
        """Submit a job spec to the scheduler queue."""
        async with self._queue_lock:
            if priority_front:
                self._queue.insert(0, spec)
            else:
                self._queue.append(spec)
            queue_len = len(self._queue)

        await self.job_registry.update_status(
            spec.job_id,
            phase=JobPhase.PENDING,
            queue_position=queue_len,
            message="Queued for worker execution.",
        )
        logger.info(f"Job {spec.job_id} submitted to scheduler queue (position {queue_len}).")

    async def start(self) -> None:
        """Start the background scheduler loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler loop started.")

    async def stop(self) -> None:
        """Stop the background scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler loop stopped.")

    async def _run_loop(self) -> None:
        """Continuous scheduling loop."""
        while self._running:
            try:
                # 1. Background worker health check
                disconnected = await self.worker_pool.check_health()
                for wid in disconnected:
                    await self._handle_worker_disconnected(wid)

                # 2. Process queue
                await self._schedule_next()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _schedule_next(self) -> None:
        """Try to schedule pending jobs to available workers."""
        async with self._queue_lock:
            if not self._queue:
                return

            remaining_queue: list[JobSpec] = []
            for spec in self._queue:
                worker = await self.worker_pool.select_best(spec)
                if not worker:
                    remaining_queue.append(spec)
                    continue

                # Reserve credits
                try:
                    await self.credit_manager.reserve(worker.account, spec.job_id, spec.cost_credits)
                    
                    # Update WorkerPool cache so routing works correctly!
                    account_info = await self.credit_manager.get_account(worker.account)
                    if account_info:
                        await self.worker_pool.update_account_credits(
                            worker.worker_id, 
                            daily_free=account_info.daily_free_remaining, 
                            balance=account_info.balance
                        )
                except InsufficientCreditsError as e:
                    logger.warning(f"Credit reservation failed for job {spec.job_id} on {worker.worker_id}: {e}")
                    remaining_queue.append(spec)
                    continue
                except Exception as e:
                    logger.error(
                        f"Unexpected error reserving credits for job {spec.job_id} on {worker.worker_id} (account={worker.account}): {e}"
                    )
                    remaining_queue.append(spec)
                    continue

                # Mark worker busy
                await self.worker_pool.mark_busy(worker.worker_id, spec.job_id)
                await self.job_registry.update_status(
                    spec.job_id,
                    phase=JobPhase.ASSIGNED,
                    worker_id=worker.worker_id,
                    message=f"Assigned to worker {worker.worker_id}.",
                )

                # Confirm reservation & dispatch
                await self.credit_manager.confirm(spec.job_id)
                asyncio.create_task(self._dispatch_task(worker.worker_id, spec))

            self._queue = remaining_queue

            # Update queue positions
            for idx, item in enumerate(self._queue):
                await self.job_registry.update_status(item.job_id, queue_position=idx + 1)

    async def _dispatch_task(self, worker_id: str, spec: JobSpec) -> None:
        """Dispatch task to local executor (Worker 0) or remote worker via gRPC."""
        try:
            if worker_id == "master_local_worker":
                if self._local_dispatcher:
                    await self._local_dispatcher(spec)
                else:
                    raise RuntimeError("Local dispatcher not registered in scheduler.")
            else:
                if not self._remote_dispatcher:
                    raise RuntimeError("Remote dispatcher not registered in scheduler.")

                # Build protobuf Struct for params
                p_struct = Struct()
                p_struct.update(spec.params)

                task_msg = flow_pb2.ExecuteTask(
                    job_id=spec.job_id,
                    task_type=spec.task_type.value,
                    project_alias=spec.project_alias,
                    params=p_struct,
                    required_assets=spec.required_assets,
                    parent_job_id=spec.parent_job_id or "",
                )
                success = await self._remote_dispatcher(worker_id, task_msg)
                if not success:
                    raise RuntimeError(f"Failed to deliver gRPC task to worker {worker_id}")

        except Exception as e:
            logger.error(f"Dispatch failed for job {spec.job_id} to worker {worker_id}: {e}")
            await self.handle_task_failed(spec.job_id, worker_id, str(e))

    async def handle_task_completed(
        self,
        job_id: str,
        worker_id: str,
        result: dict[str, Any],
        produced_assets: list[dict[str, Any]],
    ) -> None:
        """Handle notification that a task has finished successfully."""
        await self.worker_pool.mark_idle(worker_id)
        
        job = await self.job_registry.get_job(job_id)
        if job and job.phase == JobPhase.CANCELLED:
            logger.info(f"Job {job_id} finished on {worker_id} but was previously cancelled. Retaining cancelled state.")
            return

        await self.job_registry.mark_completed(job_id, result=result, produced_assets=produced_assets)
        logger.info(f"Job {job_id} successfully finished on worker {worker_id}.")

    async def handle_task_failed(self, job_id: str, worker_id: str, error: str) -> None:
        """Handle task failure: release reservation and trigger failover retry if allowed."""
        logger.warning(f"Job {job_id} failed on worker {worker_id}: {error}")
        await self.credit_manager.release(job_id)
        
        worker = await self.worker_pool.get_worker(worker_id)
        if worker and worker.account:
            account_info = await self.credit_manager.get_account(worker.account)
            if account_info:
                await self.worker_pool.update_account_credits(
                    worker.worker_id, 
                    daily_free=account_info.daily_free_remaining, 
                    balance=account_info.balance
                )

        await self.worker_pool.mark_failed(worker_id)

        job = await self.job_registry.get_job(job_id)
        if not job:
            return

        spec = job.spec
        if spec.retry_count < spec.max_retries:
            spec.retry_count += 1
            logger.info(f"Retrying job {job_id} (attempt {spec.retry_count}/{spec.max_retries})")
            await self.submit(spec, priority_front=True)
        else:
            await self.job_registry.mark_failed(job_id, error=error)

    async def _handle_worker_disconnected(self, worker_id: str) -> None:
        """Failover in-flight task when worker drops connection."""
        worker = await self.worker_pool.get_worker(worker_id)
        if worker and worker.current_job_id:
            logger.warning(f"In-flight job {worker.current_job_id} lost due to worker {worker_id} disconnect.")
            await self.handle_task_failed(
                worker.current_job_id, worker_id, f"Worker {worker_id} disconnected unexpectedly"
            )
