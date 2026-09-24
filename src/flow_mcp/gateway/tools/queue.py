"""Queue and cluster status MCP tools."""
from __future__ import annotations

from typing import Any, Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from flow_mcp.control.credit_manager import CreditManager
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.control.scheduler import Scheduler
from flow_mcp.control.worker_pool import WorkerPool
from flow_mcp.models.job import JobPhase


def register_queue_tools(
    mcp: FastMCP,
    job_registry: JobRegistry,
    worker_pool: WorkerPool,
    credit_manager: CreditManager,
    scheduler: Scheduler,
) -> None:
    """Register queue and task management MCP tools."""

    @mcp.tool(name="task_queue_status", description="Query cluster task queue and connected worker status")
    async def task_queue_status() -> dict[str, Any]:
        """
        查询 Google Flow MCP 全局任务队列的当前状态。
        
        【用途与返回字段说明】
        可以获取当前激活的任务(排队或进行中)列表，以及连接的 worker 状态、可用账号等概览信息。
        """
        workers = await worker_pool.list_workers()
        active_jobs = await job_registry.list_active_jobs()
        accounts = await credit_manager.list_accounts()

        return {
            "status": "success",
            "active_jobs_count": len(active_jobs),
            "workers_count": len(workers),
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "phase": w.phase.value,
                    "account": w.account,
                    "daily_free": w.daily_free,
                    "balance": w.balance,
                    "is_available": w.is_available,
                    "current_job_id": w.current_job_id,
                }
                for w in workers
            ],
            "active_jobs": [
                {
                    "job_id": j.job_id,
                    "task_type": j.task_type.value,
                    "phase": j.phase.value,
                    "worker_id": j.status.worker_id,
                    "progress_percent": j.status.progress_percent,
                    "progress_text": j.status.progress_text,
                    "elapsed_seconds": j.status.elapsed_seconds,
                    "queue_position": j.status.queue_position,
                }
                for j in active_jobs
            ],
            "accounts": [a.model_dump() for a in accounts],
        }

    @mcp.tool(name="task_cancel", description="Cancel an active or queued task by job_id")
    async def task_cancel(
        job_id: Annotated[str, Field(description="要取消的任务唯一 ID (job_id)")]
    ) -> dict[str, Any]:
        """
        取消指定的生成任务（包括排队中任务及正在执行中的任务）。
        
        【执行规则】
        1. 若任务正在排队中：立即从队列中移除并标记为 cancelled，后续任务自动前移。
        2. 若任务正在执行中：触发取消中断信号，重置相关资源并标记为 cancelled。
        3. 若任务已结束或不存在：返回相应提示信息。
        """
        job = await job_registry.get_job(job_id)
        if not job:
            return {"status": "error", "message": f"Job '{job_id}' not found."}

        if job.is_finished:
            return {"status": "info", "message": f"Job '{job_id}' is already finished ({job.phase.value})."}

        await credit_manager.release(job_id)
        await job_registry.update_status(
            job_id,
            phase=JobPhase.CANCELLED,
            is_finished=True,
            message="Task was cancelled by user request.",
        )
        return {"status": "success", "message": f"Job '{job_id}' has been cancelled."}
