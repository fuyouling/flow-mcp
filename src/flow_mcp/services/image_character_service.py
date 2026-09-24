"""ImageCharacterService: Orchestrates Master local creation and parallel worker broadcasting."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from loguru import logger

from flow_mcp.control.asset_hub import AssetHub
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.control.scheduler import Scheduler
from flow_mcp.control.worker_pool import WorkerPool
from flow_mcp.local.local_executor import LocalExecutor
from flow_mcp.models.asset import AssetKind
from flow_mcp.models.job import Job, JobPhase, JobSpec, TaskType
from flow_mcp.models.params import (
    CharacterCreateByUploadParams,
    CharacterCreateParams,
    ImageCreateByUploadParams,
    ImageCreateParams,
)


class ImageCharacterService:
    """
    Coordinates creation of images and characters:
    1. Local creation on Master's Worker 0
    2. Ingestion of output files into Master AssetHub
    3. Parallel broadcast submission to all connected Workers
    4. Aggregation of broadcast status
    """

    def __init__(
        self,
        local_executor: LocalExecutor,
        scheduler: Scheduler,
        asset_hub: AssetHub,
        worker_pool: WorkerPool,
        job_registry: JobRegistry,
    ):
        self.local_executor = local_executor
        self.scheduler = scheduler
        self.asset_hub = asset_hub
        self.worker_pool = worker_pool
        self.job_registry = job_registry

    async def create_image(self, params: ImageCreateParams) -> str:
        """Submit text-to-image creation job. Returns job_id immediately."""
        spec = JobSpec(
            task_type=TaskType.IMAGE_CREATE,
            project_alias=params.project_name or "default",
            params=params.model_dump(),
            cost_credits=0,
        )
        job = await self.job_registry.register_job(spec)
        asyncio.create_task(self._run_image_create_job(job, params))
        return job.job_id

    async def create_image_by_upload(self, params: ImageCreateByUploadParams) -> str:
        """Submit image upload job. Returns job_id immediately."""
        spec = JobSpec(
            task_type=TaskType.IMAGE_CREATE_BY_UPLOAD,
            project_alias=params.project_name or "default",
            params=params.model_dump(),
            cost_credits=0,
        )
        job = await self.job_registry.register_job(spec)
        asyncio.create_task(self._run_image_upload_job(job, params))
        return job.job_id

    async def create_character(self, params: CharacterCreateParams) -> str:
        """Submit character creation job. Returns job_id immediately."""
        spec = JobSpec(
            task_type=TaskType.CHARACTER_CREATE,
            project_alias=params.project_name or "default",
            params=params.model_dump(),
            cost_credits=0,
        )
        job = await self.job_registry.register_job(spec)
        asyncio.create_task(self._run_character_create_job(job, params))
        return job.job_id

    async def create_character_by_upload(self, params: CharacterCreateByUploadParams) -> str:
        """Submit character creation by upload job. Returns job_id immediately."""
        spec = JobSpec(
            task_type=TaskType.CHARACTER_CREATE_BY_UPLOAD,
            project_alias=params.project_name or "default",
            params=params.model_dump(),
            cost_credits=0,
        )
        job = await self.job_registry.register_job(spec)
        asyncio.create_task(self._run_character_upload_job(job, params))
        return job.job_id

    async def _run_image_create_job(self, job: Job, params: ImageCreateParams) -> None:
        """Execute image creation on Master, store in AssetHub, broadcast to workers."""
        try:
            await self.job_registry.update_status(
                job.job_id,
                phase=JobPhase.MASTER_RUNNING,
                message="Master Worker 0 generating image...",
            )

            start_time = time.time()
            loop = asyncio.get_running_loop()

            def progress_cb(pct: int, txt: str):
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.job_registry.update_status(
                            job.job_id,
                            progress_percent=pct,
                            progress_text=txt,
                            elapsed_seconds=round(time.time() - start_time, 1),
                        ),
                        loop,
                    )
                except Exception as ex:
                    logger.debug(f"Failed to update progress for job {job.job_id}: {ex}")

            res = await self.local_executor.create_image(
                job.spec.project_alias, params, progress_cb=progress_cb
            )

            # Store in AssetHub if downloaded
            local_path = res.get("local_path")
            image_name = res.get("image_name") or f"image_{job.job_id[:8]}"
            if local_path and Path(local_path).is_file():
                record = await self.asset_hub.store_asset(
                    source_path=Path(local_path),
                    name=image_name,
                    kind=AssetKind.IMAGE,
                    created_by_worker="master",
                    source_job_id=job.job_id,
                )
                res["asset_hub_record"] = record.model_dump()

            # Broadcast to all connected workers
            await self.job_registry.update_status(
                job.job_id,
                phase=JobPhase.BROADCASTING,
                message="Broadcasting image to all worker nodes...",
            )
            broadcast_results = await self._broadcast_asset(
                asset_name=image_name,
                kind=AssetKind.IMAGE,
                project_alias=job.spec.project_alias,
                parent_job=job,
            )

            await self.job_registry.update_status(
                job.job_id,
                phase=JobPhase.COMPLETED,
                is_finished=True,
                progress_percent=100,
                progress_text="100%",
                message="Image created and broadcasted to workers.",
                result=res,
                broadcast_results=broadcast_results,
            )

        except Exception as e:
            logger.error(f"Image creation job {job.job_id} failed: {e}", exc_info=True)
            await self.job_registry.mark_failed(job.job_id, error=str(e))

    async def _run_image_upload_job(self, job: Job, params: ImageCreateByUploadParams) -> None:
        """Upload image to Master, ingest into AssetHub, broadcast to workers."""
        try:
            await self.job_registry.update_status(job.job_id, phase=JobPhase.MASTER_RUNNING)
            res = await self.local_executor.create_image_by_upload(job.spec.project_alias, params)

            image_name = params.image_name or Path(params.image_path).stem
            record = await self.asset_hub.store_asset(
                source_path=Path(params.image_path),
                name=image_name,
                kind=AssetKind.IMAGE,
                created_by_worker="master",
                source_job_id=job.job_id,
            )
            res["asset_hub_record"] = record.model_dump()

            await self.job_registry.update_status(job.job_id, phase=JobPhase.BROADCASTING)
            broadcast_results = await self._broadcast_asset(
                asset_name=image_name,
                kind=AssetKind.IMAGE,
                project_alias=job.spec.project_alias,
                parent_job=job,
            )

            await self.job_registry.update_status(
                job.job_id,
                phase=JobPhase.COMPLETED,
                is_finished=True,
                result=res,
                broadcast_results=broadcast_results,
            )
        except Exception as e:
            logger.error(f"Image upload job {job.job_id} failed: {e}", exc_info=True)
            await self.job_registry.mark_failed(job.job_id, error=str(e))

    async def _run_character_create_job(self, job: Job, params: CharacterCreateParams) -> None:
        """Create character on Master, ingest into AssetHub, broadcast to workers."""
        try:
            await self.job_registry.update_status(job.job_id, phase=JobPhase.MASTER_RUNNING)
            res = await self.local_executor.create_character(job.spec.project_alias, params)

            char_name = params.character_name
            portrait_path = res.get("portrait_path")
            if portrait_path and Path(portrait_path).is_file():
                await self.asset_hub.store_asset(
                    source_path=Path(portrait_path),
                    name=f"{char_name}_Portrait",
                    kind=AssetKind.CHARACTER,
                    created_by_worker="master",
                    source_job_id=job.job_id,
                )

            fullbody_path = res.get("fullbody_path")
            if fullbody_path and Path(fullbody_path).is_file():
                await self.asset_hub.store_asset(
                    source_path=Path(fullbody_path),
                    name=f"{char_name}_Fullbody",
                    kind=AssetKind.CHARACTER,
                    created_by_worker="master",
                    source_job_id=job.job_id,
                )

            await self.job_registry.update_status(job.job_id, phase=JobPhase.BROADCASTING)
            broadcast_results = {}
            if portrait_path and Path(portrait_path).is_file():
                broadcast_results = await self._broadcast_asset(
                    asset_name=f"{char_name}_Portrait",
                    kind=AssetKind.CHARACTER,
                    project_alias=job.spec.project_alias,
                    parent_job=job,
                )
            
            if fullbody_path and Path(fullbody_path).is_file():
                fb_broadcast = await self._broadcast_asset(
                    asset_name=f"{char_name}_Fullbody",
                    kind=AssetKind.CHARACTER,
                    project_alias=job.spec.project_alias,
                    parent_job=job,
                )
                for wid, status in fb_broadcast.items():
                    if status == "failed":
                        broadcast_results[wid] = "failed"
                    elif wid not in broadcast_results:
                        broadcast_results[wid] = status

            await self.job_registry.update_status(
                job.job_id,
                phase=JobPhase.COMPLETED,
                is_finished=True,
                result=res,
                broadcast_results=broadcast_results,
            )
        except Exception as e:
            logger.error(f"Character create job {job.job_id} failed: {e}", exc_info=True)
            await self.job_registry.mark_failed(job.job_id, error=str(e))

    async def _run_character_upload_job(self, job: Job, params: CharacterCreateByUploadParams) -> None:
        """Upload character to Master, ingest into AssetHub, broadcast to workers."""
        try:
            await self.job_registry.update_status(job.job_id, phase=JobPhase.MASTER_RUNNING)
            res = await self.local_executor.create_character_by_upload(job.spec.project_alias, params)

            char_name = params.character_name
            if params.portrait_image_path and Path(params.portrait_image_path).is_file():
                await self.asset_hub.store_asset(
                    source_path=Path(params.portrait_image_path),
                    name=f"{char_name}_Portrait",
                    kind=AssetKind.CHARACTER,
                    created_by_worker="master",
                    source_job_id=job.job_id,
                )

            if params.full_body_image_path and Path(params.full_body_image_path).is_file():
                await self.asset_hub.store_asset(
                    source_path=Path(params.full_body_image_path),
                    name=f"{char_name}_Fullbody",
                    kind=AssetKind.CHARACTER,
                    created_by_worker="master",
                    source_job_id=job.job_id,
                )

            await self.job_registry.update_status(job.job_id, phase=JobPhase.BROADCASTING)
            broadcast_results = {}
            if params.portrait_image_path and Path(params.portrait_image_path).is_file():
                broadcast_results = await self._broadcast_asset(
                    asset_name=f"{char_name}_Portrait",
                    kind=AssetKind.CHARACTER,
                    project_alias=job.spec.project_alias,
                    parent_job=job,
                )
            
            if params.full_body_image_path and Path(params.full_body_image_path).is_file():
                fb_broadcast = await self._broadcast_asset(
                    asset_name=f"{char_name}_Fullbody",
                    kind=AssetKind.CHARACTER,
                    project_alias=job.spec.project_alias,
                    parent_job=job,
                )
                for wid, status in fb_broadcast.items():
                    if status == "failed":
                        broadcast_results[wid] = "failed"
                    elif wid not in broadcast_results:
                        broadcast_results[wid] = status

            await self.job_registry.update_status(
                job.job_id,
                phase=JobPhase.COMPLETED,
                is_finished=True,
                result=res,
                broadcast_results=broadcast_results,
            )
        except Exception as e:
            logger.error(f"Character upload job {job.job_id} failed: {e}", exc_info=True)
            await self.job_registry.mark_failed(job.job_id, error=str(e))

    async def _broadcast_asset(
        self,
        asset_name: str,
        kind: AssetKind,
        project_alias: str,
        parent_job: Job,
        timeout: float = 120.0,
    ) -> dict[str, str]:
        """
        Broadcast an asset in parallel to all connected remote workers.
        Failures are tracked per worker without aborting the parent job.
        """
        workers = await self.worker_pool.list_workers()
        # Exclude Worker 0 (already has the asset)
        target_workers = [w for w in workers if w.worker_id != "master_local_worker"]

        if not target_workers:
            logger.info("No remote workers currently connected; broadcast step skipped.")
            return {}

        results: dict[str, str] = {}
        child_jobs: list[Job] = []

        task_type = (
            TaskType.BROADCAST_IMAGE if kind == AssetKind.IMAGE else TaskType.BROADCAST_CHARACTER
        )

        for w in target_workers:
            child_spec = JobSpec(
                task_type=task_type,
                project_alias=project_alias,
                params={"asset_name": asset_name},
                target_worker_id=w.worker_id,
                parent_job_id=parent_job.job_id,
                cost_credits=0,
            )
            child_job = await self.job_registry.register_job(child_spec)
            child_jobs.append(child_job)
            await self.scheduler.submit(child_spec)

        # Wait for child jobs completion up to timeout
        start = time.time()
        while time.time() - start < timeout:
            all_done = True
            for c in child_jobs:
                st = await self.job_registry.get_status(c.job_id)
                if not st or not st.is_finished:
                    all_done = False
                    break
            if all_done:
                break
            await asyncio.sleep(1.0)

        # Collect results
        for c in child_jobs:
            st = await self.job_registry.get_status(c.job_id)
            wid = c.spec.target_worker_id or "unknown"
            if st and st.phase == JobPhase.COMPLETED:
                results[wid] = "success"
                await self.worker_pool.add_cached_asset(wid, asset_name)
            else:
                results[wid] = "failed"

        logger.info(f"Broadcast of asset '{asset_name}' completed. Results: {results}")
        return results
