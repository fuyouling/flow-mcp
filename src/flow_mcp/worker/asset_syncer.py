"""AssetSyncer: JIT download of assets from Master AssetHub to Worker."""
from __future__ import annotations

from pathlib import Path
import httpx
from loguru import logger

from flow_mcp.config import get_settings
from flow_mcp.models.asset import AssetKind
from flow_mcp.pages.character_page import CharacterPage
from flow_mcp.pages.image_page import ImagePage


class AssetSyncer:
    """
    Downloads assets from Master AssetHub via HTTP and uploads them into Worker's Flow projects.
    """

    def __init__(self, master_http_url: str | None = None, cache_dir: Path | str | None = None):
        settings = get_settings()
        self.master_http_url = (master_http_url or settings.master_http_url).rstrip("/")
        self.cache_dir = Path(cache_dir or (Path(settings.chrome_download_dir) / "asset_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def download_from_hub(self, asset_name: str) -> Path:
        """Download asset from Master AssetHub if not already in local cache."""
        # Check if already cached
        matching = list(self.cache_dir.glob(f"{asset_name}.*")) + list(self.cache_dir.glob(asset_name))
        if matching:
            return matching[0]

        url = f"{self.master_http_url}/assets/{asset_name}"
        logger.info(f"Downloading asset '{asset_name}' from Master AssetHub: {url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to download asset {asset_name} from Master: HTTP {resp.status_code}")

            # Guess filename or default
            ext = ".bin"
            content_disp = resp.headers.get("content-disposition", "")
            if "filename=" in content_disp:
                ext = Path(content_disp.split("filename=")[-1].strip('"\'')).suffix or ext

            dest = self.cache_dir / f"{asset_name}{ext}"
            with dest.open("wb") as f:
                f.write(resp.content)

            logger.info(f"Asset '{asset_name}' downloaded to: {dest}")
            return dest

    async def sync_to_flow_project(
        self,
        tab,
        project_url: str,
        asset_name: str,
        kind: AssetKind = AssetKind.IMAGE,
    ) -> None:
        """Ensure asset is uploaded to the specified Flow project."""
        local_file = await self.download_from_hub(asset_name)

        logger.info(f"Syncing asset '{asset_name}' ({kind.value}) to project {project_url}...")
        if kind == AssetKind.IMAGE:
            page = ImagePage(tab)
            page.upload_image_on_project_page(
                project_url=project_url,
                image_path=str(local_file),
                target_name=asset_name,
            )
        elif kind == AssetKind.CHARACTER:
            page = CharacterPage(tab)
            page.navigate_to_characters(project_url)
            page.click_new_character()
            page.upload_portrait(str(local_file))
            page.save_character()
        logger.info(f"Asset '{asset_name}' successfully synced into Flow project.")
