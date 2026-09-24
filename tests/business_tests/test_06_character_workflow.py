"""Test module 06: Character generation and management tools.

Verifies character_create, character_status, character_create_by_upload,
and character_list tools (TC-CHR-001 ~ TC-CHR-005).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from mcp import ClientSession

from .conftest import call_tool_json, poll_job_status


@pytest.mark.asyncio
async def test_character_create_full_params(mcp_session: ClientSession):
    """TC-CHR-001 & TC-CHR-002: Submit character_create with full params, poll character_status, then cancel."""
    character_name = "CyberPilot_Test"
    prompt = "A photorealistic portrait of a female space commander, glowing cybernetic visor, silver hair, highly detailed, cinematic lighting, 8k resolution"
    full_body_prompt = "A photorealistic full body shot of a female space commander, glowing cybernetic visor, silver hair, sleek armored uniform, standing in a futuristic command center, highly detailed, cinematic lighting, 8k resolution"
    project_name = "default"

    # 1. Submit character creation task
    raw_res, data = await call_tool_json(
        mcp_session,
        "character_create",
        {
            "character_name": character_name,
            "prompt": prompt,
            "project_name": project_name,
            "model_name": "Nano banana pro",
            "full_body": True,
            "full_body_prompt": full_body_prompt,
            "voice_name": "achird",
        },
    )

    assert not raw_res.isError, f"Tool character_create failed: {raw_res}"
    job_id = data.get("job_id")
    assert job_id, f"character_create did not return job_id: {data}"
    assert data.get("status") == "pending"

    # 2. Poll task status via character_status
    raw_res_status, status_data = await poll_job_status(
        mcp_session,
        "character_status",
        job_id,
        max_attempts=120,
        interval=5.0,
    )

    assert not raw_res_status.isError, f"Tool character_status failed: {raw_res_status}"
    assert status_data.get("job_id") == job_id
    assert status_data.get("phase") == "completed", f"Job failed or timed out: {status_data}"

    # 3. Clean up task by canceling
    await call_tool_json(mcp_session, "task_cancel", {"job_id": job_id})


@pytest.mark.asyncio
async def test_character_status_not_found(mcp_session: ClientSession):
    """TC-CHR-003: Verify character_status returns not_found for non-existent job."""
    fake_job_id = "non_existent_chr_job_000000"
    raw_res, data = await call_tool_json(
        mcp_session,
        "character_status",
        {"job_id": fake_job_id},
    )

    assert not raw_res.isError
    assert data.get("status") == "not_found"
    assert fake_job_id in data.get("message", "")


@pytest.mark.asyncio
async def test_character_list(mcp_session: ClientSession):
    """TC-CHR-004: Verify character_list returns project character list."""
    raw_res, data = await call_tool_json(
        mcp_session,
        "character_list",
        {"project_name": "default"},
    )

    assert not raw_res.isError, f"Tool character_list failed: {raw_res}"
    assert data.get("status") == "success"
    assert "count" in data
    assert isinstance(data.get("characters"), list)


@pytest.mark.asyncio
async def test_character_create_by_upload_full_params(mcp_session: ClientSession):
    """TC-CHR-005: Submit character upload task with full params, poll status, then cancel."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_portrait, \
         tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_fullbody:
        f_portrait.write(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        f_fullbody.write(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        tmp_img_portrait = Path(f_portrait.name)
        tmp_img_fullbody = Path(f_fullbody.name)

    try:
        raw_res, data = await call_tool_json(
            mcp_session,
            "character_create_by_upload",
            {
                "character_name": "Uploaded_Hero_Test",
                "portrait_image_path": str(tmp_img_portrait),
                "project_name": "test_char_proj",
                "full_body_image_path": str(tmp_img_fullbody),
                "voice_name": "Nova",
            },
        )
        assert not raw_res.isError, f"character_create_by_upload failed: {raw_res}"
        job_id = data.get("job_id")
        assert job_id, f"Missing job_id: {data}"
        assert data.get("status") == "pending"

        # 2. Poll task status via character_status
        raw_res_status, status_data = await poll_job_status(
            mcp_session,
            "character_status",
            job_id,
            max_attempts=120,
            interval=5.0,
        )
        assert not raw_res_status.isError, f"Tool character_status failed: {raw_res_status}"
        assert status_data.get("job_id") == job_id
        assert status_data.get("phase") == "completed", f"Job failed or timed out: {status_data}"

        # 3. Clean up task
        await call_tool_json(mcp_session, "task_cancel", {"job_id": job_id})
    finally:
        if tmp_img_portrait.exists():
            tmp_img_portrait.unlink(missing_ok=True)
        if tmp_img_fullbody.exists():
            tmp_img_fullbody.unlink(missing_ok=True)


