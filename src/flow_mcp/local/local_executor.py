"""LocalExecutor: Direct browser automation on Master node (Worker 0)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from flow_mcp.browser.session import get_browser
from flow_mcp.config import get_settings
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.models.params import (
    CharacterCreateByUploadParams,
    CharacterCreateParams,
    ImageCreateByUploadParams,
    ImageCreateParams,
    VideoCreateParams,
)
from flow_mcp.pages.character_page import CharacterPage
from flow_mcp.pages.home_page import HomePage
from flow_mcp.pages.image_page import ImagePage
from flow_mcp.pages.video_page import VideoPage


class LocalExecutor:
    """
    Executes browser actions locally on Master (Worker 0).
    Directly drives Chromium via Page Objects without network overhead.
    """

    def __init__(self, project_dao: ProjectDAO | None = None, worker_id: str = "master_local_worker"):
        self.project_dao = project_dao or ProjectDAO()
        self.worker_id = worker_id

    async def ensure_project_url(self, project_alias: str, force_sync: bool = False) -> str:
        """
        Resolve project alias to Flow project URL on this node.
        If project does not exist on Flow, creates and renames it.
        """
        settings = get_settings()
        base_url = settings.google_flow_base_url

        if not force_sync:
            existing_uuid = await self.project_dao.get_local_uuid(project_alias, self.worker_id)
            if existing_uuid:
                return f"{base_url}/project/{existing_uuid}"

        # Drive browser to inspect/create project
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        home = HomePage(tab)
        home.open()

        projects = home.get_projects()
        if project_alias in projects:
            local_uuid = projects[project_alias]["local_uuid"]
            await self.project_dao.upsert_project(project_alias, self.worker_id, local_uuid)
            return f"{base_url}/project/{local_uuid}"

        # Create new project
        logger.info(f"Project '{project_alias}' not found on Worker 0, creating new project...")
        new_uuid = home.create_project()
        home.open()
        home.rename_project(new_title=project_alias, project_uuid=new_uuid)

        await self.project_dao.upsert_project(project_alias, self.worker_id, new_uuid)
        return f"{base_url}/project/{new_uuid}"

    async def create_image(
        self,
        project_alias: str,
        params: ImageCreateParams,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, Any]:
        """Execute text-to-image creation locally on Worker 0."""
        project_url = await self.ensure_project_url(project_alias)
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        img_page = ImagePage(tab)

        def run_sync():
            assets_list = [a.strip() for a in params.assets.split(",") if a.strip()] if params.assets else None
            return img_page.generate_image(
                project_url=project_url,
                prompt=params.prompt,
                aspect_ratio=params.aspect_ratio,
                model_name=params.model_name,
                quantity=f"x{params.quantity}",
                assets=assets_list,
                rename_name=params.image_name or "",
                download=params.download,
                progress_callback=progress_cb,
            )

        return await asyncio.to_thread(run_sync)

    async def create_image_by_upload(
        self,
        project_alias: str,
        params: ImageCreateByUploadParams,
    ) -> dict[str, Any]:
        """Upload image to project locally on Worker 0."""
        project_url = await self.ensure_project_url(project_alias)
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        img_page = ImagePage(tab)

        def run_sync():
            img_page.upload_image_on_project_page(
                project_url=project_url,
                image_path=params.image_path,
                target_name=params.image_name or "",
            )
            return {"image_name": params.image_name or Path(params.image_path).stem}

        return await asyncio.to_thread(run_sync)

    async def create_character(
        self,
        project_alias: str,
        params: CharacterCreateParams,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, Any]:
        """Create character (portrait + optional fullbody) locally on Worker 0."""
        project_url = await self.ensure_project_url(project_alias)
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        char_page = CharacterPage(tab)

        def run_sync():
            char_page.navigate_to_characters(project_url)
            char_page.click_new_character()

            portrait_b64 = char_page.generate_portrait(params.prompt, params.model_name)
            char_page.rename_character(params.character_name)
            portrait_path = char_page.download_character_image(f"{params.character_name}_Portrait")

            fullbody_path = ""
            if params.full_body:
                char_page.generate_fullbody(params.prompt, params.model_name)
                fullbody_path = char_page.download_character_image(f"{params.character_name}_Fullbody") or ""

            char_page.save_character()
            return {
                "character_name": params.character_name,
                "portrait_path": portrait_path or "",
                "fullbody_path": fullbody_path,
                "portrait_b64": portrait_b64,
            }

        return await asyncio.to_thread(run_sync)

    async def create_character_by_upload(
        self,
        project_alias: str,
        params: CharacterCreateByUploadParams,
    ) -> dict[str, Any]:
        """Create character by uploading reference images locally on Worker 0."""
        project_url = await self.ensure_project_url(project_alias)
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        char_page = CharacterPage(tab)

        def run_sync():
            char_page.navigate_to_characters(project_url)
            char_page.click_new_character()
            char_page.upload_portrait(params.portrait_image_path)
            char_page.rename_character(params.character_name)
            portrait_path = char_page.download_character_image(f"{params.character_name}_Portrait")

            fullbody_path = ""
            if params.full_body_image_path:
                char_page.upload_portrait(params.full_body_image_path)
                fullbody_path = char_page.download_character_image(f"{params.character_name}_Fullbody") or ""

            char_page.save_character()
            return {
                "character_name": params.character_name,
                "portrait_path": portrait_path or "",
                "fullbody_path": fullbody_path,
            }

        return await asyncio.to_thread(run_sync)

    async def create_video(
        self,
        project_alias: str,
        params: VideoCreateParams,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, Any]:
        """Execute video creation locally on Worker 0."""
        project_url = await self.ensure_project_url(project_alias)
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        vid_page = VideoPage(tab)

        def run_sync():
            assets_list = [a.strip() for a in params.assets.split(",") if a.strip()] if params.assets else None
            return vid_page.generate_video(
                project_url=project_url,
                prompt=params.prompt,
                model_name=params.model_name,
                mode=params.mode,
                start_frame=params.start_frame,
                end_frame=params.end_frame,
                aspect_ratio=params.aspect_ratio,
                resolution=params.resolution,
                duration=params.duration,
                quantity=f"x{params.quantity}",
                assets=assets_list,
                rename_name=params.video_name or "",
                download=params.download,
                progress_callback=progress_cb,
            )

        return await asyncio.to_thread(run_sync)

    async def get_current_credits(self) -> int | None:
        """Fetch credits from Worker 0 browser."""
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        home = HomePage(tab)
        home.open()
        return home.get_credits()
