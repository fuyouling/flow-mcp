"""VideoService: Orchestrates video generation jobs, credit calculation, and worker routing."""
from __future__ import annotations

from loguru import logger

from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.control.scheduler import Scheduler
from flow_mcp.models.job import JobSpec, TaskType
from flow_mcp.models.params import VideoCreateParams, VideoCreateByUploadParams
from flow_mcp.utils.credit_calc import calc_task_credits


class VideoService:
    """
    Orchestrates video tasks:
    1. Calculates credit cost
    2. Enqueues job spec into Scheduler
    3. Scheduler routes to optimal Worker based on credits & assets
    4. Worker generates video and uploads result back to Master AssetHub
    """

    def __init__(self, scheduler: Scheduler, job_registry: JobRegistry):
        self.scheduler = scheduler
        self.job_registry = job_registry

    async def create_video(self, params: VideoCreateParams) -> str:
        """Submit text/image-to-video generation job. Returns job_id."""
        cost = calc_task_credits(TaskType.VIDEO_CREATE, params.model_dump())
        assets_list = [a.strip() for a in params.assets.split(",") if a.strip()] if params.assets else []

        spec = JobSpec(
            task_type=TaskType.VIDEO_CREATE,
            project_alias=params.project_name or "default",
            params=params.model_dump(),
            required_assets=assets_list,
            cost_credits=cost,
        )

        job = await self.job_registry.register_job(spec)
        logger.info(f"Video job {job.job_id} registered with cost={cost} credits, submitting to scheduler...")
        await self.scheduler.submit(spec)
        return job.job_id

    async def create_video_by_upload(self, params: VideoCreateByUploadParams) -> str:
        """Submit video creation by uploading reference media. Returns job_id."""
        cost = calc_task_credits(TaskType.VIDEO_CREATE_BY_UPLOAD, params.model_dump())
        assets_list = [a.strip() for a in params.assets.split(",") if a.strip()] if params.assets else []

        spec = JobSpec(
            task_type=TaskType.VIDEO_CREATE_BY_UPLOAD,
            project_alias=params.project_name or "default",
            params=params.model_dump(),
            required_assets=assets_list,
            cost_credits=cost,
        )

        job = await self.job_registry.register_job(spec)
        logger.info(f"Video by upload job {job.job_id} registered with cost={cost} credits, submitting to scheduler...")
        await self.scheduler.submit(spec)
        return job.job_id
