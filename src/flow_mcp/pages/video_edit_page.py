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
        rename_input = self.find_input(
            ["tag:input@@class=editable-text-input", "css:input.editable-text-input"],
            name="视频重命名输入框",
            timeout=5,
        )

        if not rename_input:
            logger.warning("Rename input field not found on video edit page.")
            return False

        self.click_btn(rename_input, name="视频重命名输入框")
        time.sleep(0.3)

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
            self.input_text(rename_input, new_name, name="视频重命名输入框", clear=False)
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

        # 1. Click download button: //button[@aria-label="下载媒体内容"]
        download_btn = self.find_button('xpath://button[@aria-label="下载媒体内容"]', name="'下载媒体内容'按钮", timeout=5)
        if not download_btn:
            logger.warning("Download button (//button[@aria-label='下载媒体内容']) not found on edit page!")
            return None

        self.click_btn(download_btn, name="'下载媒体内容'按钮")
        time.sleep(1)

        # 2. Click resolution button: //span[text()="{resolution}"]
        res_btn = self.find_button(
            [
                f'xpath://span[text()="{resolution}"]',
                f'xpath://*[contains(normalize-space(text()), "{resolution}")]',
                f'text:{resolution}',
            ],
            name=f"视频分辨率'{resolution}'选项按钮",
            timeout=5,
            silent_fail=True,
        )

        if not res_btn:
            logger.info("Resolution button not found after 5s. Retrying download button click...")
            self.click_btn(download_btn, name="'下载媒体内容'按钮(重试)", by_js=True)
            time.sleep(1)
            res_btn = self.find_button(
                [
                    f'xpath://span[text()="{resolution}"]',
                    f'xpath://*[contains(normalize-space(text()), "{resolution}")]',
                    f'text:{resolution}',
                ],
                name=f"视频分辨率'{resolution}'选项按钮",
                timeout=3,
            )

        if not res_btn:
            logger.warning(f"Resolution button for '{resolution}' not found!")
            return None

        self.click_btn(res_btn, name=f"视频分辨率'{resolution}'选项按钮")

        # 3. Wait for file download to complete
        logger.info(f"Waiting up to {timeout}s for video file starting with '{expected_prefix}' in {download_dir}...")
        poll_interval = 2
        while time.time() - start_time < timeout:
            time.sleep(poll_interval)
            try:
                current_files = list(download_dir.iterdir())
            except Exception as e:
                logger.warning(f"Error scanning download directory: {e}")
                continue

            for file in current_files:
                if not file.is_file():
                    continue

                fname = file.name
                matches_prefix = fname.startswith(expected_prefix) if expected_prefix else True
                if not matches_prefix:
                    continue

                # Ignore unfinished temporary download files
                if fname.endswith('.crdownload') or fname.endswith('.tmp'):
                    continue

                # Ensure it's a new or updated file with content
                if file not in existing_files:
                    try:
                        if file.stat().st_size > 0:
                            logger.info(f"Video download complete: {file.resolve()}")
                            return str(file.resolve())
                    except Exception:
                        pass
                else:
                    try:
                        stat = file.stat()
                        if stat.st_mtime >= start_time - 1 and stat.st_size > 0:
                            logger.info(f"Video download complete (updated file): {file.resolve()}")
                            return str(file.resolve())
                    except Exception:
                        pass

        logger.warning(f"Video download timed out after {timeout}s waiting for file with prefix '{expected_prefix}'")
        return None

    def save_and_close(self) -> None:
        """Click the Done/Save button to close the edit view."""
        logger.info("Attempting to click Done/Save button")
        done_btn = self.find_button('xpath://button[@aria-label="完成场景编辑"]', name="'完成场景编辑'按钮", timeout=5)
        if done_btn:
            self.click_btn(done_btn, name="'完成场景编辑'按钮")
            time.sleep(1)
        else:
            logger.warning("Done/Save button not found.")
