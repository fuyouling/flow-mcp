"""Page Object Model for Character operations in Google Flow."""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

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
            'xpath://button[contains(., "新角色") or contains(., "新建角色") or contains(., "创建角色") or contains(., "New Character")]',
            timeout=3,
        )
        if new_btn:
            new_btn.click()
            time.sleep(2.5)
            logger.info("Clicked New Character.")
        else:
            logger.warning("New Character button not found. Checking if editor is ready.")

        # Verify editor is ready
        if not self.tab.ele("css:.ProseMirror", timeout=3) and not self.tab.ele("css:textarea", timeout=1):
            logger.error("Editor not found after clicking New Character.")
            return False
        return True

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
            if err and ("失败" in err.text or "failed" in err.text.lower() or "error" in err.text.lower()):  # type: ignore[operator]
                retry = self.tab.ele(
                    'xpath://button[contains(., "重试") or contains(., "Retry") or contains(., "重新生成")]',
                    timeout=0,
                )
                if retry:
                    logger.warning("Generation failed, clicking retry...")
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
                        return b64  # type: ignore[return-value]
                except Exception:
                    pass
                return new_img.attr("src") or ""

            time.sleep(2)

        raise TimeoutError("Timeout waiting for character image generation.")

    def generate_portrait(self, prompt: str, model_name: str = "Nano banana pro") -> str:
        """Generate character portrait."""
        logger.info(f"Generating character portrait (model={model_name})...")
        editor = self.tab.ele("css:.ProseMirror", timeout=3)
        if not editor:
            editor = self.tab.ele("css:textarea")

        if editor:
            editor.click()
            editor.clear()
            self._safe_input_prompt(editor, prompt)
            time.sleep(1)

        if model_name:
            logger.info(f"Selecting model: {model_name}")
            model_btn = self.tab.ele('css:button.model-select-button, button[aria-label*="模型"], button[aria-label*="model"]', timeout=2)
            if model_btn:
                model_btn.click()
                time.sleep(1)
                lower_model = model_name.lower()
                menu_items = self.tab.eles("css:.mat-mdc-menu-item, .mat-menu-item", timeout=2)
                for item in menu_items:
                    if lower_model in (item.text or "").lower():
                        item.click()
                        time.sleep(1)
                        break

        gen_btn = self.tab.ele('xpath://button[@type="submit"]', timeout=5)
        if not gen_btn:
            gen_btn = self.tab.ele('xpath://button[contains(., "生成") or contains(., "Generate")]', timeout=5)

        if gen_btn:
            if gen_btn.attr("disabled"):
                logger.warning("Generate button is disabled, attempting to click anyway...")
            gen_btn.click()
            time.sleep(2)
        else:
            raise RuntimeError("Generate button not found.")

        return self._wait_for_generation_complete()

    def generate_fullbody(self, prompt: str = "", model_name: str = "Nano banana pro") -> str:
        """Generate full body character image."""
        logger.info("Generating fullbody image...")
        fullbody_btn = self.tab.ele(
            'xpath://button[contains(., "生成全身") or contains(., "全身") or contains(., "Full body")]',
            timeout=3,
        )
        if not fullbody_btn:
            logger.warning("Generate Fullbody button not found.")
            return ""

        try:
            fullbody_btn.click(by_js=True)
        except Exception as e:
            logger.warning(f"JS click on fullbody button failed: {e}, attempting regular click...")
            fullbody_btn.click()
        time.sleep(2)

        if prompt:
            editor = self.tab.ele("css:.ProseMirror", timeout=2)
            if not editor:
                editor = self.tab.ele("css:textarea")
            if editor:
                editor.click()
                editor.clear()
                self._safe_input_prompt(editor, prompt)
                time.sleep(1)

        gen_btn = self.tab.ele('xpath://button[@type="submit"]', timeout=5)
        if not gen_btn:
            gen_btn = self.tab.ele('xpath://button[contains(., "生成") or contains(., "Generate")]', timeout=5)

        if gen_btn:
            if gen_btn.attr("disabled"):
                logger.warning("Generate button is disabled, attempting to click anyway...")
            gen_btn.click()
            time.sleep(2)
        else:
            logger.warning("Generate button not found for fullbody.")

        return self._wait_for_generation_complete()

    def configure_voice(self, voice_name: str, voice_style: str) -> bool:
        """Configure voice for the character."""
        if not voice_name:
            return True
            
        logger.info(f"Configuring voice: {voice_name}")
        voice_btn = self.tab.ele('xpath://button[contains(., "选择") or contains(., "voice") or contains(@aria-label, "声音") or contains(@aria-label, "voice")]', timeout=3)
        if not voice_btn:
            logger.error("Could not find Voice button.")
            return False
            
        voice_btn.click()
        import time
        time.sleep(1.5)
        
        search_input = self.tab.ele('css:input[placeholder*="搜"], input[placeholder*="Search"]', timeout=2)
        if search_input:
            search_input.input(voice_name)
            time.sleep(1)
            
        # Check if the voice was found
        not_found = self.tab.ele('xpath://span[contains(text(),"未找到资源")]', timeout=1)
        if not_found:
            logger.warning(f"Voice '{voice_name}' not found.")
            close_btn = self.tab.ele('xpath://button[@aria-label="关闭"]', timeout=2)
            if close_btn:
                close_btn.click()
                time.sleep(1)
        else:
            add_btn = self.tab.ele('xpath://span[contains(text(),"添加到角色")]', timeout=2)
            if add_btn:
                try:
                    add_btn.click()
                except Exception:
                    add_btn.click(by_js=True)
                time.sleep(1)
            
        if voice_style:
            style_input = self.tab.ele('css:textarea[placeholder*="口音"], textarea[placeholder*="accent"]', timeout=1)
            if style_input:
                style_input.input(voice_style)
                time.sleep(0.5)
                
        logger.info("Voice configured successfully.")
        return True

    def rename_character(self, name: str) -> bool:
        """Rename character in character editor."""
        logger.info(f"Renaming character to '{name}'...")
        name_input = self.tab.ele('xpath://input[@placeholder="角色名称"]', timeout=3)
        if not name_input:
            logger.warning("Character name input not found.")
            return False

        name_input.click()
        time.sleep(0.3)
        name_input.clear()
        name_input.input(name)
        time.sleep(0.5)
        return True

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
            agree_btn = self.tab.ele('xpath://span[text()="我同意，不再显示"]', timeout=0)
            if not agree_btn:
                agree_btn = self.tab.ele('xpath://button[contains(., "我同意") or .//span[contains(text(), "我同意")]]', timeout=0)
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

    def upload_fullbody(self, fullbody_path: str, timeout: int = 30) -> bool:
        """
        Upload character fullbody image file.
        Clicks Fullbody tab/button, intercepts file chooser dialog,
        handles agreement dialog, and waits for upload completion.
        """
        path_obj = Path(fullbody_path)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Fullbody image file not found: {fullbody_path}")

        abs_path = str(path_obj.resolve())
        logger.info(f"Initiating fullbody upload for file: {abs_path}")

        # Step 5: Click Fullbody button/tab
        logger.info("Clicking Fullbody button/tab...")
        fullbody_btn = self.tab.ele('xpath://button[contains(., "全身") or contains(., "full body")] | //span[contains(text(), "全身")]', timeout=5)
        if fullbody_btn:
            try:
                fullbody_btn.click(by_js=True)
            except Exception as e:
                logger.warning(f"JS click on fullbody button failed: {e}, attempting regular click...")
                fullbody_btn.click()
            time.sleep(1.5)
        else:
            logger.warning("Could not find Fullbody button/tab. Continuing to look for fullbody upload button...")

        # Count existing download buttons prior to fullbody upload
        existing_dl_btns = self.tab.eles('xpath://button[@aria-label="下载图片"]')
        initial_dl_count = len(existing_dl_btns) if existing_dl_btns else 0

        # Set upload file via CDP interception
        self.tab.set.upload_files(abs_path)

        # Step 6: Locate and click Upload button in fullbody area
        upload_btn = self.tab.ele('xpath://span[text()="上传"] | //span[contains(text(), "上传")]', timeout=5)
        if not upload_btn:
            upload_btn = self.tab.ele('xpath://button[contains(., "上传")]', timeout=2)
        if not upload_btn:
            raise Exception("Could not find fullbody Upload button (//span[contains(text(), '上传')]).")

        try:
            upload_btn.click()
        except Exception as e:
            logger.warning(f"Direct click on fullbody upload button failed: {e}, attempting JS click...")
            upload_btn.click(by_js=True)

        logger.info(f"Waiting up to {timeout}s for fullbody upload to complete...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check for agreement popup
            agree_btn = self.tab.ele('xpath://span[text()="我同意，不再显示"]', timeout=0)
            if not agree_btn:
                agree_btn = self.tab.ele('xpath://button[contains(., "我同意") or .//span[contains(text(), "我同意")]]', timeout=0)
            if agree_btn:
                logger.info("Detected agreement dialog, clicking '我同意，不再显示'...")
                try:
                    agree_btn.click()
                except Exception:
                    agree_btn.click(by_js=True)
                time.sleep(1)

            # Check if a new download button appeared, or if at least one exists
            current_dl_btns = self.tab.eles('xpath://button[@aria-label="下载图片"]')
            current_dl_count = len(current_dl_btns) if current_dl_btns else 0
            if current_dl_count > initial_dl_count or (initial_dl_count == 0 and current_dl_count > 0):
                logger.info("Fullbody upload completed successfully! Download button detected.")
                time.sleep(1)
                return True

            time.sleep(1)

        raise TimeoutError(f"Timeout ({timeout}s) waiting for fullbody upload completion.")

    def download_character_image(self, target_stem: str, timeout: int = 60) -> str | None:
        """Download character image and rename to target_stem."""
        settings = get_settings()
        download_dir = Path(settings.chrome_download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)

        existing_files = set(download_dir.iterdir())
        start_time = time.time()

        download_btn = self.tab.ele('xpath://button[@aria-label="下载图片"]', timeout=5)
        if not download_btn:
            logger.warning("Download character image button (//button[@aria-label='下载图片']) not found.")
            return None

        try:
            download_btn.click()
            time.sleep(1)
        except Exception:
            try:
                download_btn.click(by_js=True)
                time.sleep(1)
            except Exception:
                return None

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
                    if not fname.startswith("图片"):
                        continue
                    if file not in existing_files and file.stat().st_size > 0:
                        downloaded_file = file
                        break
                    elif file.stat().st_mtime >= start_time - 1 and file.stat().st_size > 0:
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
            if target_file.exists():
                target_file.unlink()
            shutil.move(str(downloaded_file), str(target_file))
            return str(target_file.resolve())

    def save_character(self) -> bool:
        """Click Done/Save button for character."""
        done_btn = self.tab.ele('xpath://button[contains(., "完成") or contains(., "Done") or contains(., "保存")]', timeout=3)
        if done_btn:
            done_btn.click()
            time.sleep(2)
            logger.info("Character saved successfully.")
            return True
        return False

    def list_characters(self, project_url: str = "") -> list[dict[str, Any]]:
        """List all characters in the project."""
        if project_url and project_url not in (self.tab.url or ""):
            self.tab.get(project_url)
            time.sleep(3)

        char_btn = self.tab.ele('xpath://mat-list-item//span[text()="角色"]', timeout=3)
        if not char_btn:
            char_btn = self.tab.ele('xpath://mat-list-item[.//span[contains(text(), "角色") or contains(text(), "Character")]]', timeout=1)
        if char_btn:
            char_btn.click()
            time.sleep(2)

        self.tab.ele('xpath://div[contains(@class, "character-tile-container")]', timeout=3)
        tiles = self.tab.eles('xpath://div[@class="character-tile-container"]')
        if not tiles:
            tiles = self.tab.eles('xpath://div[contains(@class, "character-tile-container")]')

        characters = []
        for idx, tile in enumerate(tiles):
            name_ele = tile.ele("xpath:.//span", timeout=0)
            name = name_ele.text.strip() if name_ele else ""
            if not name:
                name = tile.text.strip()

            img_ele = tile.ele("css:img", timeout=0)
            thumbnail_url = img_ele.attr("src") if img_ele else ""
            characters.append({"index": idx + 1, "name": name, "thumbnail_url": thumbnail_url})
        return characters
