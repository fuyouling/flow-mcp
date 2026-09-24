"""Video generation and management MCP tools."""
from __future__ import annotations

from typing import Any, Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

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
        prompt: Annotated[str, Field(description="视频生成的提示词 (Prompt)，详细描述视频画面、主体动作、镜头运镜及光影风格")],
        project_name: Annotated[str, Field(description="Google Flow 项目的名称，视频将创建在该项目内。留空则自动使用最近访问的项目")] = "default",
        model_name: Annotated[str, Field(description="生成视频的模型名称。可选: 'Omni 1.1 Flash', 'Veo 3.1 - Lite', 'Veo 3.1 - Fast', 'Veo 3.1 - Quality' (Veo 模型在素材模式下添加素材不会被模型引用)")] = "Omni 1.1 Flash",
        mode: Annotated[str, Field(description="生成模式: 'asset' (素材参考/纯文本模式) 或 'frame' (首尾帧模式)")] = "asset",
        start_frame: Annotated[str, Field(description="[仅帧模式] 首帧图片名称，必须为该项目中已存在的图片资源")] = "",
        end_frame: Annotated[str, Field(description="[仅帧模式] 尾帧图片名称，必须为该项目中已存在的图片资源")] = "",
        aspect_ratio: Annotated[str, Field(description="视频宽高比: '16:9' 或 '9:16'")] = "16:9",
        resolution: Annotated[str, Field(description="视频分辨率 (仅 Omni 1.1 Flash 模型生效): 可选 '360p' 或 '720p'")] = "720p",
        duration: Annotated[int, Field(description="视频时长，单位为秒 (仅 Omni 1.1 Flash 模型生效)")] = 8,
        quantity: Annotated[int, Field(description="单次并发生成的视频数量: 可选 1, 2, 3, 4")] = 1,
        assets: Annotated[str, Field(description="[仅素材模式] 逗号分隔的参考素材名称列表。仅 Omni 1.1 Flash 模型支持引用素材")] = "",
        video_name: Annotated[str, Field(description="生成的视频重命名名称，便于在项目素材库中检索与引用。留空则自动生成")] = "",
        download: Annotated[str, Field(description="可选下载清晰度: '270p', '720p', '1080p'。指定后将自动下载至本地目录，留空则不下载")] = "720p",
    ) -> dict[str, Any]:
        """
        在 Google Flow 中发起后台视频生成任务。

        【一、 核心工作流与异步架构】
        1. 异步执行：在后台异步执行生成任务。若当前空闲则立即启动；若有任务在生成中，将自动进入全局排队队列。智能体【严禁】因看到 queued 而重复调用创建工具！
        2. 状态轮询：智能体【必须】使用返回的 job_id 定期调用 video_status 工具轮询状态。
        3. 结束判定：必须根据 video_status 返回的 is_finished 判定任务是否结束，严禁提前下结论。

        【二、 生成模式】
        1. mode='asset'：纯文本生视频，或通过 assets 引用素材。注意 Veo 模型不支持引用素材！
        2. mode='frame'：首尾帧模式，需提供 start_frame 和 end_frame。
        """
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
        video_path: Annotated[str, Field(description="待上传视频的本地绝对路径")],
        project_name: Annotated[str, Field(description="Google Flow 项目的名称，留空则自动选用最近访问的项目")] = "default",
        video_name: Annotated[str, Field(description="上传后的视频重命名名称（必填项）。名称中的所有空格将被自动统一替换为下划线 '_'")] = "",
    ) -> dict[str, Any]:
        """
        通过在项目主页上传本地已有视频文件创建视频媒体资产并重命名保存。
        
        流程步骤：进入项目首页 -> 点击「添加媒体」-> 自动上传 -> 重命名保存。
        异步排队机制：任务接入后台任务队列，立即返回 job_id，请使用 `video_status` 轮询。
        """
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
        """
        查询 Google Flow 后台视频生成任务的当前状态与生成结果。
        
        核心结束判定依据：is_finished (bool)
        当 is_finished == False：任务仍在处理中，智能体【绝不能】停止轮询，必须等待 5~10 秒后继续查询。
        当 is_finished == True：任务已彻底完成或出错。智能体【必须停止轮询】并汇报结果。
        """
        status = await job_registry.get_status(job_id)
        if not status:
            return {"status": "not_found", "message": f"Job '{job_id}' not found."}
        return status.model_dump()

    @mcp.tool(name="video_list", description="List all videos in a Google Flow project")
    async def video_list(
        project_name: Annotated[str, Field(description="Google Flow 项目的名称。留空则自动从浏览器当前所在的项目页面中提取")] = "default"
    ) -> dict[str, Any]:
        """
        查看并列出 Google Flow 项目中的所有视频。
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
        vid_page = VideoPage(tab)
        videos = vid_page.list_videos(project_url=url)
        return {
            "status": "success",
            "project_name": project_name,
            "count": len(videos),
            "videos": videos,
        }
