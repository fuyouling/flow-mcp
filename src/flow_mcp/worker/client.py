"""WorkerClient: gRPC streaming client for connecting to Master and executing tasks."""
from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator
from google.protobuf.struct_pb2 import Struct
import grpc
from grpc import aio as grpc_aio
from loguru import logger

from flow_mcp.browser.session import get_browser
from flow_mcp.config import get_settings
from flow_mcp.pages.home_page import HomePage
from flow_mcp.proto import flow_pb2, flow_pb2_grpc
from flow_mcp.worker.executor import WorkerExecutor


class WorkerClient:
    """
    gRPC Client running on Worker node: maintains persistent bidirectional stream to Master.
    """

    def __init__(
        self,
        worker_id: str | None = None,
        master_grpc_target: str | None = None,
        master_http_url: str | None = None,
        heartbeat_interval: float = 10.0,
    ):
        settings = get_settings()
        self.worker_id = worker_id or settings.worker_id
        self.master_grpc_target = master_grpc_target or settings.master_grpc_target
        self.master_http_url = master_http_url or settings.master_http_url
        self.heartbeat_interval = heartbeat_interval

        self.executor = WorkerExecutor(
            worker_id=self.worker_id,
            master_http_url=self.master_http_url,
        )

        self._running = False
        self._out_queue: asyncio.Queue[flow_pb2.WorkerMessage] = asyncio.Queue()
        self._current_task_handle: asyncio.Task | None = None

    async def start(self) -> None:
        """Start worker client connection and reconnection loop."""
        self._running = True
        logger.info(f"Starting WorkerClient '{self.worker_id}' targeting {self.master_grpc_target}")

        while self._running:
            try:
                await self._run_stream()
            except Exception as e:
                logger.warning(f"Worker stream disconnected ({e}), reconnecting in 3s...")
                await asyncio.sleep(3.0)

    async def stop(self) -> None:
        """Stop worker client."""
        self._running = False
        if self._current_task_handle:
            self._current_task_handle.cancel()
        logger.info(f"WorkerClient '{self.worker_id}' stopped.")

    async def _run_stream(self) -> None:
        """Establish bidirectional gRPC stream."""
        # Inspect local account info from browser
        account_email = ""
        credits_val = None
        try:
            browser = get_browser()
            home = HomePage(browser.latest_tab)
            home.open()
            account_email = home.get_account_email() or ""
            credits_val = home.get_credits()
            projects = home.get_projects()
            self.executor.project_mappings = {name: p["local_uuid"] for name, p in projects.items()}
        except Exception as e:
            logger.debug(f"Pre-flight browser inspection note: {e}")

        async with grpc_aio.insecure_channel(self.master_grpc_target) as channel:
            stub = flow_pb2_grpc.FlowClusterStub(channel)

            # Send registration
            reg_msg = flow_pb2.WorkerMessage(
                register=flow_pb2.RegisterRequest(
                    worker_id=self.worker_id,
                    account=account_email,
                    project_mappings=self.executor.project_mappings,
                    cached_assets=list(self.executor.cached_assets),
                )
            )
            await self._out_queue.put(reg_msg)

            # Send initial credits update if found
            if credits_val is not None:
                acct_msg = flow_pb2.WorkerMessage(
                    account_update=flow_pb2.AccountUpdate(
                        worker_id=self.worker_id,
                        email=account_email,
                        balance=credits_val,
                    )
                )
                await self._out_queue.put(acct_msg)

            # Start heartbeat loop
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            async def request_generator() -> AsyncGenerator[flow_pb2.WorkerMessage, None]:
                while self._running:
                    msg = await self._out_queue.get()
                    yield msg

            try:
                call = stub.StreamTasks(request_generator())
                async for master_msg in call:
                    payload_type = master_msg.WhichOneof("payload")

                    if payload_type == "ack":
                        logger.info(f"Worker {self.worker_id} registered successfully with Master.")

                    elif payload_type == "execute":
                        task = master_msg.execute
                        logger.info(f"Received ExecuteTask: {task.job_id} ({task.task_type})")
                        self._current_task_handle = asyncio.create_task(self._handle_execute(task))

                    elif payload_type == "cancel":
                        cancel_job_id = master_msg.cancel.job_id
                        logger.info(f"Received CancelTask: {cancel_job_id}")
                        if self._current_task_handle and not self._current_task_handle.done():
                            self._current_task_handle.cancel()

            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages to Master."""
        while self._running:
            await asyncio.sleep(self.heartbeat_interval)
            hb = flow_pb2.WorkerMessage(
                heartbeat=flow_pb2.HeartbeatRequest(worker_id=self.worker_id)
            )
            await self._out_queue.put(hb)

    async def _handle_execute(self, task: flow_pb2.ExecuteTask) -> None:
        """Execute a task and stream progress / completion back to Master."""
        start_time = time.time()

        async def report_progress(pct: int, txt: str):
            p_msg = flow_pb2.WorkerMessage(
                progress=flow_pb2.ProgressReport(
                    job_id=task.job_id,
                    phase="generating",
                    message=f"Generating: {txt}",
                    progress_percent=pct,
                    progress_text=txt,
                    elapsed_seconds=round(time.time() - start_time, 1),
                )
            )
            await self._out_queue.put(p_msg)

        try:
            result_dict, produced_assets = await self.executor.execute_task(task, report_progress)

            res_struct = Struct()
            res_struct.update(result_dict)

            comp_msg = flow_pb2.WorkerMessage(
                completed=flow_pb2.CompletedReport(
                    job_id=task.job_id,
                    worker_id=self.worker_id,
                    result=res_struct,
                    produced_assets=produced_assets,
                )
            )
            await self._out_queue.put(comp_msg)
            logger.info(f"Completed and reported job {task.job_id} to Master.")

        except asyncio.CancelledError:
            fail_msg = flow_pb2.WorkerMessage(
                failed=flow_pb2.FailedReport(
                    job_id=task.job_id,
                    worker_id=self.worker_id,
                    error="Task was cancelled by Master.",
                )
            )
            await self._out_queue.put(fail_msg)

        except Exception as e:
            logger.error(f"Execution failed for job {task.job_id}: {e}", exc_info=True)
            fail_msg = flow_pb2.WorkerMessage(
                failed=flow_pb2.FailedReport(
                    job_id=task.job_id,
                    worker_id=self.worker_id,
                    error=str(e),
                )
            )
            await self._out_queue.put(fail_msg)
