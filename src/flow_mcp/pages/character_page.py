"""Page Object Model for Character operations in Google Flow."""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from flow_mcp.config import get_settings
from flow_mcp.pages.base_page import BasePage


class CharacterPage(BasePage):
    """
    Page Object Model for Character Creation and management in Google Flow.
    """

    def navigate_to_characters(self, project_url: str) -> None:
        """Navigate to project characters tab."""
        logger.info(f"Navigating to characters tab at {project_url}...")
        if self.tab.url != project_url:
            self.tab.get(project_url)
            time.sleep(3)

        char_btn = self.tab.ele(
            'xpath://mat-list-item[.//span[contains(text(), "角色") or contains(text(), "Character")]]',
            timeout=3,
        )
        if char_btn:
            char_btn.click()
            time.sleep(2)
        else:
            logger.warning("Character button not found in sidebar.")

    def click_new_character(self) -> bool:
        """Click 'New Character' button."""
        logger.info("Clicking 'New Character' button...")
        new_btn = self.tab.ele(
            'xpath://button[contains(., "创建角色") or contains(., "新建角色") or contains(., "角色") or contains(., "New Character")]',
            timeout=3,
        )
        if new_btn:
            new_btn.click()
            time.sleep(2)
            return True
        logger.warning("New Character button not found.")
        return False

    def _safe_input_prompt(self, editor: Any, prompt: str) -> None:
        """Input prompt text into character editor without triggering popup triggers."""
        if getattr(editor, "tag", "").lower() == "textarea":
            editor.run_js(
                "this.value = arguments[0]; this.dispatchEvent(new Event('input', {bubbles: true}));",
                prompt,
            )
        else:
            js = """
            const dataTransfer = new DataTransfer();
            dataTransfer.setData('text/plain', arguments[0]);
            const event = new ClipboardEvent('paste', {
                clipboardData: dataTransfer,
                bubbles: true,
                cancelable: true
            });
            this.dispatchEvent(event);
            """
            editor.run_js(js, prompt)

    def _wait_for_generation_complete(self, max_wait: int = 300) -> str:
        """Wait for character image generation to finish."""
        initial_imgs = self.tab.eles('css:img[src*="flow-content.google/image/"]')
        initial_count = len(initial_imgs) if initial_imgs else 0

        start_time = time.time()
        while time.time() - start_time < max_wait:
            err = self.tab.ele("css:.error-message", timeout=0)
            if err and ("失败" in err.text or "failed" in err.text.lower()):
                retry = self.tab.ele('xpath://button[contains(., "重试") or contains(., "Retry")]', timeout=0)
                if retry:
                    retry.click()
                    time.sleep(2)
                    continue
                raise RuntimeError(f"Generation failed: {err.text}")

            current_imgs = self.tab.eles('css:img[src*="flow-content.google/image/"]')
            current_count = len(current_imgs) if current_imgs else 0

            if current_count > initial_count:
                new_img = current_imgs[-1]
                time.sleep(1)
                try:
                    b64 = new_img.get_screenshot(as_base64="png")
                    if b64:
                        return b64
                except Exception:
                    pass
                return new_img.attr("src") or ""

            time.sleep(2)

        raise TimeoutError("Timeout waiting for character image generation.")

    def generate_portrait(self, prompt: str, model_name: str = "Nano banana pro") -> str:
        """Generate character portrait."""
        logger.info(f"Generating character portrait (model={model_name})...")
        editor = self.tab.ele("css:.ProseMirror", timeout=3) or self.tab.ele("css:textarea")
        if editor:
            editor.click()
            editor.clear()
            self._safe_input_prompt(editor, prompt)
            time.sleep(1)

        gen_btn = self.tab.ele('xpath://button[@type="submit"]', timeout=3)
        if gen_btn:
            gen_btn.click()
            time.sleep(2)

        return self._wait_for_generation_complete()

    def generate_fullbody(self, prompt: str, model_name: str = "Nano banana pro") -> str:
        """Generate full body character image."""
        logger.info("Generating character full body...")
        fullbody_btn = self.tab.ele(
            'xpath://button[contains(., "生成全身") or contains(., "full body") or contains(., "全身")]',
            timeout=3,
        )
        if fullbody_btn:
            fullbody_btn.click(by_js=True)
            time.sleep(2)

        editor = self.tab.ele("css:.ProseMirror", timeout=3) or self.tab.ele("css:textarea")
        if editor:
            editor.click()
            editor.clear()
            self._safe_input_prompt(editor, prompt)
            time.sleep(1)

        gen_btn = self.tab.ele('xpath://button[@type="submit"]', timeout=3)
        if gen_btn:
            gen_btn.click()
            time.sleep(2)

        return self._wait_for_generation_complete()

    def upload_portrait(self, portrait_path: str, timeout: int = 30) -> bool:
        """Upload portrait image file using CDP interception."""
        path_obj = Path(portrait_path)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Portrait file not found: {portrait_path}")

        abs_path = str(path_obj.resolve())
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

            dl_btn = self.tab.ele('xpath://button[@aria-label="下载图片"]', timeout=1)
            if dl_btn:
                logger.info("Portrait upload completed successfully.")
                return True
            time.sleep(1)

        raise TimeoutError(f"Timeout ({timeout}s) waiting for portrait upload completion.")

    def download_character_image(self, target_stem: str, timeout: int = 60) -> str | None:
        """Download character image and rename to target_stem."""
        settings = get_settings()
        download_dir = Path(settings.chrome_download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)

        existing_files = set(download_dir.iterdir())
        start_time = time.time()

        download_btn = self.tab.ele('xpath://button[@aria-label="下载图片"]', timeout=5)
        if not download_btn:
            logger.warning("Download character image button not found.")
            return None

        try:
            download_btn.click()
        except Exception:
            download_btn.click(by_js=True)

        downloaded_file = None
        while time.time() - start_time < timeout:
            time.sleep(1)
            try:
                for file in download_dir.iterdir():
                    if not file.is_file():
                        continue
                    fname = file.name
                    if fname.endswith(".crdownload") or fname.endswith(".tmp"):
                        continue
                    if file not in existing_files and file.stat().st_size > 0:
                        downloaded_file = file
                        break
            except Exception:
                continue
            if downloaded_file:
                break

        if not downloaded_file:
            logger.warning("Character image download timed out.")
            return None

        ext = downloaded_file.suffix or ".png"
        target_file = download_dir / f"{target_stem}{ext}"
        try:
            if target_file.exists():
                target_file.unlink()
            downloaded_file.rename(target_file)
            return str(target_file.resolve())
        except Exception:
            shutil.move(str(downloaded_file), str(target_file))
            return str(target_file.resolve())

    def save_character(self) -> bool:
        """Click Done/Save button for character."""
        done_btn = self.tab.ele('xpath://button[contains(., "完成") or contains(., "Done")]', timeout=3)
        if done_btn:
            done_btn.click()
            time.sleep(2)
            return True
        return False

    def list_characters(self, project_url: str = "") -> list[dict[str, Any]]:
        """List characters in project."""
        if project_url and project_url not in (self.tab.url or ""):
            self.tab.get(project_url)
            time.sleep(3)

        char_btn = self.tab.ele('xpath://mat-list-item//span[text()="角色"]', timeout=3)
        if not char_btn:
            char_btn = self.tab.ele('xpath://mat-list-item[.//span[contains(text(), "角色") or text()="Characters"]]', timeout=1)
        if char_btn:
            char_btn.click()
            time.sleep(2)

        tiles = self.tab.eles("xpath://flow-character-tile")
        if not tiles:
            tiles = self.tab.eles('xpath://*[contains(@class, "flow-character-tile")]')

        characters = []
        for idx, tile in enumerate(tiles):
            name_ele = tile.ele("xpath:.//flow-tile-hover-footer/div/span", timeout=0) or tile.ele("xpath:.//span", timeout=0)
            name = name_ele.text.strip() if name_ele else ""
            img_ele = tile.ele("css:img", timeout=0)
            thumbnail_url = img_ele.attr("src") if img_ele else ""
            characters.append({"index": idx + 1, "name": name, "thumbnail_url": thumbnail_url})
        return characters
