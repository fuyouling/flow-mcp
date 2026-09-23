"""CLI entrypoint to launch Master node."""
from __future__ import annotations

import argparse
import sys
from loguru import logger

from flow_mcp.gateway.server import FlowMCPGateway


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Flow MCP Master node (MCP Gateway + Cluster Control)")
    parser.add_argument("--transport", type=str, choices=["stdio", "sse"], default="stdio", help="MCP transport protocol")
    parser.add_argument("--port", type=int, default=8000, help="Port if using SSE transport")
    args = parser.parse_args()

    # If stdio, redirect all logging strictly to stderr to prevent breaking JSON-RPC
    if args.transport == "stdio":
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    logger.info("Initializing Flow MCP Master node...")
    gateway = FlowMCPGateway()
    gateway.run(transport=args.transport)


if __name__ == "__main__":
    main()
