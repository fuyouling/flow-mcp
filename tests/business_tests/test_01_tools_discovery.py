"""Test module 01: MCP tools discovery and schema contract validation.

Verifies that Master node registers all 19 Flow MCP tools with valid schemas
and descriptions as specified in TC-DISC-001 and TC-DISC-002.
"""
from __future__ import annotations

import pytest
from mcp import ClientSession

EXPECTED_TOOLS = {
    # Project tools (5)
    "website_open",
    "project_list",
    "project_open",
    "project_create",
    "project_rename",
    # Queue & Cluster tools (2)
    "task_queue_status",
    "task_cancel",
    # Image tools (4)
    "image_create",
    "image_create_by_upload",
    "image_status",
    "image_list",
    # Video tools (4)
    "video_create",
    "video_create_by_upload",
    "video_status",
    "video_list",
    # Character tools (4)
    "character_create",
    "character_create_by_upload",
    "character_status",
    "character_list",
}


@pytest.mark.asyncio
async def test_tools_discovery_all_19_tools_present(mcp_session: ClientSession):
    """TC-DISC-001: Verify all 19 business tools are registered and discovered."""
    print(f"\n{'='*25} [API CALL: list_tools] {'='*25}")
    tools_result = await mcp_session.list_tools()
    discovered_tools = {tool.name: tool for tool in tools_result.tools}

    print(f"Discovered Tools Count: {len(discovered_tools)} / 19")
    print("Discovered Tools List:")
    for name in sorted(discovered_tools.keys()):
        print(f"  - {name:28} : {discovered_tools[name].description}")
    print(f"{'='*70}\n")

    missing_tools = EXPECTED_TOOLS - set(discovered_tools.keys())
    assert not missing_tools, f"Missing expected tools on Master: {missing_tools}"
    assert len(discovered_tools) == 19, f"Expected 19 tools, discovered: {len(discovered_tools)}"


@pytest.mark.asyncio
async def test_tools_schemas_and_descriptions(mcp_session: ClientSession):
    """TC-DISC-002: Verify schemas, required arguments, and descriptions."""
    print(f"\n{'='*25} [SCHEMA VALIDATION: list_tools] {'='*25}")
    tools_result = await mcp_session.list_tools()
    tool_map = {tool.name: tool for tool in tools_result.tools}

    # 1. Check description non-empty for all tools
    for name, tool in tool_map.items():
        assert tool.description, f"Tool '{name}' has empty description"

    # Print input schemas for sample tools
    sample_tools = ["image_create", "video_create", "character_create", "task_cancel"]
    print("Sample Tool inputSchema Contract Validation:")
    for name in sample_tools:
        print(f"  Tool '{name}' properties: {list(tool_map[name].inputSchema.get('properties', {}).keys())}")
    print(f"{'='*70}\n")

    # 2. Check schema contracts for image_create
    img_tool = tool_map["image_create"]
    assert "prompt" in img_tool.inputSchema["properties"]
    assert "project_name" in img_tool.inputSchema["properties"]
    assert "aspect_ratio" in img_tool.inputSchema["properties"]

    # 3. Check schema contracts for video_create
    vid_tool = tool_map["video_create"]
    assert "prompt" in vid_tool.inputSchema["properties"]
    assert "duration" in vid_tool.inputSchema["properties"]
    assert "resolution" in vid_tool.inputSchema["properties"]

    # 4. Check schema contracts for character_create
    chr_tool = tool_map["character_create"]
    assert "character_name" in chr_tool.inputSchema["properties"]
    assert "prompt" in chr_tool.inputSchema["properties"]

    # 5. Check schema contracts for task_cancel
    cancel_tool = tool_map["task_cancel"]
    assert "job_id" in cancel_tool.inputSchema["properties"]

