"""Page Object Model for the video edit/detail interface in Google Flow."""
from __future__ import annotations

import time
from pathlib import Path
from loguru import logger

from flow_mcp.config import get_settings
from flow_mcp.pages.base_page import BasePage


class VideoEditPage(BasePage):
    """
    Page Object Model for video details and editing in Google Flow.
    URL pattern: https://flow.google.com/project/{project_id}/edit/{media_id}
    """

    def open(self, project_id: str, media_id: str) -> None:
        """Open the specific video edit page."""
        url = f"https://flow.google.com/project/{project_id}/edit/{media_id}"
        logger.info(f"Opening Video Edit Page: {url}")
        self.tab.get(url)
        time.sleep(3)

    def rename(self, new_name: str) -> bool:
        """Rename the video media via CDP events."""
        logger.info(f"Renaming video media to '{new_name}' via CDP...")
        rename_input = self.tab.ele("tag:input@@class=editable-text-input", timeout=5)
        if not rename_input:
            rename_input = self.tab.ele("css:input.editable-text-input", timeout=2)

        if not rename_input:
            logger.warning("Rename input field not found on video edit page.")
            return False

        try:
            rename_input.click()
            time.sleep(0.3)
        except Exception:
            pass

        try:
            # Select all (Ctrl+A)
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=65, modifiers=2)
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=65, modifiers=2)
            time.sleep(0.1)

            # Backspace
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=8)
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=8)
            time.sleep(0.1)

            # Input text
            rename_input.input(new_name)
            time.sleep(0.2)

            # Enter
            self.tab.run_cdp(
                "Input.dispatchKeyEvent",
                type="rawKeyDown",
                windowsVirtualKeyCode=13,
                key="Enter",
                code="Enter",
                text="\r",
                unmodifiedText="\r",
            )
            self.tab.run_cdp(
                "Input.dispatchKeyEvent",
                type="char",
                windowsVirtualKeyCode=13,
                key="Enter",
                code="Enter",
                text="\r",
                unmodifiedText="\r",
            )
            self.tab.run_cdp(
                "Input.dispatchKeyEvent",
                type="keyUp",
                windowsVirtualKeyCode=13,
                key="Enter",
                code="Enter",
            )
            time.sleep(0.8)
        except Exception as e:
            logger.warning(f"CDP video rename keystroke failure: {e}")

        final_val = rename_input.property("value")
        return final_val == new_name

    def download_video(
        self, resolution: str = "720p", expected_prefix: str = "", timeout: int = 180
    ) -> str | None:
        """
        Download video in specified resolution ('270p', '720p', '1080p').
        Returns the absolute local path of the downloaded video.
        """
        resolution = resolution.strip().lower()
        if resolution not in ("270p", "720p", "1080p"):
            logger.warning(f"Unsupported video resolution: {resolution}, defaulting to 720p")
            resolution = "720p"

        settings = get_settings()
        download_dir = Path(settings.chrome_download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)

        existing_files = set(download_dir.iterdir())
        start_time = time.time()

        # 1. Click download button
        download_btn = self.tab.ele(
            'xpath://button[@aria-label="下载媒体" or @aria-label="Download media"]', timeout=5
        )
        if not download_btn:
            download_btn = self.tab.ele('xpath://button[contains(@aria-label, "下载")]', timeout=2)

        if not download_btn:
            logger.warning("Download button not found on video edit page.")
            return None

        try:
            download_btn.click()
            time.sleep(0.8)
        except Exception:
            download_btn.click(by_js=True)
            time.sleep(0.8)

        # 2. Select resolution option
        res_btn = self.tab.ele(f'xpath://span[text()="{resolution}"]', timeout=5)
        if not res_btn:
            res_btn = self.tab.ele(f'xpath://button[contains(., "{resolution}")]', timeout=2)

        if not res_btn:
            logger.warning(f"Resolution button '{resolution}' not found.")
            return None

        try:
            res_btn.click()
        except Exception:
            res_btn.click(by_js=True)

        logger.info(f"Triggered {resolution} video download, polling {download_dir}...")

        # 3. Poll download directory
        while time.time() - start_time < timeout:
            time.sleep(2)
            try:
                current_files = list(download_dir.iterdir())
            except Exception:
                continue

            for file in current_files:
                if not file.is_file():
                    continue
                fname = file.name
                if expected_prefix and not fname.startswith(expected_prefix):
                    continue
                if fname.endswith(".crdownload") or fname.endswith(".tmp"):
                    continue

                if file not in existing_files:
                    try:
                        if file.stat().st_size > 0:
                            logger.info(f"Video downloaded: {file.resolve()}")
                            return str(file.resolve())
                    except Exception:
                        pass
                else:
                    try:
                        stat = file.stat()
                        if stat.st_mtime >= start_time - 1 and stat.st_size > 0:
                            return str(file.resolve())
                    except Exception:
                        pass

        logger.warning(f"Download timed out after {timeout}s waiting for video prefix '{expected_prefix}'")
        return None

    def save_and_close(self) -> None:
        """Click Done/Save button to exit edit view."""
        btn = self.tab.ele(
            'xpath://button[@aria-label="完成修改" or @aria-label="完成编辑" or @aria-label="Done" or @aria-label="Save"]',
            timeout=3,
        )
        if btn:
            try:
                btn.click()
                time.sleep(0.5)
            except Exception:
                pass
