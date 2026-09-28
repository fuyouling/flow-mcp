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
        kind: AssetKind | None = None,
    ) -> None:
        """Ensure asset is uploaded to the specified Flow project."""
        try:
            local_file = await self.download_from_hub(asset_name)
            
            # Infer kind from extension if not provided or if it defaults to IMAGE
            # since executor sometimes calls this without knowing the exact kind.
            ext = local_file.suffix.lower()
            if kind is None or kind == AssetKind.IMAGE:
                if ext in [".mp4", ".mov", ".webm", ".avi", ".mkv"]:
                    kind = AssetKind.VIDEO
                else:
                    kind = AssetKind.IMAGE

            logger.info(f"Syncing asset '{asset_name}' ({kind.value}) to project {project_url}...")
            
            if kind == AssetKind.IMAGE:
                logger.debug(f"Uploading image asset '{asset_name}'...")
                page = ImagePage(tab)
                page.upload_image_on_project_page(
                    project_url=project_url,
                    image_path=str(local_file),
                    target_name=asset_name,
                )
            elif kind == AssetKind.VIDEO:
                logger.debug(f"Uploading video asset '{asset_name}'...")
                from flow_mcp.pages.video_page import VideoPage
                page = VideoPage(tab)
                page.upload_video_on_project_page(
                    project_url=project_url,
                    video_path=str(local_file),
                    target_name=asset_name,
                )
            elif kind == AssetKind.CHARACTER:
                logger.warning("AssetKind.CHARACTER should use sync_character_to_flow_project directly.")
                
            logger.info(f"Asset '{asset_name}' successfully synced into Flow project.")
        except Exception as e:
            kind_val = kind.value if kind else "unknown"
            logger.error(f"Failed to sync asset '{asset_name}' ({kind_val}) to project {project_url}: {e}")
            raise

    async def sync_character_to_flow_project(
        self,
        tab,
        project_url: str,
        character_name: str,
        has_portrait: bool,
        has_fullbody: bool,
        voice_name: str = "",
        voice_style: str = "",
    ) -> None:
        """Download character assets and recreate the character on the worker's project."""
        logger.info(f"Syncing character '{character_name}' to project {project_url}...")
        
        try:
            portrait_local = None
            if has_portrait:
                logger.debug(f"Downloading portrait for character '{character_name}'...")
                portrait_local = await self.download_from_hub(f"{character_name}_Portrait")
                
            fullbody_local = None
            if has_fullbody:
                logger.debug(f"Downloading fullbody for character '{character_name}'...")
                fullbody_local = await self.download_from_hub(f"{character_name}_Fullbody")
                
            page = CharacterPage(tab)
            logger.debug(f"Navigating to characters tab for project '{project_url}'...")
            page.navigate_to_characters(project_url)
            
            logger.debug(f"Clicking 'New Character' for '{character_name}'...")
            if not page.click_new_character():
                logger.warning(f"Failed to click 'New Character' or editor not ready for '{character_name}'.")
            
            if portrait_local:
                logger.debug(f"Uploading portrait for character '{character_name}'...")
                page.upload_portrait(str(portrait_local))
                
            if fullbody_local:
                logger.debug(f"Uploading fullbody for character '{character_name}'...")
                page.upload_fullbody(str(fullbody_local))
                
            if voice_name:
                logger.debug(f"Configuring voice '{voice_name}' for character '{character_name}'...")
                page.configure_voice(voice_name, voice_style)
                
            logger.debug(f"Renaming character to '{character_name}'...")
            page.rename_character(character_name)
            
            logger.debug(f"Saving character '{character_name}'...")
            page.save_character()
            logger.info(f"Character '{character_name}' successfully synced into Flow project.")
            
        except Exception as e:
            logger.error(f"Failed to sync character '{character_name}' to project {project_url}: {e}")
            raise
