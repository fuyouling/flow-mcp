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
        mode: str = "frame",
        aspect_ratio: str = "16:9",
        model_name: str = "Omni 1.1 Flash",
        resolution: str = "720p",
        duration: int = 8,
        quantity: str = "x1",
    ) -> None:
        """Apply video configuration in Google Flow settings panel."""
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

        # 2. Switch to '视频' tab
        vid_tab = self.find_button('xpath://span[text()="视频" and @class="toggle-text"]', name="'视频'Tab按钮", timeout=2)
        if vid_tab:
            self.click_btn(vid_tab, name="'视频'Tab按钮")
            logger.info("Switched to '视频' tab")
            time.sleep(0.5)

        # 3. Switch to '帧' or '素材' sub-tab
        is_frame_mode = mode.lower() in ["frame", "frames", "帧"]
        target_subtab = "帧" if is_frame_mode else "素材"
        subtab_btn = self.find_button(f"tag:span@@text():{target_subtab}", name=f"'{target_subtab}'子Tab按钮", timeout=2)
        if subtab_btn:
            self.click_btn(subtab_btn, name=f"'{target_subtab}'子Tab按钮")
            logger.info(f"Switched to '{target_subtab}' sub-tab")
            time.sleep(0.5)

        # 4. Aspect Ratio (16:9 / 9:16)
        ratio_btn = self.find_button(f"tag:button@@text():{aspect_ratio}", name=f"画幅比例'{aspect_ratio}'按钮", timeout=1)
        if ratio_btn:
            self.click_btn(ratio_btn, name=f"画幅比例'{aspect_ratio}'按钮")
            time.sleep(0.5)

        # 5. Model Dropdown
        m_lower = model_name.lower().strip()
        if "omni" in m_lower:
            target_model = "Omni 1.1 Flash"
        elif "lite" in m_lower or m_lower == "veo":
            target_model = "Veo 3.1 - Lite"
        elif "fast" in m_lower:
            target_model = "Veo 3.1 - Fast"
        elif "quality" in m_lower:
            target_model = "Veo 3.1 - Quality"
        else:
            target_model = model_name

        dropdown = self.find_button(
            ["@@aria-label=选择模型系列", "tag:button@@text():arrow_drop_down"],
            name="模型选择下拉按钮",
            timeout=2,
        )
        if dropdown:
            self.click_btn(dropdown, name="模型选择下拉按钮")
            time.sleep(0.5)
            model_options = self.find_buttons(f"tag:button@@text():{target_model}", name=f"模型'{target_model}'选项列表", timeout=1)
            for opt in model_options:
                if "arrow_drop_down" not in (opt.text or ""):
                    self.click_btn(opt, name=f"模型选项'{target_model}'")
                    time.sleep(0.5)
                    break

        # 6. Resolution & Duration (Omni models only)
        if "omni" in target_model.lower():
            res_btn = self.find_button(f"tag:button@@text():{resolution}", name=f"分辨率'{resolution}'按钮", timeout=1)
            if res_btn:
                self.click_btn(res_btn, name=f"分辨率'{resolution}'按钮")
                time.sleep(0.5)

            dur_clean = str(duration).replace("秒", "").replace("s", "").strip()
            dur_target = f"{dur_clean} 秒"
            dur_btn = self.find_button(f"tag:button@@text():{dur_target}", name=f"时长'{dur_target}'按钮", timeout=1)
            if dur_btn:
                self.click_btn(dur_btn, name=f"时长'{dur_target}'按钮")
                time.sleep(0.5)
        else:
            logger.info(f"Model {target_model} does not support resolution/duration selection; skipped.")

        # 7. Quantity (x1 ~ x4)
        qty_btn = self.find_button(f"tag:button@@text()={quantity}", name=f"生成数量'{quantity}'按钮", timeout=1)
        if qty_btn:
            self.click_btn(qty_btn, name=f"生成数量'{quantity}'按钮")
            time.sleep(0.5)

        # 8. Close settings panel by pressing ESC
        self.tab.run_cdp("Input.dispatchKeyEvent", type="rawKeyDown", windowsVirtualKeyCode=27)
        self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=27)
        time.sleep(0.8)
        if self.tab.ele(".cdk-overlay-backdrop", timeout=0.5):
            self.tab.run_cdp("Input.dispatchKeyEvent", type="rawKeyDown", windowsVirtualKeyCode=27)
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyUp", windowsVirtualKeyCode=27)
            time.sleep(0.5)

    def bind_frame_image(self, chip_label: str, image_name: str) -> None:
        """Bind start or end frame image in frame mode."""
        logger.info(f"Binding frame [{chip_label}] with image {image_name!r}")
        chip = self.find_button(f"tag:button@@text():{chip_label}", name=f"[{chip_label}]帧选择按钮", timeout=2, silent_fail=True)
        if not chip:
            chips = self.tab.eles(".empty-chip")
            if chip_label == "开始" and chips:
                chip = chips[0]
            elif chip_label == "结束" and len(chips) > 1:
                chip = chips[1]

        if not chip:
            raise RuntimeError(f"未找到 [{chip_label}] 帧选择按钮")

        self.click_btn(chip, name=f"[{chip_label}]帧选择按钮")
        time.sleep(1)

        search_input = self.find_input(
            ["tag:input@@placeholder:搜索资源", "tag:input@@placeholder:搜索"],
            name="画面图像搜索输入框",
            timeout=2,
        )
        if not search_input:
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=27)
            raise RuntimeError("未找到画面图像搜索输入框")

        self.input_text(search_input, image_name, name="画面图像搜索输入框", clear=True)
        logger.info(f"Searching for frame image: {image_name!r}")
        time.sleep(1.5)

        add_btn = self.find_button("tag:button@@text():添加到提示", name="'添加到提示'按钮", timeout=2)
        if add_btn:
            self.click_btn(add_btn, name="'添加到提示'按钮")
            time.sleep(1)
        else:
            self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=27)
            time.sleep(0.5)
            raise RuntimeError(f"未找到添加按钮或图片: {image_name!r}")

    def add_assets_to_prompt(self, assets: list[str]) -> None:
        """Add a reference material to prompt in asset mode."""
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
                logger.info(f"Searching for asset: {asset!r}")
                time.sleep(1.5)

                add_to_prompt_btn = self.find_button("tag:button@@text():添加到提示", name="'添加到提示'按钮", timeout=2)
                if add_to_prompt_btn:
                    self.click_btn(add_to_prompt_btn, name="'添加到提示'按钮")
                    time.sleep(1)
                else:
                    logger.warning(f"Asset result or add button not found for: {asset!r}")
                    self.tab.run_cdp("Input.dispatchKeyEvent", type="keyDown", windowsVirtualKeyCode=27)
                    time.sleep(0.5)
            else:
                logger.warning(f"Search input not found for asset: {asset!r}")

    def enter_prompt(self, prompt: str) -> None:
        """Type prompt into rich text editor."""
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
            name="视频提示词编辑器",
            timeout=3,
        )

        if editor:
            self.click_btn(editor, name="视频提示词编辑器")
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
                    logger.info(f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 输入视频提示词成功 (CDP方式, 预览: '{preview}')")
                else:
                    logger.warning("CDP Input.insertText executed but text not verified, trying JS clipboard fallback")
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
                    self.click_btn(editor, name="视频提示词编辑器(粘贴重试)")
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
                        logger.info(f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 输入视频提示词成功 (剪贴板方式, 预览: '{preview}')")
                except Exception as e:
                    logger.warning(f"Clipboard paste fallback failed: {e!r}")

        if not prompt_entered:
            logger.warning("Could not verify video prompt entered into editor.")

    def generate_video(
        self,
        project_url: str,
        prompt: str,
        model_name: str = "Omni 1.1 Flash",
        mode: str = "asset",
        start_frame: str = "",
        end_frame: str = "",
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        duration: int = 8,
        quantity: str = "x1",
        assets: list[str] | None = None,
        rename_name: str = "",
        download: str = "720p",
        progress_callback: Optional[Callable[[int, str], None]] = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Execute full video creation flow."""
        logger.info(f"Generating video in {project_url} with model {model_name}, mode={mode}...")
        # Always refresh the page to ensure a clean state (empty prompt, no old assets) for the new task
        self.tab.get(project_url)
        time.sleep(3)

        self.check_and_handle_refresh_prompt()

        self.apply_settings(
            mode=mode,
            aspect_ratio=aspect_ratio,
            model_name=model_name,
            resolution=resolution,
            duration=duration,
            quantity=quantity,
        )

        is_frame_mode = mode.lower() in ["frame", "frames", "帧"]
        if is_frame_mode:
            if start_frame:
                self.bind_frame_image("开始", start_frame)
            if end_frame:
                self.bind_frame_image("结束", end_frame)
        elif assets:
            self.add_assets_to_prompt(assets)

        self.enter_prompt(prompt)
        time.sleep(0.5)

        tiles_before = len(self.tab.eles("xpath://flow-grid-tile-container", timeout=0.1))

        submit_btn = self.find_button('xpath://button[@type="submit"]', name="视频生成提交按钮", timeout=5)
        if not submit_btn or submit_btn.attr("disabled"):
            raise RuntimeError("Video submit button not clickable.")

        self.click_btn(submit_btn, name="视频生成提交按钮")
        logger.info(f"Clicked generate video button (tiles before: {tiles_before}), polling progress...")

        start_time = time.time()
        loading_xpath = 'xpath://div[@class="loading-percentage"]'

        # Wait for loading to start or new tile to appear
        generation_started = False
        for _ in range(60):
            if self.tab.ele(loading_xpath, timeout=0.5):
                generation_started = True
                break
            if len(self.tab.eles("xpath://flow-grid-tile-container", timeout=0.1)) > tiles_before:
                generation_started = True
                break
            time.sleep(0.5)
            
        if not generation_started:
            raise RuntimeError("Video generation did not start within 30 seconds (no new tile or loading indicator found).")

        # Poll percentage until completed
        while time.time() - start_time < timeout:
            loading_ele = self.tab.ele(loading_xpath, timeout=0.5)
            if not loading_ele:
                # Generation finished — check for error overlay before proceeding
                error_title_ele = self.tab.ele('xpath://div[@class="error-title"]', timeout=0.5)
                if error_title_ele:
                    error_msg_ele = self.tab.ele('xpath://span[@class="error-message-text"]', timeout=0.5)
                    error_msg = error_msg_ele.text.strip() if error_msg_ele and error_msg_ele.text else "Unknown generation error"
                    logger.error(f"Video generation error detected: {error_msg}")
                    if progress_callback:
                        try:
                            progress_callback(-1, f"[ERROR] {error_msg}")
                        except Exception as ex:
                            logger.debug(f"Progress callback exception: {ex}")
                    raise RuntimeError(f"Video generation failed: {error_msg}")
                break
            text = loading_ele.text or ""
            m = re.search(r"(\d{1,3})", text)
            pct = int(m.group(1)) if m else 0
            if progress_callback:
                try:
                    progress_callback(pct, text or f"{pct}%")
                except Exception as ex:
                    logger.debug(f"Progress callback exception: {ex}")
            time.sleep(3)

        time.sleep(1)

        # Click newest tile to open details
        tile = self.find_element("xpath://flow-grid-tile-container[1]", name="新生成视频卡片", timeout=10)
        if not tile:
            raise RuntimeError("Generated video tile not found.")

        self.click_btn(tile, name="新生成视频卡片")
        time.sleep(1.5)

        if self.tab.ele('xpath://span[text()="所有媒体"]', timeout=1):
            logger.warning("Still on project page after clicking tile, trying again...")
            self.click_btn(tile, name="新生成视频卡片(重试)", by_js=True)
            time.sleep(1.5)
            if self.tab.ele('xpath://span[text()="所有媒体"]', timeout=1):
                raise RuntimeError("Failed to enter details page after multiple click attempts.")

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

        vid_btn = self.find_button(
            [
                'xpath://mat-list-item//span[text()="视频"]',
                'xpath://mat-list-item[.//span[contains(text(), "视频") or text()="Videos"]]',
            ],
            name="侧边栏'视频'按钮",
            timeout=3,
        )
        if vid_btn:
            self.click_btn(vid_btn, name="侧边栏'视频'按钮")
            time.sleep(2)

        tiles = self.tab.eles("xpath://flow-video-tile")
        if not tiles:
            tiles = self.tab.eles('xpath://*[contains(@class, "flow-video-tile")]')

        videos = []
        for idx, tile in enumerate(tiles):
            try:
                name_ele = tile.ele("xpath:.//flow-tile-hover-footer/div/span", timeout=0) or tile.ele("xpath:.//span", timeout=0)
                name = name_ele.text.strip() if name_ele else ""
                img_ele = tile.ele("tag:img", timeout=0) or tile.ele("tag:video", timeout=0)
                thumbnail_url = img_ele.attr("src") if img_ele else ""
                videos.append({"index": idx + 1, "name": name, "thumbnail_url": thumbnail_url})
            except Exception:
                continue
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

        add_btn = self.find_button(
            [
                'xpath://button[@mattooltip="添加媒体"]',
                'xpath://button[contains(@mattooltip, "添加媒体") or contains(@aria-label, "添加媒体")]',
            ],
            name="'添加媒体'按钮",
            timeout=5,
        )
        if not add_btn:
            raise RuntimeError("Add media button not found.")

        self.click_btn(add_btn, name="'添加媒体'按钮")
        time.sleep(0.8)

        self.tab.set.upload_files(abs_path)

        upload_btn = self.find_button(
            ['xpath://span[text()="上传"]', 'xpath://button[contains(., "上传")]'],
            name="'上传'按钮",
            timeout=5,
        )
        if not upload_btn:
            raise RuntimeError("Upload button not found.")

        self.click_btn(upload_btn, name="'上传'按钮")

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
                    uploaded_tile = self.find_element("xpath:(//flow-grid-tile-container)[1]", name="已上传视频卡片", timeout=1)
                    break
            time.sleep(1)

        if not uploaded_tile:
            raise TimeoutError(f"Timeout waiting for uploaded video tile '{file_stem}' to appear.")

        if target_name:
            try:
                self.click_btn(uploaded_tile, name="已上传视频卡片")
                time.sleep(1)
                edit_page = VideoEditPage(self.tab)
                edit_page.rename(target_name)
                edit_page.save_and_close()
            except Exception as e:
                logger.warning(f"Error renaming uploaded video to {target_name}: {e}")

        return True
