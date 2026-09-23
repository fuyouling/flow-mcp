"""Data Access Object for Project Alias Mappings."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import aiosqlite
from loguru import logger

from flow_mcp.db.connection import get_db_connection


class ProjectDAO:
    """Async DAO for mapping global project aliases to worker-specific Flow project UUIDs."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    async def upsert_project(
        self,
        project_alias: str,
        worker_id: str,
        local_uuid: str,
        flow_url: str = "",
    ) -> None:
        """Insert or update a project mapping for a specific worker."""
        now = datetime.now(timezone.utc).isoformat()
        query = """
        INSERT INTO projects (project_alias, worker_id, local_uuid, flow_url, last_accessed)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(project_alias, worker_id) DO UPDATE SET
            local_uuid = excluded.local_uuid,
            flow_url = CASE WHEN excluded.flow_url != '' THEN excluded.flow_url ELSE projects.flow_url END,
            last_accessed = excluded.last_accessed
        """
        async with get_db_connection(self.db_path) as db:
            await db.execute(query, (project_alias, worker_id, local_uuid, flow_url, now))
            await db.commit()

    async def get_project(self, project_alias: str, worker_id: str) -> dict[str, Any] | None:
        """Get project mapping details for a worker."""
        query = "SELECT * FROM projects WHERE project_alias = ? AND worker_id = ?"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (project_alias, worker_id)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return dict(row)

    async def get_local_uuid(self, project_alias: str, worker_id: str) -> str | None:
        """Get the local Flow project UUID for a worker."""
        row = await self.get_project(project_alias, worker_id)
        return row["local_uuid"] if row else None

    async def list_projects_by_worker(self, worker_id: str) -> list[dict[str, Any]]:
        """List all project mappings for a specific worker."""
        query = "SELECT * FROM projects WHERE worker_id = ? ORDER BY project_alias ASC"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (worker_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def list_all_aliases(self) -> list[str]:
        """List all distinct project aliases known across the cluster."""
        query = "SELECT DISTINCT project_alias FROM projects ORDER BY project_alias ASC"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [r["project_alias"] for r in rows]

    async def get_all_worker_mappings(self, project_alias: str) -> dict[str, str]:
        """Get worker_id -> local_uuid mapping for a given project alias."""
        query = "SELECT worker_id, local_uuid FROM projects WHERE project_alias = ?"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (project_alias,)) as cursor:
                rows = await cursor.fetchall()
                return {r["worker_id"]: r["local_uuid"] for r in rows}

    async def update_last_accessed(self, project_alias: str, worker_id: str) -> None:
        """Update last_accessed timestamp for a project."""
        now = datetime.now(timezone.utc).isoformat()
        query = "UPDATE projects SET last_accessed = ? WHERE project_alias = ? AND worker_id = ?"
        async with get_db_connection(self.db_path) as db:
            await db.execute(query, (now, project_alias, worker_id))
            await db.commit()

    async def delete_project(self, project_alias: str, worker_id: str | None = None) -> bool:
        """Delete project mapping(s). If worker_id is None, deletes for all workers."""
        if worker_id:
            query = "DELETE FROM projects WHERE project_alias = ? AND worker_id = ?"
            params = (project_alias, worker_id)
        else:
            query = "DELETE FROM projects WHERE project_alias = ?"
            params = (project_alias,)

        async with get_db_connection(self.db_path) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.rowcount > 0
