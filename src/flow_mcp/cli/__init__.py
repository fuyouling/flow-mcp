"""Main CLI dispatcher for flow-mcp."""
from __future__ import annotations

import sys


def print_help():
    print("Usage: flow-mcp <command> [options]")
    print("\nCommands:")
    print("  master   Start Master node (MCP Gateway + Cluster Control)")
    print("  worker   Start Worker node")
    print("  status   Query cluster status")
    print("  browser  Manage Chrome browser instance")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()
    sys.argv.pop(1)

    if cmd == "master":
        from flow_mcp.cli.master import main as master_main
        master_main()
    elif cmd == "worker":
        from flow_mcp.cli.worker import main as worker_main
        worker_main()
    elif cmd == "status":
        from flow_mcp.cli.status import main as status_main
        status_main()
    elif cmd == "browser":
        from flow_mcp.browser.start_browser import main as browser_main
        browser_main()
    else:
        print(f"Unknown command: {cmd}\n")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
