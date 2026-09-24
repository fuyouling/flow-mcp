"""Character creation and management MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from flow_mcp.browser.session import get_browser
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.models.params import CharacterCreateByUploadParams, CharacterCreateParams
from flow_mcp.pages.character_page import CharacterPage
from flow_mcp.services.image_character_service import ImageCharacterService


def register_character_tools(
    mcp: FastMCP,
    image_character_service: ImageCharacterService,
    job_registry: JobRegistry,
    project_dao: ProjectDAO,
) -> None:
    """Register character-related MCP tools."""

    @mcp.tool(name="character_create", description="Create a new character in Google Flow")
    async def character_create(
        character_name: str,
        prompt: str,
        project_name: str = "default",
        model_name: str = "Nano banana pro",
        full_body: bool = False,
    ) -> dict[str, Any]:
        """Submit character creation task."""
        params = CharacterCreateParams(
            project_name=project_name,
            prompt=prompt,
            character_name=character_name,
            model_name=model_name,
            full_body=full_body,
        )
        job_id = await image_character_service.create_character(params)
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Character task submitted. Poll character_status(job_id).",
            "next_action": f"Call character_status(job_id='{job_id}') to check status.",
        }

    @mcp.tool(name="character_create_by_upload", description="Create character by uploading reference portrait/fullbody images")
    async def character_create_by_upload(
        character_name: str,
        portrait_image_path: str,
        project_name: str = "default",
        full_body_image_path: str = "",
    ) -> dict[str, Any]:
        """Submit character upload task."""
        params = CharacterCreateByUploadParams(
            project_name=project_name,
            character_name=character_name,
            portrait_image_path=portrait_image_path,
            full_body_image_path=full_body_image_path,
        )
        job_id = await image_character_service.create_character_by_upload(params)
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Character upload task submitted. Poll character_status(job_id).",
        }

    @mcp.tool(name="character_status", description="Query progress and results of a character task")
    async def character_status(job_id: str) -> dict[str, Any]:
        """Query real-time status of a character job."""
        status = await job_registry.get_status(job_id)
        if not status:
            return {"status": "not_found", "message": f"Job '{job_id}' not found."}
        return status.model_dump()

    @mcp.tool(name="character_list", description="List all characters in a Google Flow project")
    async def character_list(project_name: str = "default") -> dict[str, Any]:
        """List characters in project."""
        local_uuid = await project_dao.get_local_uuid(project_name, "master_local_worker")
        url = ""
        if local_uuid:
            from flow_mcp.config import get_settings
            url = f"{get_settings().google_flow_base_url}/project/{local_uuid}"

        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        char_page = CharacterPage(tab)
        characters = char_page.list_characters(project_url=url)
        return {
            "status": "success",
            "project_name": project_name,
            "count": len(characters),
            "characters": characters,
        }
