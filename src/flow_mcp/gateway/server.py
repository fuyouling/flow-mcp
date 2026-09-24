"""FastMCP Gateway Server: Tool registration and Master cluster entrypoint."""
from __future__ import annotations

import asyncio
import time

from loguru import logger
from mcp.server.fastmcp import FastMCP

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
from flow_mcp.models.job import JobSpec, TaskType
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

        # Inspect local account info from browser for Master
        account_email = ""
        credits_val = None
        try:
            from flow_mcp.browser.session import get_browser
            from flow_mcp.pages.home_page import HomePage

            browser = get_browser()
            home = HomePage(browser.latest_tab)
            home.open()
            account_email = home.get_account_email() or ""
            credits_val = home.get_credits()
        except Exception as e:
            logger.debug(f"Master pre-flight browser inspection note: {e}")

        # Register Master's Worker 0 in pool
        local_account = account_email or self.settings.worker_account or "master_local@google.com"
        await self.worker_pool.register_worker(
            worker_id="master_local_worker",
            account=local_account,
            daily_free=50,
        )
        if local_account:
            await self.credit_manager.update_from_worker(
                worker_id="master_local_worker",
                email=local_account,
                balance=credits_val,
                daily_free=50,
            )

        # Configure local task dispatcher for Worker 0 video tasks
        async def local_dispatch(spec: JobSpec) -> None:
            logger.info(f"Worker 0 executing dispatched task: {spec.job_id}")
            if spec.task_type in (TaskType.VIDEO_CREATE, TaskType.VIDEO_CREATE_BY_UPLOAD):
                params = VideoCreateParams(**spec.params)
                start_time = time.time()
                loop = asyncio.get_running_loop()

                def progress_cb(pct: int, txt: str):
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self.job_registry.update_status(
                                spec.job_id,
                                progress_percent=pct,
                                progress_text=txt,
                                elapsed_seconds=round(time.time() - start_time, 1),
                            ),
                            loop,
                        )
                    except Exception as ex:
                        logger.debug(f"Failed to update video progress for job {spec.job_id}: {ex}")

                res = await self.local_executor.create_video(spec.project_alias, params, progress_cb=progress_cb)
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

    async def run_async(self, transport: str = "stdio", port: int = 8000) -> None:
        """Run Master background services and FastMCP within the same event loop."""
        await self.initialize()
        try:
            logger.info(f"Running FastMCP server with transport='{transport}'...")
            if transport == "stdio":
                await self.mcp.run_stdio_async()
            else:
                self.mcp.settings.port = port
                await self.mcp.run_sse_async()
        finally:
            await self.shutdown()

    def run(self, transport: str = "stdio", port: int = 8000) -> None:
        """Run the MCP server."""
        import anyio

        anyio.run(self.run_async, transport, port)


def create_gateway() -> FlowMCPGateway:
    """Gateway factory function."""
    return FlowMCPGateway()

