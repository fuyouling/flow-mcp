"""Image generation and management MCP tools."""
from __future__ import annotations

from typing import Any, Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

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
        prompt: Annotated[str, Field(description="生成图片的提示词")],
        project_name: Annotated[str, Field(description="Google Flow 项目的名称，留空则自动选用最近访问的项目")] = "default",
        aspect_ratio: Annotated[str, Field(description="图片宽高比，例如 '16:9' 或 '9:16'")] = "16:9",
        model_name: Annotated[str, Field(description="使用的模型名称")] = "Nano Banana Pro",
        quantity: Annotated[int, Field(description="生成的图片数量，通常为 1-4")] = 1,
        image_name: Annotated[str, Field(description="生成后的图片重命名名称，留空则自动生成")] = "",
        assets: Annotated[str, Field(description="可选的参考素材名称，多个用逗号分隔")] = "",
        download: Annotated[str, Field(description="可选下载分辨率，可选 '1K' 或 '2K'，留空则不下载")] = "2K",
    ) -> dict[str, Any]:
        """
        在 Google Flow 中发起后台图片生成任务。

        【重要执行规则与状态轮询机制】
        1. 异步执行与全局队列：本工具在后台异步执行生成任务。由于浏览器单一，全服务所有生成任务（涵盖图片/视频/角色）共用全局单任务队列串行执行。若当前空闲则立即启动；若已有任务在生成中，将自动进入全局排队队列。智能体【严禁】因看到 queued 而重复调用创建工具！
        2. 必须轮询：调用成功后，智能体【必须】使用返回的 job_id 定期调用 image_status 工具查询任务最新进度与最终结果。
        3. 结束判定：智能体必须根据 image_status 返回的 is_finished 字段判定任务是否结束。
        """
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
        image_path: Annotated[str, Field(description="待上传图片的本地绝对路径")],
        project_name: Annotated[str, Field(description="Google Flow 项目的名称，留空则自动选用最近访问的项目")] = "default",
        image_name: Annotated[str, Field(description="上传后的图片重命名名称（必填项）。名称中的所有空格将被自动统一替换为下划线 '_'")] = "",
    ) -> dict[str, Any]:
        """
        通过在项目主页上传本地已有图片创建图片媒体资产并重命名保存。
        
        流程步骤：进入项目首页 -> 点击「添加媒体」-> 自动上传 -> 重命名保存。
        异步排队机制：任务接入后台任务队列，立即返回 job_id，请使用 `image_status` 轮询。
        """
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
        """
        查询 Google Flow 后台图片生成任务的当前状态与生成结果。
        
        核心结束判定依据：is_finished (bool)
        当 is_finished == False：任务仍在处理中，智能体【绝不能】停止轮询，必须等待 5 秒后继续查询。
        当 is_finished == True：任务已彻底完成或出错。智能体【必须停止轮询】并汇报结果。
        """
        status = await job_registry.get_status(job_id)
        if not status:
            return {"status": "not_found", "message": f"Job '{job_id}' not found."}
        return status.model_dump()

    @mcp.tool(name="image_list", description="List all images in a Google Flow project")
    async def image_list(
        project_name: Annotated[str, Field(description="Google Flow 项目的名称。留空则自动从浏览器当前所在的项目页面中提取")] = "default"
    ) -> dict[str, Any]:
        """
        查看并列出 Google Flow 项目中的所有图片。
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
        img_page = ImagePage(tab)
        images = img_page.list_images(project_url=url)
        return {
            "status": "success",
            "project_name": project_name,
            "count": len(images),
            "images": images,
        }
