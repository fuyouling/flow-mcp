"""Page Object Model for Video operations in Google Flow."""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable, Optional
from loguru import logger

from flow_mcp.pages.base_page import BasePage
from flow_mcp.pages.video_edit_page import VideoEditPage


class VideoPage(BasePage):
    """
    Page Object Model for video generation, listing, and uploading in Google Flow.
    """

    def apply_settings(
        self,
        model_name: str = "Omni 1.1 Flash",
        resolution: str = "720p",
        quantity: str = "x1",
    ) -> None:
        """Configure video generation settings panel."""
        time.sleep(1)

        # Open settings panel
        settings_btn = self.tab.ele("tag:button@@aria-label=设置", timeout=2)
        if not settings_btn:
            candidates = self.tab.eles("tag:button@@text():设置")
            if candidates:
                settings_btn = candidates[-1]

        if settings_btn:
            settings_btn.click()
            time.sleep(0.8)

        # Switch to video tab
        vid_tab = self.tab.ele('xpath://span[text()="视频" and @class="toggle-text"]', timeout=2)
        if not vid_tab:
            vid_tab = self.tab.ele("tag:button@@text()=视频", timeout=1)

        if vid_tab:
            vid_tab.click()
            time.sleep(0.5)

        # Model dropdown
        dropdown = self.tab.ele("tag:button@@text():arrow_drop_down", timeout=1)
        if dropdown:
            dropdown.click()
            time.sleep(0.5)
            options = self.tab.eles(f"tag:button@@text():{model_name}")
            for opt in options:
                if "arrow_drop_down" not in opt.text:
                    opt.click()
                    time.sleep(0.3)
                    break

        # Resolution
        res_btn = self.tab.ele(f"tag:button@@text():{resolution}", timeout=1)
        if res_btn:
            res_btn.click()
            time.sleep(0.3)

        # Quantity
        qty_btn = self.tab.ele(f"tag:button@@text()={quantity}", timeout=1)
        if qty_btn:
            qty_btn.click()
            time.sleep(0.3)

        # Close settings panel via ESC
        self.tab.run_cdp("Input.dispatchKeyEvent", type="rawKeyDown", windowsVirtualKeyCode=27)
        self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=27)
        time.sleep(0.5)

    def add_assets_to_prompt(self, assets: list[str]) -> None:
        """Add asset references to video prompt."""
        for asset in assets:
            if not asset.strip():
                continue
            add_btn = self.tab.ele("@@aria-label=显示素材", timeout=2)
            if not add_btn:
                add_btn = self.tab.ele('xpath://button[contains(@aria-label, "素材") or contains(., "素材")]', timeout=1)
            if not add_btn:
                continue

            add_btn.click()
            time.sleep(0.8)

            search_input = self.tab.ele('xpath://input[@class="search-input" and @placeholder="搜索"]', timeout=2)
            if search_input:
                search_input.clear()
                search_input.input(asset.strip())
                time.sleep(1.2)
                add_prompt_btn = self.tab.ele("tag:button@@text():添加到提示", timeout=2)
                if add_prompt_btn:
                    add_prompt_btn.click()
                    time.sleep(0.8)
                else:
                    self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=27)
                    time.sleep(0.3)

    def enter_prompt(self, prompt: str) -> None:
        """Type prompt into rich text editor."""
        editor = self.tab.ele(
            'xpath://flow-rich-text-editor[@class="prompt-input"]//div[@contenteditable="true"]',
            timeout=3,
        )
        if not editor:
            editor = self.tab.ele('xpath://flow-rich-text-editor[@class="prompt-input"]', timeout=2)

        if not editor:
            raise RuntimeError("Video prompt input editor element not found.")

        editor.click()
        time.sleep(0.3)

        try:
            self.tab.run_cdp("Input.insertText", text=prompt)
            time.sleep(0.5)
            val = self.tab.run_js(
                "return (document.querySelector('flow-rich-text-editor.prompt-input div[contenteditable=\"true\"]') || {}).innerText || '';"
            )
            if prompt.strip() in val.strip():
                return
        except Exception:
            pass

        try:
            editor.input(prompt)
        except Exception as e:
            raise RuntimeError(f"Failed to enter video prompt: {e}") from e

    def generate_video(
        self,
        project_url: str,
        prompt: str,
        model_name: str = "Omni 1.1 Flash",
        resolution: str = "720p",
        quantity: str = "x1",
        assets: list[str] | None = None,
        rename_name: str = "",
        download: str = "720p",
        progress_callback: Optional[Callable[[int, str], None]] = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Execute full video creation flow."""
        logger.info(f"Generating video in {project_url} with model {model_name}...")
        if self.tab.url != project_url:
            self.tab.get(project_url)
            time.sleep(3)

        self.apply_settings(model_name, resolution, quantity)

        if assets:
            self.add_assets_to_prompt(assets)

        self.enter_prompt(prompt)
        time.sleep(0.5)

        submit_btn = self.tab.ele('xpath://button[@type="submit"]', timeout=5)
        if not submit_btn or submit_btn.attr("disabled"):
            raise RuntimeError("Video submit button not clickable.")

        submit_btn.click()
        logger.info("Clicked generate video button, polling progress...")

        start_time = time.time()
        loading_xpath = 'xpath://div[@class="loading-percentage"]'

        # Wait for loading to start
        for _ in range(40):
            if self.tab.ele(loading_xpath, timeout=0.5):
                break
            time.sleep(0.5)

        # Poll percentage until completed
        while time.time() - start_time < timeout:
            loading_ele = self.tab.ele(loading_xpath, timeout=0.5)
            if not loading_ele:
                break
            text = loading_ele.text or ""
            m = re.search(r"(\d{1,3})", text)
            pct = int(m.group(1)) if m else 0
            if progress_callback:
                progress_callback(pct, text or f"{pct}%")
            time.sleep(3)

        time.sleep(1)

        # Click newest tile to open details
        tile = self.tab.ele("xpath://flow-grid-tile-container[1]", timeout=10)
        if not tile:
            raise RuntimeError("Generated video tile not found.")

        try:
            tile.click()
        except Exception:
            tile.click(by_js=True)
        time.sleep(1)

        edit_page = VideoEditPage(self.tab)
        final_name = rename_name or f"video_{int(time.time())}"
        edit_page.rename(final_name)

        local_path = ""
        if download:
            local_path = edit_page.download_video(resolution=download, expected_prefix=final_name) or ""

        edit_page.save_and_close()

        return {
            "video_name": final_name,
            "local_path": local_path,
        }

    def list_videos(self, project_url: str = "") -> list[dict[str, Any]]:
        """List all videos in the project."""
        if project_url and project_url not in (self.tab.url or ""):
            self.tab.get(project_url)
            time.sleep(3)

        vid_btn = self.tab.ele('xpath://mat-list-item//span[text()="视频"]', timeout=3)
        if not vid_btn:
            vid_btn = self.tab.ele('xpath://mat-list-item[.//span[contains(text(), "视频") or text()="Videos"]]', timeout=1)
        if vid_btn:
            vid_btn.click()
            time.sleep(2)

        tiles = self.tab.eles("xpath://flow-video-tile")
        if not tiles:
            tiles = self.tab.eles('xpath://*[contains(@class, "flow-video-tile")]')

        videos = []
        for idx, tile in enumerate(tiles):
            name_ele = tile.ele("xpath:.//flow-tile-hover-footer/div/span", timeout=0) or tile.ele("xpath:.//span", timeout=0)
            name = name_ele.text.strip() if name_ele else ""
            img_ele = tile.ele("css:img, css:video", timeout=0)
            thumbnail_url = img_ele.attr("src") if img_ele else ""
            videos.append({"index": idx + 1, "name": name, "thumbnail_url": thumbnail_url})
        return videos

    def upload_video_on_project_page(
        self, project_url: str, video_path: str, target_name: str = "", timeout: int = 90
    ) -> bool:
        """Upload a local video file into the project."""
        path_obj = Path(video_path)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        abs_path = str(path_obj.resolve())
        file_stem = path_obj.stem

        if project_url not in (self.tab.url or ""):
            self.tab.get(project_url)
            time.sleep(3)

        add_btn = self.tab.ele('xpath://button[@mattooltip="添加媒体"]', timeout=5)
        if not add_btn:
            add_btn = self.tab.ele('xpath://button[contains(@mattooltip, "添加媒体") or contains(@aria-label, "添加媒体")]', timeout=2)
        if not add_btn:
            raise RuntimeError("Add media button not found.")

        try:
            add_btn.click()
        except Exception:
            add_btn.click(by_js=True)
        time.sleep(0.8)

        self.tab.set.upload_files(abs_path)

        upload_btn = self.tab.ele('xpath://span[text()="上传"]', timeout=5)
        if not upload_btn:
            upload_btn = self.tab.ele('xpath://button[contains(., "上传")]', timeout=2)
        if not upload_btn:
            raise RuntimeError("Upload button not found.")

        try:
            upload_btn.click()
        except Exception:
            upload_btn.click(by_js=True)

        start_time = time.time()
        uploaded_tile = None
        while time.time() - start_time < timeout:
            agree_btn = self.tab.ele('xpath://span[text()="我同意，不再提示"]', timeout=0)
            if not agree_btn:
                agree_btn = self.tab.ele('xpath://button[contains(., "同意")]', timeout=0)
            if agree_btn:
                try:
                    agree_btn.click()
                except Exception:
                    agree_btn.click(by_js=True)
                time.sleep(1)

            first_span = self.tab.ele("xpath:(//flow-grid-tile-container)[1]//span", timeout=0.5)
            if first_span:
                span_text = first_span.text.strip()
                if file_stem.lower() in span_text.lower():
                    uploaded_tile = self.tab.ele("xpath:(//flow-grid-tile-container)[1]", timeout=1)
                    break
            time.sleep(1)

        if not uploaded_tile:
            raise TimeoutError(f"Timeout waiting for uploaded video tile '{file_stem}' to appear.")

        if target_name:
            try:
                uploaded_tile.click()
                time.sleep(1)
                edit_page = VideoEditPage(self.tab)
                edit_page.rename(target_name)
                edit_page.save_and_close()
            except Exception as e:
                logger.warning(f"Error renaming uploaded video to {target_name}: {e}")

        return True
