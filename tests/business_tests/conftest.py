"""Pytest configuration and MCP SSE client fixtures for Flow MCP business tests.

Tests in this directory default to assuming that the Flow MCP Master node is running
in standalone debug mode with SSE transport:
    flow-mcp master --transport sse --port 8000
    (See docs/debugging_guide.md, Section 3)
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult

# Target SSE URL for Master node (default: http://localhost:8000/sse)
DEFAULT_SSE_URL = "http://localhost:8000/sse"
FLOW_MCP_SSE_URL = os.environ.get("FLOW_MCP_SSE_URL", DEFAULT_SSE_URL)


def is_master_alive(url: str = FLOW_MCP_SSE_URL, timeout: float = 1.5) -> bool:
    """Check if the Master node SSE server is responsive."""
    try:
        # Fast health check on the base URL or SSE endpoint
        base_url = url.rsplit("/sse", 1)[0]
        # Attempt to probe base or sse endpoint
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(base_url, follow_redirects=True)
            # Uvicorn/Starlette will return 200, 404 or 405, all indicating server is listening
            return resp.status_code in (200, 404, 405)
    except Exception:
        try:
            # Fallback probe directly to sse
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                return resp.status_code in (200, 404, 405)
        except Exception:
            return False


@pytest.fixture(scope="session")
def master_server_url() -> str:
    """Return the active Flow MCP Master SSE URL."""
    return FLOW_MCP_SSE_URL


@pytest.fixture(scope="session")
def master_is_available() -> bool:
    """Session-scoped check for Master node availability."""
    return is_master_alive()


@pytest.fixture(scope="function")
def ensure_master_running(master_is_available: bool):
    """Ensure Flow MCP Master node is running before executing tests."""
    if not master_is_available:
        pytest.skip(
            f"Master 节点未启动 (无法连接 {FLOW_MCP_SSE_URL})。\n"
            "请参考 docs/debugging_guide.md 场景一在独立终端中启动服务：\n"
            "    flow-mcp master --transport sse --port 8000"
        )


@pytest_asyncio.fixture(scope="function")
async def mcp_session(ensure_master_running) -> AsyncGenerator[ClientSession, None]:
    """Yield an initialized MCP ClientSession connected to the running Master.

    Uses an isolated runner task so that AnyIO's TaskGroup in sse_client
    and ClientSession is entered and exited within the same task context,
    preventing pytest-asyncio's multi-task finalizer from triggering:
    'RuntimeError: Attempted to exit cancel scope in a different task than it was entered in'.
    """
    ready_event = asyncio.Event()
    done_event = asyncio.Event()
    session_holder: list[ClientSession] = []
    error_holder: list[BaseException] = []

    async def sse_runner():
        try:
            async with sse_client(FLOW_MCP_SSE_URL, timeout=10.0, sse_read_timeout=120.0) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    session_holder.append(session)
                    ready_event.set()
                    await done_event.wait()
        except BaseException as ex:
            error_holder.append(ex)
            ready_event.set()

    task = asyncio.create_task(sse_runner())
    await ready_event.wait()

    if error_holder:
        raise error_holder[0]

    try:
        yield session_holder[0]
    finally:
        done_event.set()
        await task


def print_tool_call(name: str, arguments: dict[str, Any] | None) -> None:
    """Print tool call metadata banner to console."""
    print(f"\n{'='*25} [TOOL CALL: {name}] {'='*25}")
    if arguments:
        print(f"Arguments:\n{json.dumps(arguments, ensure_ascii=False, indent=2)}")
    else:
        print("Arguments: None")


def print_tool_result(name: str, raw_res: CallToolResult, parsed: dict[str, Any]) -> None:
    """Print tool call response result to console."""
    print(f"\n[RESPONSE RESULT: {name}] (isError={raw_res.isError}):")
    if parsed:
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    elif raw_res.content:
        for c in raw_res.content:
            text = getattr(c, "text", str(c))
            print(text)
    else:
        print("(empty response)")
    print(f"{'='*70}\n")


async def call_tool_json(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> tuple[CallToolResult, dict[str, Any]]:
    """Helper to invoke an MCP tool, print arguments and return results, and parse JSON text.

    Returns:
        tuple of (raw_result, parsed_dict)
    """
    print_tool_call(name, arguments)
    res: CallToolResult = await session.call_tool(name, arguments or {})
    parsed: dict[str, Any] = {}

    if res.content:
        for c in res.content:
            if c.type == "text" and hasattr(c, "text") and getattr(c, "text"):
                try:
                    parsed = json.loads(getattr(c, "text"))
                    break
                except json.JSONDecodeError:
                    parsed = {"raw_text": getattr(c, "text")}

    print_tool_result(name, res, parsed)
    return res, parsed


async def poll_job_status(
    session: ClientSession,
    tool_name: str,
    job_id: str,
    max_attempts: int = 5,
    interval: float = 1.0,
    stop_when_finished: bool = True,
) -> tuple[CallToolResult, dict[str, Any]]:
    """Poll a job status tool (image_status, video_status, character_status) and print real-time status.

    Args:
        session: Active MCP ClientSession.
        tool_name: Status tool name to call ('image_status', 'video_status', 'character_status').
        job_id: The job ID to poll.
        max_attempts: Maximum number of polling attempts (default: 5).
        interval: Interval between polls in seconds (default: 1.0s).
        stop_when_finished: If True, stops polling early when reaching a terminal phase
                            (is_finished=True or phase in completed/failed/cancelled).

    Returns:
        tuple of (last_raw_result, last_parsed_dict)
    """
    print(f"\n{'*'*20} [POLLING START: {tool_name}] {'*'*20}")
    print(f"Target Job ID: {job_id}")
    print(f"Max Attempts: {max_attempts}, Interval: {interval}s")
    print(f"{'*'*65}\n")

    last_res: CallToolResult | None = None
    last_data: dict[str, Any] = {}

    for attempt in range(1, max_attempts + 1):
        print(f"\n--- [Poll Iteration {attempt}/{max_attempts}] ---")
        last_res, last_data = await call_tool_json(session, tool_name, {"job_id": job_id})

        phase = last_data.get("phase", "unknown")
        progress = last_data.get("progress_percent", 0)
        progress_text = last_data.get("progress_text", "")
        is_finished = last_data.get("is_finished", False)
        msg = last_data.get("message", "")

        print(
            f"--> [Poll Summary #{attempt}/{max_attempts}] phase={phase} | progress={progress}% ({progress_text}) | "
            f"is_finished={is_finished} | msg={msg}"
        )

        if stop_when_finished and (is_finished or phase in ("completed", "failed", "cancelled")):
            print(f"\n[POLLING COMPLETE] Job reached terminal phase: '{phase}' at iteration {attempt}/{max_attempts}.")
            break

        if attempt < max_attempts:
            await asyncio.sleep(interval)

    print(f"\n{'*'*20} [POLLING END: {tool_name}] {'*'*20}\n")
    assert last_res is not None, f"Polling failed to execute any attempt for job {job_id}"
    return last_res, last_data

