"""Character creation and management MCP tools."""
from __future__ import annotations

from typing import Any, Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

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
        character_name: Annotated[str, Field(description="要创建的虚拟角色名称")],
        prompt: Annotated[str, Field(description="生成角色头像（肖像）的提示词。必须严格使用全英文并且遵守官方模板，若要生成全身像，需保持描述主体的一致性。")],
        project_name: Annotated[str, Field(description="Google Flow 项目的名称，留空则自动选用最近访问的项目")] = "default",
        model_name: Annotated[str, Field(description="用于生成图片的模型名称")] = "Nano banana pro",
        full_body: Annotated[bool, Field(description="是否一并生成角色的全身像")] = False,
    ) -> dict[str, Any]:
        """
        在 Google Flow 中创建一个新的虚拟角色，并为其生成头像、全身像等。
        
        注意：
        1. 由于生成过程需要几分钟，此工具会在后台启动任务，并立即返回一个 job_id。
        2. 若当前已有生成任务进行中，该任务将自动进入全局排队队列。
        3. 你**必须**使用 `character_status` 工具轮询这个 job_id 来获取最终的生成结果。
        """
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
        character_name: Annotated[str, Field(description="要创建的虚拟角色名称（必填项）。如果名称中包含空格，系统会自动将空格统一转换为下划线 '_' 进行保存")],
        portrait_image_path: Annotated[str, Field(description="头像图片的本地绝对路径")],
        project_name: Annotated[str, Field(description="Google Flow 项目的名称，留空则自动选用最近访问的项目")] = "default",
        full_body_image_path: Annotated[str, Field(description="全身像图片的本地绝对路径（可选），若提供则上传全身像")] = "",
    ) -> dict[str, Any]:
        """
        通过上传本地已有图片在 Google Flow 中创建一个新的虚拟角色（头像必传，全身像选传）。
        
        特性与流程说明：
        1. 角色名称规范：角色名称为必填项。传入的角色名称中所有的空格均会自动统一转换为下划线 '_' 进行命名与保存。
        2. 异步排队机制：任务接入后台任务队列统一串行调度，立即返回 job_id，请使用 `character_status` 工具轮询执行结果。
        """
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
        """
        查询 Google Flow 后台角色生成任务的当前状态与生成结果。
        
        状态说明：
        - pending/generating: 生成中（is_finished=False），必须继续轮询。
        - completed/error: 完成或出错（is_finished=True），停止轮询。
        """
        status = await job_registry.get_status(job_id)
        if not status:
            return {"status": "not_found", "message": f"Job '{job_id}' not found."}
        return status.model_dump()

    @mcp.tool(name="character_list", description="List all characters in a Google Flow project")
    async def character_list(
        project_name: Annotated[str, Field(description="Google Flow 项目的名称。留空则自动从浏览器当前所在的项目页面中提取")] = "default"
    ) -> dict[str, Any]:
        """
        查看并列出 Google Flow 项目中的所有角色。
        若传入 project_name，则自动定位/跳转至该项目页面；若留空，则直接查看当前正在浏览器中打开的项目。
        """
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
