"""Interactive and automated CLI test runner for Flow MCP business tests.

Usage:
    python tests/business_tests/run_tests.py
    python tests/business_tests/run_tests.py --module image
    python tests/business_tests/run_tests.py --module discovery --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

try:
    from .conftest import FLOW_MCP_SSE_URL, is_master_alive
except (ImportError, ValueError):
    from conftest import FLOW_MCP_SSE_URL, is_master_alive  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODULE_MAP = {
    "all": None,
    "discovery": "tests/business_tests/test_01_tools_discovery.py",
    "queue": "tests/business_tests/test_02_task_queue_status.py",
    "project": "tests/business_tests/test_03_project_management.py",
    "image": "tests/business_tests/test_04_image_workflow.py",
    "video": "tests/business_tests/test_05_video_workflow.py",
    "character": "tests/business_tests/test_06_character_workflow.py",
    "e2e": "tests/business_tests/test_07_end_to_end_pipeline.py",
}


def print_banner(text: str, char: str = "=") -> None:
    line = char * 78
    print(f"\n{line}\n{text}\n{line}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flow MCP Master Standalone Business Function Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--module",
        "-m",
        choices=list(MODULE_MAP.keys()),
        default="all",
        help="Specify which business module test file to run (default: all)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed verbose output (-v -s in pytest)",
    )
    parser.add_argument(
        "--url",
        default=FLOW_MCP_SSE_URL,
        help=f"Master SSE URL to test against (default: {FLOW_MCP_SSE_URL})",
    )

    args = parser.parse_args()

    print_banner("Google Flow MCP - Business Function Test Suite", "=")
    print(f"[INFO] Target Master SSE Endpoint: {args.url}")
    print(f"[INFO] Selected Test Scope: {args.module}")

    # 1. Pre-flight check: Is Master node running?
    print("[INFO] Probing Master node connection...")
    alive = is_master_alive(url=args.url)

    if not alive:
        print_banner(
            f"[!] 警告: 无法连接到 Flow MCP Master 节点: {args.url}\n\n"
            "根据 docs/debugging_guide.md (第 3 节：场景一 单节点最小化调试)：\n"
            "业务测试脚本要求 Master 节点处于运行状态。\n\n"
            "请在另一个 PowerShell 终端中执行以下命令启动服务：\n"
            "    cd c:\\dev\\ai\\mcp\\flow-mcp\n"
            "    & .venv\\Scripts\\Activate.ps1\n"
            "    flow-mcp master --transport sse --port 8000\n\n"
            "Master 启动成功后，重新运行此测试脚本即可。",
            "*",
        )
        return 1

    print("[OK] Master node is active and responsive!\n")

    # 2. Assemble pytest command arguments
    pytest_args = []
    target_file = MODULE_MAP.get(args.module)
    if target_file:
        pytest_args.append(str(PROJECT_ROOT / target_file))
    else:
        pytest_args.append(str(PROJECT_ROOT / "tests/business_tests"))

    # Always include -v and -s to ensure return results and polling logs are visible in console
    pytest_args.extend(["-v", "-s"])

    print(f"[INFO] Executing pytest with args: {pytest_args}\n")
    exit_code = pytest.main(pytest_args)

    if exit_code == 0:
        print_banner("[PASS] All business function tests completed successfully! [PASS]", "=")
    else:
        print_banner(f"[FAIL] Test execution finished with exit code: {exit_code}", "=")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
