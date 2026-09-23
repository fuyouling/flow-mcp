"""Unit tests for WorkerPool routing algorithm."""
import pytest
from flow_mcp.control.worker_pool import WorkerPool
from flow_mcp.models.job import JobSpec, TaskType
from flow_mcp.models.worker import WorkerPhase


@pytest.mark.asyncio
async def test_worker_routing_credit_tiers():
    pool = WorkerPool()

    # Worker 1: daily_free=50 (can afford cost=20 with pure free credits)
    await pool.register_worker("w1", account="w1@gmail.com", daily_free=50, balance=0)

    # Worker 2: daily_free=10, balance=100 (needs balance to afford cost=20)
    await pool.register_worker("w2", account="w2@gmail.com", daily_free=10, balance=100)

    # Worker 3: daily_free=0, balance=500 (pure balance)
    await pool.register_worker("w3", account="w3@gmail.com", daily_free=0, balance=500)

    spec = JobSpec(
        task_type=TaskType.VIDEO_CREATE,
        project_alias="test",
        cost_credits=20,
    )

    # Should select w1 because it can pay purely from daily_free (Tier 1)
    best = await pool.select_best(spec)
    assert best is not None
    assert best.worker_id == "w1"


@pytest.mark.asyncio
async def test_worker_routing_asset_hit_priority():
    pool = WorkerPool()

    # Both workers have enough daily free credits
    await pool.register_worker("w1", daily_free=50, cached_assets=["asset_A"])
    await pool.register_worker("w2", daily_free=50, cached_assets=["asset_A", "asset_B"])

    spec = JobSpec(
        task_type=TaskType.VIDEO_CREATE,
        project_alias="test",
        cost_credits=10,
        required_assets=["asset_A", "asset_B"],
    )

    # w2 has 2 asset hits vs w1 has 1 asset hit -> w2 preferred
    best = await pool.select_best(spec)
    assert best is not None
    assert best.worker_id == "w2"
