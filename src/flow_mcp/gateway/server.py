"""FastMCP Gateway Server: Tool registration and Master cluster entrypoint."""
from __future__ import annotations

import asyncio
from mcp.server.fastmcp import FastMCP
from loguru import logger

from flow_mcp.config import get_settings
from flow_mcp.control.asset_hub import AssetHub
from flow_mcp.control.credit_manager import CreditManager
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.control.scheduler import Scheduler
from flow_mcp.control.server import MasterServer
from flow_mcp.control.worker_pool import WorkerPool
from flow_mcp.db.account_dao import AccountDAO
from flow_mcp.db.asset_dao import AssetDAO
from flow_mcp.db.connection import init_db
from flow_mcp.db.job_dao import JobDAO
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.gateway.tools.character import register_character_tools
from flow_mcp.gateway.tools.image import register_image_tools
from flow_mcp.gateway.tools.project import register_project_tools
from flow_mcp.gateway.tools.queue import register_queue_tools
from flow_mcp.gateway.tools.video import register_video_tools
from flow_mcp.local.local_executor import LocalExecutor
from flow_mcp.models.job import JobPhase, JobSpec, TaskType
from flow_mcp.models.params import VideoCreateParams
from flow_mcp.services.image_character_service import ImageCharacterService
from flow_mcp.services.video_service import VideoService


class FlowMCPGateway:
    """Encapsulates FastMCP server and Master cluster subsystems."""

    def __init__(self):
        self.mcp = FastMCP(
            name="flow-mcp",
            instructions="Google Agentspace Flow cluster-native media automation service.",
        )
        self.settings = get_settings()

        # Database DAOs
        self.job_dao = JobDAO()
        self.account_dao = AccountDAO()
        self.project_dao = ProjectDAO()
        self.asset_dao = AssetDAO()

        # Control Plane subsystems
        self.asset_hub = AssetHub(self.asset_dao)
        self.job_registry = JobRegistry(self.job_dao)
        self.credit_manager = CreditManager(self.account_dao)
        self.worker_pool = WorkerPool()
        self.scheduler = Scheduler(
            worker_pool=self.worker_pool,
            job_registry=self.job_registry,
            credit_manager=self.credit_manager,
        )

        self.local_executor = LocalExecutor(project_dao=self.project_dao)

        self.master_server = MasterServer(
            worker_pool=self.worker_pool,
            job_registry=self.job_registry,
            scheduler=self.scheduler,
            credit_manager=self.credit_manager,
            asset_hub=self.asset_hub,
            project_dao=self.project_dao,
        )

        # Application Services
        self.image_character_service = ImageCharacterService(
            local_executor=self.local_executor,
            scheduler=self.scheduler,
            asset_hub=self.asset_hub,
            worker_pool=self.worker_pool,
            job_registry=self.job_registry,
        )
        self.video_service = VideoService(
            scheduler=self.scheduler,
            job_registry=self.job_registry,
        )

        self._register_all_tools()

    def _register_all_tools(self) -> None:
        """Register all modular MCP tools."""
        register_project_tools(self.mcp, self.project_dao)
        register_image_tools(
            self.mcp,
            self.image_character_service,
            self.job_registry,
            self.project_dao,
        )
        register_video_tools(
            self.mcp,
            self.video_service,
            self.job_registry,
            self.project_dao,
        )
        register_character_tools(
            self.mcp,
            self.image_character_service,
            self.job_registry,
            self.project_dao,
        )
        register_queue_tools(
            self.mcp,
            self.job_registry,
            self.worker_pool,
            self.credit_manager,
            self.scheduler,
        )

    async def initialize(self) -> None:
        """Initialize database, load jobs, and register Worker 0."""
        await init_db()
        await self.job_registry.initialize()

        # Register Master's Worker 0 in pool
        await self.worker_pool.register_worker(
            worker_id="master_local_worker",
            account="master_local@google.com",
            daily_free=50,
        )

        # Configure local task dispatcher for Worker 0 video tasks
        async def local_dispatch(spec: JobSpec) -> None:
            logger.info(f"Worker 0 executing dispatched task: {spec.job_id}")
            if spec.task_type in (TaskType.VIDEO_CREATE, TaskType.VIDEO_CREATE_BY_UPLOAD):
                params = VideoCreateParams(**spec.params)
                res = await self.local_executor.create_video(spec.project_alias, params)
                local_path = res.get("local_path")
                produced = []
                if local_path:
                    produced = [{"name": res.get("video_name", ""), "kind": "video", "local_path": local_path}]
                await self.scheduler.handle_task_completed(spec.job_id, "master_local_worker", res, produced)
            else:
                logger.warning(f"Unexpected task type for local dispatcher: {spec.task_type}")

        self.scheduler._local_dispatcher = local_dispatch

        # Start background Master network servers (gRPC & HTTP)
        await self.master_server.start()
        logger.info("FlowMCPGateway initialization complete.")

    async def shutdown(self) -> None:
        """Gracefully shutdown Master servers."""
        await self.master_server.stop()
        logger.info("FlowMCPGateway shut down.")

    def run(self, transport: str = "stdio", port: int = 8000) -> None:
        """Run the MCP server."""
        asyncio.run(self.initialize())
        logger.info(f"Running FastMCP server with transport='{transport}'...")
        if transport == "stdio":
            self.mcp.run(transport="stdio")
        else:
            self.mcp.settings.port = port
            self.mcp.run(transport="sse")


def create_gateway() -> FlowMCPGateway:
    """Gateway factory function."""
    return FlowMCPGateway()

