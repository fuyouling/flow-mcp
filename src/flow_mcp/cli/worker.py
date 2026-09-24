"""CLI entrypoint to launch Worker node."""
from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from flow_mcp.config import get_settings
from flow_mcp.worker.client import WorkerClient


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Start Flow MCP Worker node")
    parser.add_argument("--worker-id", type=str, default="", help="Unique Worker ID")
    parser.add_argument("--master-grpc", type=str, default="", help="Master gRPC endpoint (host:port)")
    parser.add_argument("--master-http", type=str, default="", help="Master HTTP endpoint (http://host:port)")
    args = parser.parse_args()

    worker_id = args.worker_id or settings.worker_id or "worker_node_1"
    master_grpc = args.master_grpc or settings.master_grpc_target
    master_http = args.master_http or settings.master_http_url

    logger.info(f"Starting Flow MCP Worker node [{worker_id}]...")
    client = WorkerClient(
        worker_id=worker_id,
        master_grpc_target=master_grpc,
        master_http_url=master_http,
    )

    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")


if __name__ == "__main__":
    main()
