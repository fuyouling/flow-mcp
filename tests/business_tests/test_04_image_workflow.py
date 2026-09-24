"""Test module 04: Image generation and asset management tools.

Verifies image_create, image_status, image_create_by_upload, and image_list
tools (TC-IMG-001 ~ TC-IMG-004).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from mcp import ClientSession

from .conftest import call_tool_json, poll_job_status


@pytest.mark.asyncio
async def test_image_create_full_params(mcp_session: ClientSession):
    """TC-IMG-001 & TC-IMG-002: Submit image_create with full params, poll image_status, then cancel."""
    prompt = "Grey-tailed sandpiper drinking water"
    project_name = "default"

    # 1. Submit text-to-image task
    raw_res, data = await call_tool_json(
        mcp_session,
        "image_create",
        {
            "prompt": prompt,
            "project_name": project_name,
            "aspect_ratio": "16:9",
            "model_name": "Nano Banana Pro",
            "quantity": 1,
            "image_name": "Gray-tailed_drifting",
            "assets": "",
            "download": "2K",
        },
    )

    assert not raw_res.isError, f"Tool image_create failed: {raw_res}"
    job_id = data.get("job_id")
    assert job_id, f"image_create did not return job_id: {data}"
    assert data.get("status") == "pending"

    # 2. Poll task status via image_status
    raw_res_status, status_data = await poll_job_status(
        mcp_session,
        "image_status",
        job_id,
        max_attempts=5,
        interval=1.0,
    )

    assert not raw_res_status.isError, f"Tool image_status failed: {raw_res_status}"
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

    # 3. Clean up task by canceling
    await call_tool_json(mcp_session, "task_cancel", {"job_id": job_id})


@pytest.mark.asyncio
async def test_image_status_not_found(mcp_session: ClientSession):
    """TC-IMG-003: Verify image_status returns not_found for non-existent job."""
    fake_job_id = "non_existent_img_job_000000"
    raw_res, data = await call_tool_json(
        mcp_session,
        "image_status",
        {"job_id": fake_job_id},
    )

    assert not raw_res.isError
    assert data.get("status") == "not_found"
    assert fake_job_id in data.get("message", "")


@pytest.mark.asyncio
async def test_image_list(mcp_session: ClientSession):
    """TC-IMG-004: Verify image_list returns project images list."""
    raw_res, data = await call_tool_json(
        mcp_session,
        "image_list",
        {"project_name": "default"},
    )

    assert not raw_res.isError, f"Tool image_list failed: {raw_res}"
    assert data.get("status") == "success"
    assert "count" in data
    assert isinstance(data.get("images"), list)


@pytest.mark.asyncio
async def test_image_create_by_upload_full_params(mcp_session: ClientSession):
    """TC-IMG-005: Submit image upload task with local file and full params, poll status, then cancel."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        # Write 1x1 dummy PNG bytes
        f.write(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        tmp_img = Path(f.name)

    try:
        raw_res, data = await call_tool_json(
            mcp_session,
            "image_create_by_upload",
            {
                "image_path": str(r"C:\Users\zgh\Downloads\google_flow\bird_3_2K_20260920002330.jpeg"),
                "project_name": "default",
                "image_name": "test_sample.png",
            },
        )
        assert not raw_res.isError, f"image_create_by_upload failed: {raw_res}"
        job_id = data.get("job_id")
        assert job_id, f"Missing job_id: {data}"
        assert data.get("status") == "pending"

        # 2. Poll task status via image_status
        raw_res_status, status_data = await poll_job_status(
            mcp_session,
            "image_status",
            job_id,
            max_attempts=5,
            interval=1.0,
        )
        assert not raw_res_status.isError, f"Tool image_status failed: {raw_res_status}"
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

        # 3. Clean up task
        await call_tool_json(mcp_session, "task_cancel", {"job_id": job_id})
    finally:
        if tmp_img.exists():
            tmp_img.unlink(missing_ok=True)


