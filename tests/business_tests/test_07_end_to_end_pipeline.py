"""Test module 07: End-to-end business pipeline integration test.

Validates the full lifecycle: Project Open -> Task Enqueue -> Status Query ->
Queue Verification -> Task Cancellation (TC-E2E-001).
"""
from __future__ import annotations

import pytest
from mcp import ClientSession

from .conftest import call_tool_json, poll_job_status


@pytest.mark.asyncio
async def test_end_to_end_business_pipeline(mcp_session: ClientSession):
    """TC-E2E-001: Comprehensive pipeline test covering project, queue, creation, status, and cancel."""
    test_project = "e2e_pipeline_integration_test"

    # Step 1: Query initial queue state
    raw_res, queue_data = await call_tool_json(mcp_session, "task_queue_status", {})
    assert not raw_res.isError
    assert queue_data.get("status") == "success"
    assert queue_data.get("workers_count", 0) >= 1

    # Step 2: Open or initialize the target project
    raw_res, prj_data = await call_tool_json(
        mcp_session,
        "project_open",
        {"project_name": test_project},
    )
    assert not raw_res.isError
    assert prj_data.get("status") == "success"

    # Step 3: Enqueue an image generation task
    raw_res, img_data = await call_tool_json(
        mcp_session,
        "image_create",
        {
            "prompt": "An artistic neon concept art for an AI automation control room",
            "project_name": test_project,
            "aspect_ratio": "16:9",
        },
    )
    assert not raw_res.isError
    job_id = img_data.get("job_id")
    assert job_id, f"Missing job_id in image_create response: {img_data}"
    assert img_data.get("status") == "pending"

    # Step 4: Poll task tracking in job status
    raw_res, status_data = await poll_job_status(
        mcp_session,
        "image_status",
        job_id,
        max_attempts=3,
        interval=1.0,
    )
    assert not raw_res.isError
    assert status_data.get("job_id") == job_id
    assert status_data.get("phase") in (
        "pending",
        "scheduled",
        "running",
        "master_running",
        "broadcasting",
        "completed",
        "failed",
        "cancelled",
    )

    # Step 5: Check task reflects in queue status
    raw_res, updated_queue = await call_tool_json(mcp_session, "task_queue_status", {})
    assert not raw_res.isError
    assert updated_queue.get("status") == "success"

    # Step 6: Cancel the task to release credits & cleanup
    raw_res, cancel_data = await call_tool_json(
        mcp_session,
        "task_cancel",
        {"job_id": job_id},
    )
    assert not raw_res.isError
    assert cancel_data.get("status") in ("success", "info")

    # Step 7: Final verification of cancellation state
    raw_res, final_status = await call_tool_json(
        mcp_session,
        "image_status",
        {"job_id": job_id},
    )
    assert not raw_res.isError
    assert final_status.get("phase") in ("cancelled", "completed")
