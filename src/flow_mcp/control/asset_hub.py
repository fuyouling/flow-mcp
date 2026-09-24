"""AssetHub: Centralized file store and asset registry on Master."""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

from loguru import logger

from flow_mcp.config import get_settings
from flow_mcp.db.asset_dao import AssetDAO
from flow_mcp.models.asset import AssetKind, AssetRecord
from flow_mcp.utils.errors import AssetNotFoundError


def compute_sha256(path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


class AssetHub:
    """
    AssetHub manages storage, deduplication, and metadata of assets (images, characters, videos).
    """

    def __init__(self, asset_dao: AssetDAO | None = None, base_dir: Path | str | None = None):
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.master_asset_dir).resolve()
        self.images_dir = self.base_dir / "images"
        self.characters_dir = self.base_dir / "characters"
        self.videos_dir = self.base_dir / "videos"

        # Ensure directories exist
        for d in (self.images_dir, self.characters_dir, self.videos_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.dao = asset_dao or AssetDAO()

    def _get_target_dir(self, kind: AssetKind) -> Path:
        if kind == AssetKind.IMAGE:
            return self.images_dir
        elif kind == AssetKind.CHARACTER:
            return self.characters_dir
        elif kind == AssetKind.VIDEO:
            return self.videos_dir
        return self.base_dir

    async def store_asset(
        self,
        source_path: Path | str,
        name: str,
        kind: AssetKind,
        created_by_worker: str = "master",
        source_job_id: str = "",
    ) -> AssetRecord:
        """
        Store a new asset file, compute sha256, and register into DB.
        """
        src = Path(source_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Source asset file does not exist: {src}")

        sha256 = compute_sha256(src)
        file_size = src.stat().st_size
        target_dir = self._get_target_dir(kind)

        # Sanitize filename
        ext = src.suffix or ".bin"
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
        dest_filename = f"{safe_name}_{int(time.time())}{ext}"
        dest_path = target_dir / dest_filename

        shutil.copy2(str(src), str(dest_path))

        record = AssetRecord(
            name=name,
            kind=kind,
            file_name=dest_filename,
            file_path=str(dest_path.resolve()),
            file_size=file_size,
            sha256=sha256,
            created_by_worker=created_by_worker,
            source_job_id=source_job_id,
            created_at=time.time(),
        )

        await self.dao.insert_asset(record)
        logger.info(f"Asset stored in AssetHub: {name} ({kind.value}) -> {dest_path}")
        return record

    async def get_asset(self, name: str) -> AssetRecord:
        """Fetch asset metadata, raises AssetNotFoundError if not registered."""
        record = await self.dao.get_asset(name)
        if not record:
            raise AssetNotFoundError(f"Asset '{name}' not found in AssetHub registry.")
        return record

    async def get_file_path(self, name: str) -> Path:
        """Get absolute path of an asset file."""
        record = await self.get_asset(name)
        p = Path(record.file_path)
        if not p.is_file():
            raise AssetNotFoundError(f"Asset file on disk missing for '{name}': {p}")
        return p

    async def find_by_sha256(self, sha256: str) -> AssetRecord | None:
        """Find an asset by its content hash."""
        return await self.dao.find_by_sha256(sha256)

    async def list_assets(self, kind: AssetKind | None = None, limit: int = 100) -> list[AssetRecord]:
        """List registered assets."""
        return await self.dao.list_assets(kind=kind, limit=limit)

    async def delete_asset(self, name: str) -> bool:
        """Delete asset from registry and disk."""
        record = await self.dao.get_asset(name)
        if not record:
            return False

        try:
            p = Path(record.file_path)
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete asset file on disk ({record.file_path}): {e}")

        return await self.dao.delete_asset(name)
