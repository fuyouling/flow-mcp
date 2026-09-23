"""Integration test for Master gRPC task streaming and HTTP asset hub endpoints."""
import asyncio
import pytest
import tempfile
from pathlib import Path
import httpx
import grpc
from grpc import aio as grpc_aio

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
from flow_mcp.proto import flow_pb2, flow_pb2_grpc


@pytest.fixture
async def cluster_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = str(tmp_path / "test_cluster.db")
        assets_dir = str(tmp_path / "assets")

        await init_db(db_path)

        job_dao = JobDAO(db_path)
        account_dao = AccountDAO(db_path)
        project_dao = ProjectDAO(db_path)
        asset_dao = AssetDAO(db_path)

        asset_hub = AssetHub(asset_dao, base_dir=assets_dir)
        job_registry = JobRegistry(job_dao)
        await job_registry.initialize()

        credit_manager = CreditManager(account_dao)
        worker_pool = WorkerPool()
        scheduler = Scheduler(worker_pool, job_registry, credit_manager)

        grpc_port = 50059
        http_port = 8769

        master_server = MasterServer(
            worker_pool=worker_pool,
            job_registry=job_registry,
            scheduler=scheduler,
            credit_manager=credit_manager,
            asset_hub=asset_hub,
            project_dao=project_dao,
            host="127.0.0.1",
            grpc_port=grpc_port,
            http_port=http_port,
        )

        await master_server.start()
        await asyncio.sleep(0.5)

        yield {
            "grpc_target": f"127.0.0.1:{grpc_port}",
            "http_url": f"http://127.0.0.1:{http_port}",
            "master_server": master_server,
            "worker_pool": worker_pool,
            "job_registry": job_registry,
            "asset_hub": asset_hub,
            "tmp_path": tmp_path,
        }

        await master_server.stop()


@pytest.mark.asyncio
async def test_grpc_registration_and_http_status(cluster_env):
    grpc_target = cluster_env["grpc_target"]
    http_url = cluster_env["http_url"]
    worker_pool = cluster_env["worker_pool"]

    # 1. Connect a test gRPC worker
    async with grpc_aio.insecure_channel(grpc_target) as channel:
        stub = flow_pb2_grpc.FlowClusterStub(channel)

        out_queue = asyncio.Queue()
        reg_msg = flow_pb2.WorkerMessage(
            register=flow_pb2.RegisterRequest(
                worker_id="test_worker_node_1",
                account="node1@gmail.com",
                project_mappings={"demo_project": "uuid-999"},
                cached_assets=["img1", "img2"],
            )
        )
        await out_queue.put(reg_msg)

        async def msg_gen():
            while True:
                msg = await out_queue.get()
                yield msg

        call = stub.StreamTasks(msg_gen())
        ack = await call.read()
        assert ack.WhichOneof("payload") == "ack"
        assert ack.ack.worker_id == "test_worker_node_1"
        assert ack.ack.success is True

        # Check worker in worker_pool
        w = await worker_pool.get_worker("test_worker_node_1")
        assert w is not None
        assert w.account == "node1@gmail.com"
        assert w.project_mappings["demo_project"] == "uuid-999"

        # 2. Check HTTP /status endpoint
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["workers_count"] >= 1
            w_ids = [item["worker_id"] for item in data["workers"]]
            assert "test_worker_node_1" in w_ids

        call.cancel()


@pytest.mark.asyncio
async def test_http_asset_upload_download(cluster_env):
    http_url = cluster_env["http_url"]
    tmp_path = cluster_env["tmp_path"]

    # Create dummy video file
    dummy_file = tmp_path / "sample_video.mp4"
    dummy_file.write_bytes(b"FAKE_MP4_CONTENT_12345")

    async with httpx.AsyncClient() as client:
        # Upload
        with dummy_file.open("rb") as f:
            files = {"file": ("sample_video.mp4", f, "video/mp4")}
            data = {
                "name": "my_test_video",
                "kind": "video",
                "worker_id": "test_w",
                "job_id": "job_001",
            }
            upload_resp = await client.post(f"{http_url}/assets/upload", files=files, data=data)
            assert upload_resp.status_code == 200
            res_json = upload_resp.json()
            assert res_json["name"] == "my_test_video"
            assert res_json["kind"] == "video"

        # Download back
        dl_resp = await client.get(f"{http_url}/assets/my_test_video")
        assert dl_resp.status_code == 200
        assert dl_resp.content == b"FAKE_MP4_CONTENT_12345"
