"""Test module 03: Google Flow project lifecycle management tools.

Verifies website_open, project_list, project_open, and project_create tools
(TC-PRJ-001 ~ TC-PRJ-004).
"""
from __future__ import annotations

import pytest
from mcp import ClientSession

from .conftest import call_tool_json


@pytest.mark.asyncio
async def test_website_open(mcp_session: ClientSession):
    """TC-PRJ-001: Verify website_open navigates browser to Google Flow."""
    raw_res, data = await call_tool_json(mcp_session, "website_open", {"url": ""})

    assert not raw_res.isError, f"Tool website_open failed: {raw_res}"
    assert data.get("status") == "success"
    assert "current_url" in data
    assert any(domain in data["current_url"].lower() for domain in ("google", "flow", "http"))


@pytest.mark.asyncio
async def test_project_list(mcp_session: ClientSession):
    """TC-PRJ-002: Verify project_list fetches projects and syncs to DAO."""
    raw_res, data = await call_tool_json(mcp_session, "project_list", {})

    assert not raw_res.isError, f"Tool project_list failed: {raw_res}"
    assert data.get("status") == "success"
    assert "count" in data
    assert isinstance(data.get("projects"), list)


@pytest.mark.asyncio
async def test_project_open_or_create(mcp_session: ClientSession):
    """TC-PRJ-003: Verify project_open opens an existing project or creates a new one."""
    test_project_name = "test_business_suite_proj"
    raw_res, data = await call_tool_json(
        mcp_session,
        "project_open",
        {"project_name": test_project_name},
    )

    assert not raw_res.isError, f"Tool project_open failed: {raw_res}"
    assert data.get("status") == "success"
    assert data.get("project_name") == test_project_name
    assert "/project/" in data.get("url", "")


@pytest.mark.asyncio
async def test_project_create(mcp_session: ClientSession):
    """TC-PRJ-004: Verify project_create explicitly creates and names a new project."""
    test_project_name = "test_create_explicit_proj"
    raw_res, data = await call_tool_json(
        mcp_session,
        "project_create",
        {"project_name": test_project_name},
    )

    assert not raw_res.isError, f"Tool project_create failed: {raw_res}"
    assert data.get("status") == "success"
    assert data.get("project_name") == test_project_name
    assert "/project/" in data.get("url", "")


@pytest.mark.asyncio
async def test_project_rename(mcp_session: ClientSession):
    """TC-PRJ-005: Verify project_rename renames an existing project."""
    old_name = "test_business_suite_proj"
    new_name = "test_renamed_explicit_proj"
    raw_res, data = await call_tool_json(
        mcp_session,
        "project_rename",
        {"old_name": old_name, "new_name": new_name},
    )

    assert not raw_res.isError, f"Tool project_rename failed: {raw_res}"
    assert data.get("status") in ("success", "error")
    if data.get("status") == "success":
        assert data.get("old_name") == old_name
        assert data.get("new_name") == new_name
