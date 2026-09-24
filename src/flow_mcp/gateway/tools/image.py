"""Image generation and management MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from flow_mcp.browser.session import get_browser
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.models.params import ImageCreateByUploadParams, ImageCreateParams
from flow_mcp.pages.image_page import ImagePage
from flow_mcp.services.image_character_service import ImageCharacterService


def register_image_tools(
    mcp: FastMCP,
    image_service: ImageCharacterService,
    job_registry: JobRegistry,
    project_dao: ProjectDAO,
) -> None:
    """Register image-related MCP tools."""

    @mcp.tool(name="image_create", description="Create an image using Google Flow text-to-image")
    async def image_create(
        prompt: str,
        project_name: str = "default",
        aspect_ratio: str = "16:9",
        model_name: str = "Nano Banana Pro",
        quantity: int = 1,
        image_name: str = "",
        assets: str = "",
        download: str = "2K",
    ) -> dict[str, Any]:
        """Submit text-to-image task."""
        params = ImageCreateParams(
            project_name=project_name,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            model_name=model_name,
            quantity=quantity,
            image_name=image_name,
            assets=assets,
            download=download,
        )
        job_id = await image_service.create_image(params)
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Image generation task submitted. Poll image_status(job_id) for progress.",
            "next_action": f"Call image_status(job_id='{job_id}') to check status.",
        }

    @mcp.tool(name="image_create_by_upload", description="Upload a local image file into Google Flow project")
    async def image_create_by_upload(
        image_path: str,
        project_name: str = "default",
        image_name: str = "",
    ) -> dict[str, Any]:
        """Submit image upload task."""
        params = ImageCreateByUploadParams(
            project_name=project_name,
            image_path=image_path,
            image_name=image_name,
        )
        job_id = await image_service.create_image_by_upload(params)
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Image upload task submitted. Poll image_status(job_id) for progress.",
        }

    @mcp.tool(name="image_status", description="Query progress and results of an image task")
    async def image_status(job_id: str) -> dict[str, Any]:
        """Query real-time status of an image job."""
        status = await job_registry.get_status(job_id)
        if not status:
            return {"status": "not_found", "message": f"Job '{job_id}' not found."}
        return status.model_dump()

    @mcp.tool(name="image_list", description="List all images in a Google Flow project")
    async def image_list(project_name: str = "default") -> dict[str, Any]:
        """List images in project."""
        local_uuid = await project_dao.get_local_uuid(project_name, "master_local_worker")
        url = ""
        if local_uuid:
            from flow_mcp.config import get_settings
            url = f"{get_settings().google_flow_base_url}/project/{local_uuid}"

        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        img_page = ImagePage(tab)
        images = img_page.list_images(project_url=url)
        return {
            "status": "success",
            "project_name": project_name,
            "count": len(images),
            "images": images,
        }
