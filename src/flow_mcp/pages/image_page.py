"""Page Object Model for Image operations in Google Flow."""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from flow_mcp.pages.base_page import BasePage
from flow_mcp.pages.image_edit_page import ImageEditPage


class ImagePage(BasePage):
    """
    Page Object Model for image generation, listing, and uploading in Google Flow.
    """

    def apply_settings(
        self,
        aspect_ratio: str = "16:9",
        model_name: str = "Nano Banana Pro",
        quantity: str = "x1",
    ) -> None:
        """Configure generation settings panel."""
        time.sleep(2)

        # 1. Open settings panel
        settings_btn = self.find_button(
            ["tag:button@@aria-label=设置触发器", "tag:button@@text():🍌"],
            name="'设置触发器'按钮",
            timeout=2,
        )

        if settings_btn:
            self.click_btn(settings_btn, name="'设置触发器'按钮")
            time.sleep(1)

        # 2. Switch to image tab
        img_tab = self.find_button(
            ['xpath://span[text()="图片" and @class="toggle-text"]', "tag:button@@text()=图片"],
            name="'图片'Tab切换按钮",
            timeout=2,
            silent_fail=True,
        )
        if not img_tab:
            s_btn = self.find_button("tag:button@@text():🍌", name="'🍌'备用设置按钮", timeout=1, silent_fail=True)
            if s_btn:
                self.click_btn(s_btn, name="'🍌'备用设置按钮")
                time.sleep(1)
                img_tab = self.find_button("tag:button@@text()=图片", name="'图片'Tab切换按钮", timeout=2)

        if img_tab:
            self.click_btn(img_tab, name="'图片'Tab切换按钮")
            time.sleep(0.5)

        # 3. Aspect ratio
        ratio_btn = self.find_button(f"tag:button@@text():{aspect_ratio}", name=f"画幅比例'{aspect_ratio}'按钮", timeout=1)
        if ratio_btn:
            self.click_btn(ratio_btn, name=f"画幅比例'{aspect_ratio}'按钮")
            time.sleep(0.5)

        # 4. Model dropdown
        dropdown = self.find_button("tag:button@@text():arrow_drop_down", name="模型选择下拉按钮", timeout=1)
        if dropdown:
            self.click_btn(dropdown, name="模型选择下拉按钮")
            time.sleep(0.5)
            pro_options = self.find_buttons(f"tag:button@@text():{model_name}", name=f"模型'{model_name}'选项列表", timeout=1)
            for opt in pro_options:
                if "arrow_drop_down" not in (opt.text or ""):
                    self.click_btn(opt, name=f"模型选项'{model_name}'")
                    time.sleep(0.5)
                    break

        # 5. Quantity
        qty_btn = self.find_button(f"tag:button@@text()={quantity}", name=f"生成数量'{quantity}'按钮", timeout=1)
        if qty_btn:
            self.click_btn(qty_btn, name=f"生成数量'{quantity}'按钮")
            time.sleep(0.5)

        # 6. Close settings panel via ESC
        self.tab.run_cdp("Input.dispatchKeyEvent", type="rawKeyDown", windowsVirtualKeyCode=27)
        self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=27)
        time.sleep(0.8)
        if self.tab.ele(".cdk-overlay-backdrop", timeout=0.5):
            self.tab.run_cdp("Input.dispatchKeyEvent", type="rawKeyDown", windowsVirtualKeyCode=27)
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=27)
            time.sleep(0.5)

    def add_assets_to_prompt(self, assets: list[str]) -> None:
        """Search and link existing project assets to the generation prompt."""
        for asset in assets:
            if not asset.strip():
                continue
            add_btn = self.find_button(
                ['xpath://button[@aria-label="在提示框中添加素材"]', "@@aria-label=在提示框中添加素材"],
                name="'在提示框中添加素材'按钮",
                timeout=2,
            )
            if add_btn:
                self.click_btn(add_btn, name="'在提示框中添加素材'按钮")
                time.sleep(1)
            else:
                logger.warning(f"'添加素材' button not found, skipping asset: {asset}")
                continue

            search_input = self.find_input(
                'xpath://input[@class="search-input" and @placeholder="搜索资源"]',
                name="素材搜索输入框",
                timeout=2,
            )
            if search_input:
                self.input_text(search_input, asset.strip(), name="素材搜索输入框", clear=True)
                logger.info(f"Searching for asset: {asset.strip()!r}")
                time.sleep(1.5)
                add_prompt_btn = self.find_button("tag:button@@text():添加到提示", name="'添加到提示'按钮", timeout=2)
                if add_prompt_btn:
                    self.click_btn(add_prompt_btn, name="'添加到提示'按钮")
                    time.sleep(1)
                else:
                    logger.warning(f"Asset result or add button not found for: {asset.strip()!r}")
                    self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=27)
                    time.sleep(0.5)
            else:
                logger.warning(f"Search input not found for asset: {asset.strip()!r}")

    def enter_prompt(self, prompt: str) -> None:
        """Safely type prompt text into ProseMirror rich text editor."""
        prompt_entered = False
        if self.tab.ele(".cdk-overlay-backdrop", timeout=0.5):
            self.tab.run_cdp("Input.dispatchKeyEvent", type="rawKeyDown", windowsVirtualKeyCode=27)
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=27)
            time.sleep(0.5)

        editor = self.find_element(
            [
                'xpath://flow-rich-text-editor[@class="prompt-input"]//div[@contenteditable="true"]',
                'xpath://flow-rich-text-editor[@class="prompt-input"]',
            ],
            name="图片提示词编辑器",
            timeout=3,
        )

        if editor:
            self.click_btn(editor, name="图片提示词编辑器")
            time.sleep(0.3)

            start_time = time.time()
            preview = (prompt[:30] + "...") if len(prompt) > 30 else prompt

            # Strategy 1: CDP Input.insertText
            try:
                self.tab.run_cdp("Input.insertText", text=prompt)
                time.sleep(0.5)
                pm_text = self.tab.run_js(
                    "return (document.querySelector('flow-rich-text-editor.prompt-input div[contenteditable=\"true\"]') || {}).innerText || '';"
                )
                if prompt.strip() in (pm_text or "").strip():
                    prompt_entered = True
                    elapsed = time.time() - start_time
                    logger.info(f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 输入图片提示词成功 (CDP方式, 预览: '{preview}')")
                else:
                    logger.warning(f"CDP Input.insertText executed but text not verified (got {pm_text!r}), trying JS clipboard fallback")
            except Exception as e:
                logger.warning(f"CDP Input.insertText failed: {e!r}, trying JS clipboard fallback")

            # Strategy 2: JS set clipboard + CDP Ctrl+V (fallback)
            if not prompt_entered:
                try:
                    self.tab.run_js("""
                        (function(text) {
                            navigator.clipboard.writeText(text).catch(function() {
                                var ta = document.createElement('textarea');
                                ta.value = text;
                                ta.style.position = 'fixed';
                                ta.style.opacity = '0';
                                document.body.appendChild(ta);
                                ta.focus();
                                ta.select();
                                document.execCommand('copy');
                                document.body.removeChild(ta);
                            });
                        })(arguments[0]);
                    """, prompt)
                    time.sleep(0.3)
                    self.click_btn(editor, name="图片提示词编辑器(粘贴重试)")
                    time.sleep(0.2)
                    self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=86, modifiers=2)
                    self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=86, modifiers=2)
                    time.sleep(0.5)
                    pm_text = self.tab.run_js(
                        "return (document.querySelector('flow-rich-text-editor.prompt-input div[contenteditable=\"true\"]') || {}).innerText || '';"
                    )
                    if prompt.strip() in (pm_text or "").strip():
                        prompt_entered = True
                        elapsed = time.time() - start_time
                        logger.info(f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 输入图片提示词成功 (剪贴板方式, 预览: '{preview}')")
                except Exception as e:
                    logger.warning(f"Clipboard paste fallback failed: {e!r}")

        if not prompt_entered:
            logger.warning("Could not verify prompt text entered into editor.")

    def generate_image(
        self,
        project_url: str,
        prompt: str,
        aspect_ratio: str = "16:9",
        model_name: str = "Nano Banana Pro",
        quantity: str = "x1",
        assets: list[str] | None = None,
        rename_name: str = "",
        download: str = "2K",
        progress_callback: Optional[Callable[[int, str], None]] = None,
        timeout: int = 180,
    ) -> dict[str, Any]:
        """
        Execute full image creation flow in the specified project.
        """
        logger.info(f"Generating image in {project_url} with prompt: {prompt[:40]}...")
        
        # Always force refresh to ensure clean state and clear any lingering dialogs
        self.tab.get(project_url)
        time.sleep(3)

        self.check_and_handle_refresh_prompt()

        self.apply_settings(aspect_ratio, model_name, quantity)

        if assets:
            self.add_assets_to_prompt(assets)

        self.enter_prompt(prompt)
        time.sleep(0.5)

        # Click submit button
        submit_btn = self.find_button('xpath://button[@type="submit"]', name="生成图片提交按钮", timeout=5)
        if not submit_btn or submit_btn.attr("disabled"):
            raise RuntimeError("Generate submit button not clickable.")

        self.click_btn(submit_btn, name="生成图片提交按钮")
        logger.info("Clicked generate button, waiting for generation to complete...")

        # Poll progress
        start_time = time.time()
        loading_xpath = 'xpath://div[@class="loading-percentage"]'

        # Wait for loading to start
        loading_started = False
        for _ in range(60):
            if self.tab.ele(loading_xpath, timeout=0.5):
                loading_started = True
                break
            time.sleep(0.5)
            
        if not loading_started:
            raise RuntimeError("Image generation failed to start (loading indicator not found within 30s).")

        # Poll percentage until completed
        while time.time() - start_time < timeout:
            loading_ele = self.tab.ele(loading_xpath, timeout=0.5)
            if not loading_ele:
                # Generation finished
                break
            text = loading_ele.text or ""
            m = re.search(r"(\d{1,3})", text)
            pct = int(m.group(1)) if m else 0
            if progress_callback:
                try:
                    progress_callback(pct, text or f"{pct}%")
                except Exception as ex:
                    logger.debug(f"Progress callback exception: {ex}")
            time.sleep(2)

        time.sleep(1)

        # Click newest tile to open details
        tile = self.find_element("xpath://flow-grid-tile-container[1]", name="新生成图片卡片", timeout=10)
        if not tile:
            raise RuntimeError("Generated image tile (//flow-grid-tile-container[1]) not found.")

        self.click_btn(tile, name="新生成图片卡片")
        time.sleep(1.5)

        if self.tab.ele('xpath://span[text()="所有媒体"]', timeout=1):
            logger.warning("Still on project page after clicking tile, trying again...")
            self.click_btn(tile, name="新生成图片卡片(重试)", by_js=True)
            time.sleep(1.5)
            if self.tab.ele('xpath://span[text()="所有媒体"]', timeout=1):
                raise RuntimeError("Failed to enter details page after multiple click attempts.")

        edit_page = ImageEditPage(self.tab)
        final_name = rename_name or f"image_{int(time.time())}"
        edit_page.rename(final_name)
        img_url = edit_page.get_media_url()
        b64 = edit_page.get_base64()

        local_path = ""
        if download in ("1K", "2K"):
            local_path = edit_page.download_image(resolution=download, expected_prefix=final_name) or ""

        edit_page.save_and_close()

        return {
            "image_name": final_name,
            "image_url": img_url,
            "image_base64": b64,
            "local_path": local_path,
        }

    def list_images(self, project_url: str = "") -> list[dict[str, Any]]:
        """List all images in the project."""
        if project_url:
            self.tab.get(project_url)
            time.sleep(3)

        img_btn = self.find_button(
            [
                'xpath://mat-list-item//span[text()="图片"]',
                'xpath://mat-list-item[.//span[contains(text(), "图片") or text()="Images"]]',
            ],
            name="侧边栏'图片'按钮",
            timeout=3,
        )
        if img_btn:
            self.click_btn(img_btn, name="侧边栏'图片'按钮")
            time.sleep(2)

        tiles = self.tab.eles("xpath://flow-image-tile")
        if not tiles:
            tiles = self.tab.eles('xpath://*[contains(@class, "flow-image-tile")]')

        images = []
        for idx, tile in enumerate(tiles):
            name_ele = tile.ele("xpath:.//flow-tile-hover-footer/div/span", timeout=0) or tile.ele("xpath:.//span", timeout=0)
            name = name_ele.text.strip() if name_ele else ""
            img_ele = tile.ele("css:img", timeout=0)
            thumbnail_url = img_ele.attr("src") if img_ele else ""
            images.append({"index": idx + 1, "name": name, "thumbnail_url": thumbnail_url})
        return images

    def upload_image_on_project_page(
        self, project_url: str, image_path: str, target_name: str = "", timeout: int = 60
    ) -> bool:
        """Upload a local image into the project media library."""
        path_obj = Path(image_path)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        abs_path = str(path_obj.resolve())
        file_stem = path_obj.stem

        if project_url:
            self.tab.get(project_url)
            time.sleep(3)

        # Click add media button
        add_btn = self.find_button(
            [
                'xpath://button[@mattooltip="添加媒体"]',
                'xpath://button[contains(@mattooltip, "添加媒体") or contains(@aria-label, "添加媒体")]',
            ],
            name="'添加媒体'按钮",
            timeout=5,
        )
        if not add_btn:
            raise RuntimeError("Add media button not found on project page.")

        self.click_btn(add_btn, name="'添加媒体'按钮")
        time.sleep(0.8)

        # Set upload files via CDP
        self.tab.set.upload_files(abs_path)

        upload_btn = self.find_button(
            ['xpath://span[text()="上传"]', 'xpath://button[contains(., "上传")]'],
            name="'上传'按钮",
            timeout=5,
        )
        if not upload_btn:
            raise RuntimeError("Upload button not found.")

        self.click_btn(upload_btn, name="'上传'按钮")

        # Wait for completion & handle agreement dialog
        start_time = time.time()
        uploaded_tile = None
        while time.time() - start_time < timeout:
            agree_btn = self.find_button(
                ['xpath://span[text()="我同意，不再显示"]', 'xpath://button[contains(., "我同意") or .//span[contains(text(), "我同意")]]'],
                name="'我同意，不再显示'按钮",
                timeout=0,
                silent_fail=True,
            )
            if agree_btn:
                self.click_btn(agree_btn, name="'我同意，不再显示'按钮", by_js=True)
                time.sleep(1)

            first_span = self.tab.ele("xpath:(//flow-grid-tile-container)[1]//span", timeout=0.5)
            if first_span:
                span_text = first_span.text.strip()
                if file_stem.lower() in span_text.lower():
                    uploaded_tile = self.find_element("xpath:(//flow-grid-tile-container)[1]", name="已上传图片卡片", timeout=1)
                    break
            time.sleep(1)

        if not uploaded_tile:
            raise TimeoutError(f"Timeout waiting for uploaded image tile '{file_stem}' to appear.")

        if target_name:
            try:
                self.click_btn(uploaded_tile, name="已上传图片卡片")
                time.sleep(1)
                edit_page = ImageEditPage(self.tab)
                edit_page.rename(target_name)
                edit_page.save_and_close()
            except Exception as e:
                logger.warning(f"Error renaming uploaded image to {target_name}: {e}")

        return True
