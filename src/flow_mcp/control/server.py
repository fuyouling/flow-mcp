"""Master Network Server: Hosting gRPC Task Streaming and FastAPI Asset/Status HTTP endpoints."""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
from typing import AsyncGenerator
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
import grpc
from grpc import aio as grpc_aio
from google.protobuf.json_format import MessageToDict
from loguru import logger
import uvicorn

from flow_mcp.config import get_settings
from flow_mcp.control.asset_hub import AssetHub
from flow_mcp.control.credit_manager import CreditManager
from flow_mcp.control.job_registry import JobRegistry
from flow_mcp.control.scheduler import Scheduler
from flow_mcp.control.worker_pool import WorkerPool
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.models.asset import AssetKind
from flow_mcp.models.job import JobPhase
from flow_mcp.proto import flow_pb2, flow_pb2_grpc


class FlowClusterServicer(flow_pb2_grpc.FlowClusterServicer):
    """gRPC service implementation for bidirectional task streaming with remote workers."""

    def __init__(
        self,
        worker_pool: WorkerPool,
        job_registry: JobRegistry,
        scheduler: Scheduler,
        credit_manager: CreditManager,
        project_dao: ProjectDAO,
    ):
        self.worker_pool = worker_pool
        self.job_registry = job_registry
        self.scheduler = scheduler
        self.credit_manager = credit_manager
        self.project_dao = project_dao
        self._worker_queues: dict[str, asyncio.Queue[flow_pb2.MasterMessage]] = {}
        self._active_connections: set[str] = set()

    async def send_to_worker(self, worker_id: str, message: flow_pb2.MasterMessage) -> bool:
        """Enqueue message to worker's outgoing gRPC stream."""
        q = self._worker_queues.get(worker_id)
        if not q:
            logger.warning(f"Cannot send to worker {worker_id}: no active gRPC queue.")
            return False
        await q.put(message)
        return True

    async def StreamTasks(
        self,
        request_iterator: AsyncGenerator[flow_pb2.WorkerMessage, None],
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[flow_pb2.MasterMessage, None]:
        """Bidirectional stream handler."""
        worker_id: str | None = None
        out_queue: asyncio.Queue[flow_pb2.MasterMessage] = asyncio.Queue()

        async def reader():
            nonlocal worker_id
            try:
                async for msg in request_iterator:
                    payload_type = msg.WhichOneof("payload")
                    if payload_type == "register":
                        req = msg.register
                        worker_id = req.worker_id
                        self._worker_queues[worker_id] = out_queue
                        self._active_connections.add(worker_id)

                        mappings = dict(req.project_mappings)
                        cached = list(req.cached_assets)

                        await self.worker_pool.register_worker(
                            worker_id=worker_id,
                            account=req.account,
                            project_mappings=mappings,
                            cached_assets=cached,
                        )

                        for alias, uuid in mappings.items():
                            await self.project_dao.upsert_project(alias, worker_id, uuid)

                        # Send ACK
                        ack = flow_pb2.MasterMessage(
                            ack=flow_pb2.RegisterAck(worker_id=worker_id, success=True)
                        )
                        await out_queue.put(ack)
                        logger.info(f"Worker {worker_id} connected and registered via gRPC.")

                    elif payload_type == "heartbeat":
                        if worker_id:
                            await self.worker_pool.heartbeat(worker_id)

                    elif payload_type == "progress":
                        p = msg.progress
                        await self.job_registry.update_status(
                            p.job_id,
                            phase=JobPhase(p.phase) if p.phase else JobPhase.ASSIGNED,
                            progress_percent=p.progress_percent,
                            progress_text=p.progress_text,
                            elapsed_seconds=p.elapsed_seconds,
                            message=p.message,
                        )

                    elif payload_type == "completed":
                        c = msg.completed
                        res_dict = MessageToDict(c.result)
                        produced = [
                            {"name": a.name, "kind": a.kind, "local_path": a.local_path}
                            for a in c.produced_assets
                        ]
                        await self.scheduler.handle_task_completed(
                            job_id=c.job_id,
                            worker_id=c.worker_id,
                            result=res_dict,
                            produced_assets=produced,
                        )

                    elif payload_type == "failed":
                        f = msg.failed
                        await self.scheduler.handle_task_failed(
                            job_id=f.job_id,
                            worker_id=f.worker_id,
                            error=f.error,
                        )

                    elif payload_type == "project_mapping":
                        pm = msg.project_mapping
                        await self.project_dao.upsert_project(pm.project_alias, pm.worker_id, pm.local_uuid)
                        await self.worker_pool.update_project_mapping(pm.worker_id, pm.project_alias, pm.local_uuid)

                    elif payload_type == "account_update":
                        au = msg.account_update
                        bal = au.balance if au.HasField("balance") else None
                        free = au.daily_free if au.HasField("daily_free") else None
                        await self.credit_manager.update_from_worker(
                            worker_id=au.worker_id,
                            email=au.email,
                            balance=bal,
                            daily_free=free,
                        )
                        await self.worker_pool.update_account_credits(au.worker_id, daily_free=free, balance=bal)

            except Exception as e:
                logger.warning(f"gRPC stream read error for worker {worker_id}: {e}")
            finally:
                if worker_id:
                    self._worker_queues.pop(worker_id, None)
                    self._active_connections.discard(worker_id)
                    logger.info(f"Worker {worker_id} gRPC stream closed.")

        read_task = asyncio.create_task(reader())

        try:
            while True:
                out_msg = await out_queue.get()
                yield out_msg
        except asyncio.CancelledError:
            pass
        finally:
            read_task.cancel()
            try:
                await read_task
            except asyncio.CancelledError:
                pass


def create_http_app(
    asset_hub: AssetHub,
    worker_pool: WorkerPool,
    job_registry: JobRegistry,
    credit_manager: CreditManager,
) -> FastAPI:
    """Create FastAPI application for asset download/upload and cluster metrics."""
    app = FastAPI(title="Flow MCP Master HTTP API", version="1.0.0")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/status")
    async def status():
        workers = await worker_pool.list_workers()
        active_jobs = await job_registry.list_active_jobs()
        accounts = await credit_manager.list_accounts()
        return {
            "workers_count": len(workers),
            "workers": [w.model_dump() for w in workers],
            "active_jobs_count": len(active_jobs),
            "active_jobs": [j.model_dump() for j in active_jobs],
            "accounts": [a.model_dump() for a in accounts],
        }

    @app.get("/assets/{name}")
    async def download_asset(name: str):
        try:
            file_path = await asset_hub.get_file_path(name)
            return FileResponse(path=str(file_path), filename=file_path.name)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/assets/upload")
    async def upload_asset(
        file: UploadFile = File(...),
        name: str = Form(...),
        kind: str = Form("video"),
        worker_id: str = Form(""),
        job_id: str = Form(""),
    ):
        try:
            asset_kind = AssetKind(kind)
            # Write to temporary file first
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "").suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            record = await asset_hub.store_asset(
                source_path=tmp_path,
                name=name,
                kind=asset_kind,
                created_by_worker=worker_id,
                source_job_id=job_id,
            )
            tmp_path.unlink(missing_ok=True)
            return record.model_dump()
        except Exception as e:
            logger.error(f"Asset upload error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app


class MasterServer:
    """
    Unified Master server orchestrating gRPC service and FastAPI HTTP endpoints.
    """

    def __init__(
        self,
        worker_pool: WorkerPool,
        job_registry: JobRegistry,
        scheduler: Scheduler,
        credit_manager: CreditManager,
        asset_hub: AssetHub,
        project_dao: ProjectDAO,
        host: str | None = None,
        grpc_port: int | None = None,
        http_port: int | None = None,
    ):
        self.worker_pool = worker_pool
        self.job_registry = job_registry
        self.scheduler = scheduler
        self.credit_manager = credit_manager
        self.asset_hub = asset_hub
        self.project_dao = project_dao

        settings = get_settings()
        self.host = host or settings.master_host
        self.grpc_port = grpc_port or settings.master_grpc_port
        self.http_port = http_port or settings.master_http_port

        self.servicer = FlowClusterServicer(
            worker_pool=self.worker_pool,
            job_registry=self.job_registry,
            scheduler=self.scheduler,
            credit_manager=self.credit_manager,
            project_dao=self.project_dao,
        )
        self.http_app = create_http_app(
            asset_hub=self.asset_hub,
            worker_pool=self.worker_pool,
            job_registry=self.job_registry,
            credit_manager=self.credit_manager,
        )

        self._grpc_server: grpc_aio.Server | None = None
        self._uvicorn_server: uvicorn.Server | None = None

    async def start(self) -> None:
        """Start gRPC and HTTP servers concurrently in the running asyncio loop."""
        # Connect remote dispatcher
        async def remote_dispatch(worker_id: str, task: flow_pb2.ExecuteTask) -> bool:
            return await self.servicer.send_to_worker(
                worker_id, flow_pb2.MasterMessage(execute=task)
            )

        self.scheduler._remote_dispatcher = remote_dispatch
        await self.scheduler.start()

        # 1. Start gRPC server
        self._grpc_server = grpc_aio.server()
        flow_pb2_grpc.add_FlowClusterServicer_to_server(self.servicer, self._grpc_server)
        grpc_addr = f"{self.host}:{self.grpc_port}"
        self._grpc_server.add_insecure_port(grpc_addr)
        await self._grpc_server.start()
        logger.info(f"Master gRPC server running at {grpc_addr}")

        # 2. Start HTTP server
        config = uvicorn.Config(
            app=self.http_app,
            host=self.host,
            port=self.http_port,
            log_level="warning",
        )
        self._uvicorn_server = uvicorn.Server(config)
        asyncio.create_task(self._uvicorn_server.serve())
        logger.info(f"Master HTTP server running at http://{self.host}:{self.http_port}")

    async def stop(self) -> None:
        """Stop all servers and scheduler."""
        await self.scheduler.stop()
        if self._grpc_server:
            await self._grpc_server.stop(grace=0.5)
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
        logger.info("MasterServer stopped.")
