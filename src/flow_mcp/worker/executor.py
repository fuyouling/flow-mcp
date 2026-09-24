"""WorkerExecutor: Handles task execution, JIT asset sync, browser operations, and result uploads."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Coroutine

import httpx
from google.protobuf.json_format import MessageToDict
from loguru import logger

from flow_mcp.browser.session import get_browser
from flow_mcp.config import get_settings
from flow_mcp.models.asset import AssetKind
from flow_mcp.models.job import TaskType
from flow_mcp.pages.home_page import HomePage
from flow_mcp.pages.video_page import VideoPage
from flow_mcp.proto import flow_pb2
from flow_mcp.worker.asset_syncer import AssetSyncer


class WorkerExecutor:
    """
    Executes tasks on the Worker node:
    - Resolves/creates local Flow projects
    - JIT downloads required assets from Master
    - Performs generation via Page Objects
    - Uploads video results back to Master AssetHub
    """

    def __init__(
        self,
        worker_id: str,
        asset_syncer: AssetSyncer | None = None,
        master_http_url: str | None = None,
        on_project_mapping_added: Callable[[str, str], Coroutine[Any, Any, None]] | None = None,
    ):
        settings = get_settings()
        self.worker_id = worker_id
        self.asset_syncer = asset_syncer or AssetSyncer(master_http_url=master_http_url)
        self.master_http_url = (master_http_url or settings.master_http_url).rstrip("/")
        self.on_project_mapping_added = on_project_mapping_added
        self.project_mappings: dict[str, str] = {}
        self.cached_assets: set[str] = set()

    async def ensure_project_url(self, project_alias: str) -> str:
        """Resolve project alias to local Flow project URL."""
        settings = get_settings()
        base_url = settings.google_flow_base_url

        if project_alias in self.project_mappings:
            return f"{base_url}/project/{self.project_mappings[project_alias]}"

        browser = get_browser()
        tab = browser.latest_tab
        # pyright complains about MixTab | str, we know it's MixTab here or we cast it
        home = HomePage(tab) # type: ignore
        home.open()

        projects = home.get_projects()
        if project_alias in projects:
            local_uuid = projects[project_alias]["local_uuid"]
            self.project_mappings[project_alias] = local_uuid
            return f"{base_url}/project/{local_uuid}"

        # Create project if not exists
        logger.info(f"Worker creating new project '{project_alias}'...")
        new_uuid = home.create_project()
        
        # Retry renaming up to 3 times
        for attempt in range(3):
            home.open()
            if home.rename_project(new_title=project_alias, project_uuid=new_uuid):
                break
            logger.warning(f"Project card not found yet (attempt {attempt+1}/3), retrying in 3s...")
            await asyncio.sleep(3)
            
        self.project_mappings[project_alias] = new_uuid
        if self.on_project_mapping_added:
            await self.on_project_mapping_added(project_alias, new_uuid)
            
        return f"{base_url}/project/{new_uuid}"

    async def _upload_result_to_hub(
        self, file_path: Path, name: str, kind: AssetKind, job_id: str
    ) -> dict[str, Any]:
        """Upload produced file back to Master AssetHub."""
        url = f"{self.master_http_url}/assets/upload"
        logger.info(f"Uploading result {name} ({file_path}) to Master AssetHub: {url}")

        async with httpx.AsyncClient(timeout=180.0) as client:
            with file_path.open("rb") as f:
                files = {"file": (file_path.name, f, "video/mp4")}
                data = {
                    "name": name,
                    "kind": kind.value,
                    "worker_id": self.worker_id,
                    "job_id": job_id,
                }
                resp = await client.post(url, files=files, data=data)
                if resp.status_code != 200:
                    raise RuntimeError(f"Asset upload failed: HTTP {resp.status_code} - {resp.text}")
                return resp.json()

    async def execute_task(
        self,
        task: flow_pb2.ExecuteTask,
        progress_cb: Callable[[int, str], Coroutine[Any, Any, None]],
    ) -> tuple[dict[str, Any], list[flow_pb2.AssetInfo]]:
        """
        Execute received task on worker browser.
        Returns: (result_dict, produced_assets)
        """
        task_type = TaskType(task.task_type)
        params = MessageToDict(task.params)
        project_url = await self.ensure_project_url(task.project_alias)

        browser = get_browser()
        tab = browser.latest_tab

        # JIT Asset Sync
        for asset in task.required_assets:
            if asset not in self.cached_assets:
                logger.info(f"JIT syncing required asset '{asset}' before executing {task.job_id}")
                await self.asset_syncer.sync_to_flow_project(tab, project_url, asset)
                self.cached_assets.add(asset)

        # ── 1. Broadcast Image ─────────────────────────────
        if task_type == TaskType.BROADCAST_IMAGE:
            asset_name = params.get("asset_name", "")
            if asset_name and asset_name not in self.cached_assets:
                await self.asset_syncer.sync_to_flow_project(tab, project_url, asset_name, AssetKind.IMAGE)
                self.cached_assets.add(asset_name)
            return {"status": "broadcast_success", "asset_name": asset_name}, []

        # ── 2. Broadcast Character ─────────────────────────
        elif task_type == TaskType.BROADCAST_CHARACTER:
            character_name = params.get("character_name", "")
            if character_name and character_name not in self.cached_assets:
                has_portrait = params.get("has_portrait", False)
                has_fullbody = params.get("has_fullbody", False)
                voice_name = params.get("voice_name", "")
                voice_style = params.get("voice_style", "")
                
                await self.asset_syncer.sync_character_to_flow_project(
                    tab, 
                    project_url, 
                    character_name, 
                    has_portrait, 
                    has_fullbody, 
                    voice_name, 
                    voice_style
                )
                self.cached_assets.add(character_name)
            return {"status": "broadcast_success", "character_name": character_name}, []

        # ── 3. Video Create ────────────────────────────────
        elif task_type in (TaskType.VIDEO_CREATE, TaskType.VIDEO_CREATE_BY_UPLOAD):
            vid_page = VideoPage(tab) # type: ignore

            loop = asyncio.get_running_loop()

            def sync_progress(pct: int, txt: str):
                try:
                    asyncio.run_coroutine_threadsafe(progress_cb(pct, txt), loop)
                except Exception as ex:
                    logger.debug(f"Failed to update task progress: {ex}")

            def run_gen():
                assets_list = [a.strip() for a in params.get("assets", "").split(",") if a.strip()]
                return vid_page.generate_video(
                    project_url=project_url,
                    prompt=params.get("prompt", ""),
                    model_name=params.get("model_name", "Omni 1.1 Flash"),
                    mode=params.get("mode", "asset"),
                    start_frame=params.get("start_frame", ""),
                    end_frame=params.get("end_frame", ""),
                    aspect_ratio=params.get("aspect_ratio", "16:9"),
                    resolution=params.get("resolution", "720p"),
                    duration=int(params.get("duration", 8)),
                    quantity=f"x{params.get('quantity', 1)}",
                    assets=assets_list,
                    rename_name=params.get("video_name", f"video_{task.job_id[:8]}"),
                    download=params.get("download", "720p"),
                    progress_callback=sync_progress,
                )

            gen_result = await asyncio.to_thread(run_gen)
            local_path = gen_result.get("local_path")
            video_name = gen_result.get("video_name")

            if not local_path or not Path(local_path).is_file():
                raise RuntimeError(f"Video generation succeeded but local downloaded file missing: {local_path}")

            # Upload video back to Master AssetHub
            hub_record = await self._upload_result_to_hub(
                file_path=Path(local_path),
                name=video_name or "video",
                kind=AssetKind.VIDEO,
                job_id=task.job_id,
            )

            produced = [
                flow_pb2.AssetInfo(
                    name=video_name or "video",
                    kind="video",
                    local_path=str(local_path),
                )
            ]
            return {"video_name": video_name or "video", "asset_hub": hub_record}, produced

        else:
            raise NotImplementedError(f"Unsupported task type on worker: {task_type}")
