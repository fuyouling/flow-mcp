"""Unit tests for SQLite database DAOs."""
import tempfile
from pathlib import Path

import pytest

from flow_mcp.db.account_dao import AccountDAO
from flow_mcp.db.asset_dao import AssetDAO
from flow_mcp.db.connection import init_db
from flow_mcp.db.job_dao import JobDAO
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.models.asset import AssetKind, AssetRecord
from flow_mcp.models.credit import AccountInfo, ReservationState
from flow_mcp.models.job import Job, JobPhase, JobSpec, TaskType


@pytest.fixture
async def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        await init_db(db_path)
        yield db_path


@pytest.mark.asyncio
async def test_job_dao_crud(temp_db):
    dao = JobDAO(temp_db)
    spec = JobSpec(
        job_id="test_job_1",
        task_type=TaskType.IMAGE_CREATE,
        project_alias="test_proj",
        cost_credits=0,
    )
    job = Job.create(spec)
    await dao.insert_job(job)

    # Read back
    fetched = await dao.get_job("test_job_1")
    assert fetched is not None
    assert fetched.job_id == "test_job_1"
    assert fetched.spec.task_type == TaskType.IMAGE_CREATE

    # Update status
    job.status.phase = JobPhase.COMPLETED
    job.status.is_finished = True
    job.status.result = {"url": "http://example.com"}
    await dao.update_status(job.status)

    updated = await dao.get_job("test_job_1")
    assert updated is not None
    assert updated.status.phase == JobPhase.COMPLETED
    assert updated.status.is_finished is True
    assert updated.status.result["url"] == "http://example.com"


@pytest.mark.asyncio
async def test_account_dao_reservation(temp_db):
    dao = AccountDAO(temp_db)
    account = AccountInfo(
        email="test@google.com",
        worker_id="worker_1",
        balance=100,
        daily_free_remaining=50,
    )
    await dao.upsert_account(account)

    # Reserve 60 credits (50 free + 10 balance)
    res = await dao.reserve_credits("test@google.com", "job_123", 60)
    assert res.reserved_free == 50
    assert res.reserved_balance == 10
    assert res.state == ReservationState.PENDING

    # Check updated account
    acc = await dao.get_account("test@google.com")
    assert acc is not None
    assert acc.daily_free_remaining == 0
    assert acc.balance == 90

    # Release reservation (failure refund)
    await dao.release_reservation("job_123")
    acc_refunded = await dao.get_account("test@google.com")
    assert acc_refunded is not None
    assert acc_refunded.daily_free_remaining == 50
    assert acc_refunded.balance == 100


@pytest.mark.asyncio
async def test_account_dao_autoprovision_reservation(temp_db):
    dao = AccountDAO(temp_db)
    # Account is not yet created, reserve 10 credits (less than daily free grant 50)
    res = await dao.reserve_credits("new_worker@google.com", "job_456", 10)
    assert res.reserved_free == 10
    assert res.reserved_balance == 0
    assert res.state == ReservationState.PENDING

    acc = await dao.get_account("new_worker@google.com")
    assert acc is not None
    assert acc.daily_free_remaining == 40


@pytest.mark.asyncio
async def test_project_dao(temp_db):
    dao = ProjectDAO(temp_db)
    await dao.upsert_project("my_proj", "w1", "uuid_123")
    await dao.upsert_project("my_proj", "w2", "uuid_456")

    mappings = await dao.get_all_worker_mappings("my_proj")
    assert mappings["w1"] == "uuid_123"
    assert mappings["w2"] == "uuid_456"


@pytest.mark.asyncio
async def test_asset_dao(temp_db):
    dao = AssetDAO(temp_db)
    record = AssetRecord(
        name="char_portrait",
        kind=AssetKind.CHARACTER,
        file_name="portrait.png",
        file_path="/tmp/portrait.png",
        sha256="abc123sha",
        created_at=1000.0,
    )
    await dao.insert_asset(record)

    found = await dao.find_by_sha256("abc123sha")
    assert found is not None
    assert found.name == "char_portrait"
