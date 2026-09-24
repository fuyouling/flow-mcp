"""Video generation and management MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from flow_mcp.browser.session import get_browser
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.models.params import VideoCreateByUploadParams, VideoCreateParams
from flow_mcp.pages.video_page import VideoPage
from flow_mcp.services.video_service import VideoService


def register_video_tools(
    mcp: FastMCP,
    video_service: VideoService,
    job_registry: JobRegistry,
    project_dao: ProjectDAO,
) -> None:
    """Register video-related MCP tools."""

    @mcp.tool(name="video_create", description="Create a video using Google Flow (routed by credit priority)")
    async def video_create(
        prompt: str,
        project_name: str = "default",
        model_name: str = "Omni 1.1 Flash",
        mode: str = "asset",
        start_frame: str = "",
        end_frame: str = "",
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        duration: int = 8,
        quantity: int = 1,
        assets: str = "",
        video_name: str = "",
        download: str = "720p",
    ) -> dict[str, Any]:
        """Submit video creation task."""
        params = VideoCreateParams(
            project_name=project_name,
            prompt=prompt,
            model_name=model_name,
            mode=mode,
            start_frame=start_frame,
            end_frame=end_frame,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            duration=duration,
            quantity=quantity,
            assets=assets,
            video_name=video_name,
            download=download,
        )
        job_id = await video_service.create_video(params)
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Video task submitted and queued for best worker. Poll video_status(job_id).",
            "next_action": f"Call video_status(job_id='{job_id}') to check status.",
        }

    @mcp.tool(name="video_create_by_upload", description="Create a video from reference uploaded media")
    async def video_create_by_upload(
        video_path: str,
        project_name: str = "default",
        video_name: str = "",
    ) -> dict[str, Any]:
        """Submit video upload task."""
        params = VideoCreateByUploadParams(
            project_name=project_name,
            video_path=video_path,
            video_name=video_name,
        )
        job_id = await video_service.create_video_by_upload(params)
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Video upload task submitted. Poll video_status(job_id).",
        }

    @mcp.tool(name="video_status", description="Query progress and results of a video task")
    async def video_status(job_id: str) -> dict[str, Any]:
        """Query real-time status of a video job."""
        status = await job_registry.get_status(job_id)
        if not status:
            return {"status": "not_found", "message": f"Job '{job_id}' not found."}
        return status.model_dump()

    @mcp.tool(name="video_list", description="List all videos in a Google Flow project")
    async def video_list(project_name: str = "default") -> dict[str, Any]:
        """List videos in project."""
        local_uuid = await project_dao.get_local_uuid(project_name, "master_local_worker")
        url = ""
        if local_uuid:
            from flow_mcp.config import get_settings
            url = f"{get_settings().google_flow_base_url}/project/{local_uuid}"

        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        vid_page = VideoPage(tab)
        videos = vid_page.list_videos(project_url=url)
        return {
            "status": "success",
            "project_name": project_name,
            "count": len(videos),
            "videos": videos,
        }
