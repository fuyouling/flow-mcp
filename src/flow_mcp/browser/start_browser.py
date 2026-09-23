"""CLI script to manage or pre-launch browser instance."""
from __future__ import annotations

import argparse
import sys
import time
from loguru import logger

from flow_mcp.browser.launcher import get_browser_port
from flow_mcp.browser.session import get_browser, close_browser
from flow_mcp.browser.utils import is_port_in_use, stop_browser, get_process_by_port
from flow_mcp.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Google Flow Chrome browser instance")
    parser.add_argument("--status", action="store_true", help="Check browser running status")
    parser.add_argument("--stop", action="store_true", help="Stop running browser instance")
    parser.add_argument("--force", action="store_true", help="Force stop existing browser before launching")
    parser.add_argument("--url", type=str, default="", help="Initial URL to navigate to")
    args = parser.parse_args()

    port = get_browser_port()

    if args.status:
        in_use = is_port_in_use(port)
        proc = get_process_by_port(port) if in_use else None
        if in_use:
            print(f"[OK] Browser is RUNNING on port {port} (PID={proc.pid if proc else 'unknown'})")
        else:
            print(f"[STOPPED] Browser is NOT running on port {port}")
        return

    if args.stop:
        stopped = stop_browser(port)
        if stopped:
            print(f"Browser on port {port} stopped.")
        else:
            print(f"Failed to stop browser on port {port}.")
        return

    if args.force:
        stop_browser(port)
        time.sleep(1)

    print(f"Starting browser on remote debugging port {port}...")
    browser = get_browser()
    target_url = args.url or get_settings().google_flow_base_url
    if target_url:
        tab = browser.latest_tab
        tab.get(target_url)
        print(f"Navigated to {target_url}")
    print("Browser is ready.")


if __name__ == "__main__":
    main()
