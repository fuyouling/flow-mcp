"""Test module 02: Cluster task queue and worker management tools.

Verifies task_queue_status and task_cancel tools (TC-QUE-001, TC-QUE-002).
"""
from __future__ import annotations

import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_task_queue_status_worker_0_registered(mcp_session: ClientSession):
    """TC-QUE-001: Verify Master cluster has Worker 0 registered and healthy."""
    raw_res, data = await call_tool_json(mcp_session, "task_queue_status", {})

    assert not raw_res.isError, f"Tool task_queue_status returned error: {raw_res}"
    assert data.get("status") == "success"
    assert "workers_count" in data
    assert data["workers_count"] >= 1, "At least 1 worker (Worker 0) must be registered"

    workers = data.get("workers", [])
    worker_ids = [w["worker_id"] for w in workers]
    assert "master_local_worker" in worker_ids, "Built-in 'master_local_worker' not found in workers"

    worker_0 = next(w for w in workers if w["worker_id"] == "master_local_worker")
    assert "is_available" in worker_0, "Worker 0 should have is_available field"
    assert worker_0["daily_free"] >= 0, "Worker 0 daily_free should be >= 0"
    assert "active_jobs" in data
    assert "accounts" in data


@pytest.mark.asyncio
async def test_task_cancel_non_existent_job(mcp_session: ClientSession):
    """TC-QUE-002: Verify task_cancel returns appropriate error for non-existent job."""
    non_existent_id = "test_fake_job_uuid_000000"
    raw_res, data = await call_tool_json(mcp_session, "task_cancel", {"job_id": non_existent_id})

    assert not raw_res.isError
    assert data.get("status") == "error"
    assert f"Job '{non_existent_id}' not found." in data.get("message", "")
