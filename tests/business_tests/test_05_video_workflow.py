"""Test module 05: Video generation and asset management tools.

Verifies video_create, video_status, video_create_by_upload, and video_list
tools (TC-VID-001 ~ TC-VID-005).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from mcp import ClientSession

from .conftest import call_tool_json, poll_job_status


@pytest.mark.asyncio
async def test_video_create_full_params(mcp_session: ClientSession):
    """TC-VID-001 & TC-VID-002: Submit video_create with full params, poll video_status, then cancel."""
    prompt = "Birds are playing in the water."
    project_name = "default"

    # 1. Submit text-to-video task
    raw_res, data = await call_tool_json(
        mcp_session,
        "video_create",
        {
            "prompt": prompt,
            "project_name": project_name,
            "model_name": "Omni 1.1 Flash",
            "mode": "asset",
            "start_frame": "",
            "end_frame": "",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "duration": 8,
            "quantity": 1,
            "assets": "Gray-tailed_drifting",
            "video_name": "SE_bird_video",
            "download": "1080p",
        },
    )

    assert not raw_res.isError, f"Tool video_create failed: {raw_res}"
    job_id = data.get("job_id")
    assert job_id, f"video_create did not return job_id: {data}"
    assert data.get("status") == "pending"

    # 2. Poll task status via video_status
    raw_res_status, status_data = await poll_job_status(
        mcp_session,
        "video_status",
        job_id,
        max_attempts=5,
        interval=1.0,
    )

    assert not raw_res_status.isError, f"Tool video_status failed: {raw_res_status}"
    assert status_data.get("job_id") == job_id
    assert status_data.get("phase") in (
        "pending",
        "scheduled",
        "running",
        "assigned",
        "syncing_assets",
        "generating",
        "downloading",
        "uploading",
        "completed",
        "failed",
        "cancelled",
    )

    # 3. Clean up task by canceling
    await call_tool_json(mcp_session, "task_cancel", {"job_id": job_id})


@pytest.mark.asyncio
async def test_video_status_not_found(mcp_session: ClientSession):
    """TC-VID-003: Verify video_status returns not_found for non-existent job."""
    fake_job_id = "non_existent_vid_job_000000"
    raw_res, data = await call_tool_json(
        mcp_session,
        "video_status",
        {"job_id": fake_job_id},
    )

    assert not raw_res.isError
    assert data.get("status") == "not_found"
    assert fake_job_id in data.get("message", "")


@pytest.mark.asyncio
async def test_video_list(mcp_session: ClientSession):
    """TC-VID-004: Verify video_list returns project video list."""
    raw_res, data = await call_tool_json(
        mcp_session,
        "video_list",
        {"project_name": "default"},
    )

    assert not raw_res.isError, f"Tool video_list failed: {raw_res}"
    assert data.get("status") == "success"
    assert "count" in data
    assert isinstance(data.get("videos"), list)


@pytest.mark.asyncio
async def test_video_create_by_upload_full_params(mcp_session: ClientSession):
    """TC-VID-005: Submit reference video upload task with full params, poll status, then cancel."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free")
        tmp_vid = Path(f.name)

    try:
        raw_res, data = await call_tool_json(
            mcp_session,
            "video_create_by_upload",
            {
                "video_path": str(tmp_vid),
                "project_name": "test_video_proj",
                "video_name": "sample_reference.mp4",
            },
        )
        assert not raw_res.isError, f"video_create_by_upload failed: {raw_res}"
        job_id = data.get("job_id")
        assert job_id, f"Missing job_id: {data}"
        assert data.get("status") == "pending"

        # 2. Poll task status via video_status
        raw_res_status, status_data = await poll_job_status(
            mcp_session,
            "video_status",
            job_id,
            max_attempts=5,
            interval=1.0,
        )
        assert not raw_res_status.isError, f"Tool video_status failed: {raw_res_status}"
        assert status_data.get("job_id") == job_id
        assert status_data.get("phase") in (
            "pending",
            "scheduled",
            "running",
            "assigned",
            "syncing_assets",
            "generating",
            "downloading",
            "uploading",
            "completed",
            "failed",
            "cancelled",
        )

        # 3. Clean up task
        await call_tool_json(mcp_session, "task_cancel", {"job_id": job_id})
    finally:
        if tmp_vid.exists():
            tmp_vid.unlink(missing_ok=True)


