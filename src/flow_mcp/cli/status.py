"""CLI tool to query cluster status."""
from __future__ import annotations

import argparse
import json
import httpx
from flow_mcp.config import get_settings


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Query Flow MCP Cluster Status")
    parser.add_argument(
        "--url",
        type=str,
        default=f"http://{settings.master_host if settings.master_host != '0.0.0.0' else '127.0.0.1'}:{settings.master_http_port}",
        help="Master HTTP endpoint",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    url = f"{args.url.rstrip('/')}/status"
    try:
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code != 200:
            print(f"Error querying cluster status: HTTP {resp.status_code}")
            return

        data = resp.json()
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        print("\n" + "=" * 60)
        print("          GOOGLE FLOW MCP CLUSTER STATUS")
        print("=" * 60)

        # Workers
        print(f"\n[WORKERS] Total Connected: {data.get('workers_count', 0)}")
        print("-" * 60)
        for w in data.get("workers", []):
            avail_str = "[IDLE]" if w.get("is_available") else f"[{w.get('phase', '').upper()}]"
            print(
                f" - {w.get('worker_id')}: {avail_str} | Account: {w.get('account') or 'unknown'} | "
                f"Free: {w.get('daily_free', 0)} | Bal: {w.get('balance')}"
            )

        # Active Jobs
        print(f"\n[ACTIVE JOBS] Total Running/Queued: {data.get('active_jobs_count', 0)}")
        print("-" * 60)
        for j in data.get("active_jobs", []):
            print(
                f" - {j.get('job_id')}: {j.get('task_type')} | Phase: {j.get('phase')} | "
                f"Worker: {j.get('worker_id') or 'none'} | Progress: {j.get('progress_text', '0%')}"
            )

        # Accounts
        print(f"\n[ACCOUNTS] Total Registered: {len(data.get('accounts', []))}")
        print("-" * 60)
        for a in data.get("accounts", []):
            print(
                f" - {a.get('email')}: Free Remaining: {a.get('daily_free_remaining')} | Balance: {a.get('balance')}"
            )

        print("=" * 60 + "\n")

    except Exception as e:
        print(f"Could not connect to Master at {url}: {e}")


if __name__ == "__main__":
    main()
