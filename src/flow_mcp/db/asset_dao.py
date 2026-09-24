"""Data Access Object for Asset Registry."""
from __future__ import annotations

import aiosqlite

from flow_mcp.db.connection import get_db_connection
from flow_mcp.models.asset import AssetKind, AssetRecord


def _row_to_asset(row: aiosqlite.Row) -> AssetRecord:
    return AssetRecord(
        name=row["name"],
        kind=AssetKind(row["kind"]),
        file_name=row["file_name"],
        file_path=row["file_path"],
        file_size=row["file_size"],
        sha256=row["sha256"] or "",
        created_by_worker=row["created_by_worker"] or "",
        source_job_id=row["source_job_id"] or "",
        created_at=row["created_at"],
    )


class AssetDAO:
    """Async DAO for asset records in Master AssetHub."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    async def insert_asset(self, record: AssetRecord) -> None:
        """Register a new asset record."""
        query = """
        INSERT INTO assets (
            name, kind, file_name, file_path, file_size,
            sha256, created_by_worker, source_job_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            file_name = excluded.file_name,
            file_path = excluded.file_path,
            file_size = excluded.file_size,
            sha256 = excluded.sha256,
            created_by_worker = excluded.created_by_worker,
            source_job_id = excluded.source_job_id
        """
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                query,
                (
                    record.name,
                    record.kind.value,
                    record.file_name,
                    record.file_path,
                    record.file_size,
                    record.sha256,
                    record.created_by_worker,
                    record.source_job_id,
                    record.created_at,
                ),
            )
            await db.commit()

    async def get_asset(self, name: str) -> AssetRecord | None:
        """Retrieve asset record by logical name."""
        query = "SELECT * FROM assets WHERE name = ?"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (name,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return _row_to_asset(row)

    async def find_by_sha256(self, sha256: str) -> AssetRecord | None:
        """Check if an asset with this sha256 already exists (for deduplication)."""
        if not sha256:
            return None
        query = "SELECT * FROM assets WHERE sha256 = ? LIMIT 1"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (sha256,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return _row_to_asset(row)

    async def list_assets(
        self, kind: AssetKind | None = None, limit: int = 100
    ) -> list[AssetRecord]:
        """List asset records, optionally filtered by kind."""
        if kind:
            query = "SELECT * FROM assets WHERE kind = ? ORDER BY created_at DESC LIMIT ?"
            params = (kind.value, limit)
        else:
            query = "SELECT * FROM assets ORDER BY created_at DESC LIMIT ?"
            params = (limit,)

        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_asset(r) for r in rows]

    async def exists(self, name: str) -> bool:
        """Check if an asset name exists."""
        query = "SELECT 1 FROM assets WHERE name = ? LIMIT 1"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (name,)) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def delete_asset(self, name: str) -> bool:
        """Delete asset record from DB."""
        query = "DELETE FROM assets WHERE name = ?"
        async with get_db_connection(self.db_path) as db:
            cursor = await db.execute(query, (name,))
            await db.commit()
            return cursor.rowcount > 0
