"""Page Object Model for Google Flow Home Page."""
from __future__ import annotations

import re
import time
from typing import Any, Optional

from loguru import logger

from flow_mcp.pages.base_page import BasePage


class HomePage(BasePage):
    """
    Page Object Model for the Google Flow home page (https://flow.google.com).
    """
    URL = "https://flow.google.com"

    def dismiss_modals(self) -> None:
        """Dismiss common promotional modals or cookie banners."""
        try:
            btn = self.tab.ele(
                'xpath://button[contains(., "开始使用") or contains(., "Get started") or contains(., "Got it") or contains(., "Close") or contains(., "关闭")]',
                timeout=2,
            )
            if btn and btn.is_displayed:
                logger.info("Dismissing promotional banner/modal...")
                btn.click()
                time.sleep(0.5)
        except Exception as e:
            logger.debug(f"Modal dismissal check: {e}")

    def open(self) -> None:
        """Open Flow home page and wait for project cards or new button."""
        logger.info(f"Opening Flow Home Page: {self.URL}")
        self.tab.get(self.URL)
        self.tab.ele("css:flow-project-card, button.new-project-button", timeout=15)
        self.dismiss_modals()
        logger.info("Flow Home Page loaded successfully.")

    def get_projects(self) -> dict[str, dict[str, Any]]:
        """
        Extract project cards into a dict keyed by project title.
        Returns: {title: {"name": title, "url": href, "local_uuid": local_uuid}}
        """
        logger.info("Extracting projects from home page...")
        cards = self.tab.eles("css:flow-project-card")
        result: dict[str, dict[str, Any]] = {}
        for card in cards:
            link_ele = card.ele("css:a.project-thumbnail-container")
            title_div = card.ele("css:div.project-title-label")
            if not link_ele or not title_div:
                continue

            href = link_ele.attr("href") or ""
            local_uuid = href.split("/")[-1] if href else ""

            full_text = title_div.text
            btn_ele = title_div.ele("css:button", timeout=0)
            btn_text = btn_ele.text if btn_ele else ""

            title = full_text.replace(btn_text, "").strip() if btn_text else full_text.strip()
            if not title:
                title = full_text.strip()

            if local_uuid and title:
                if title in result:
                    raise ValueError(f"检测到同名项目冲突: 存在多个名为 '{title}' 的项目。请进入 Google Flow 网页端手动将它们重命名以区分。")
                result[title] = {"name": title, "url": href, "local_uuid": local_uuid}

        logger.info(f"Discovered {len(result)} projects on home page.")
        return result

    def create_project(self) -> str:
        """Click 'New project' button, wait for navigation, return new project UUID."""
        logger.info("Creating new project via home page button...")
        new_btn = self.tab.ele("css:button.new-project-button") or self.tab.ele(
            'xpath://button[contains(., "新建项目") or contains(., "New project")]', timeout=3
        )
        if not new_btn:
            raise RuntimeError("Could not locate 'New Project' button on Flow home page.")

        old_url = self.tab.url or ""
        new_btn.click()

        start_time = time.time()
        timeout = 20
        match = None
        current_url = self.tab.url or ""
        while time.time() - start_time < timeout:
            current_url = self.tab.url or ""
            if current_url != old_url:
                match = re.search(r"/project/([a-zA-Z0-9\-]+)", current_url)
                if match:
                    break
            time.sleep(0.5)

        if match:
            new_uuid = match.group(1)
            logger.info(f"New project created: {new_uuid}")
            return new_uuid
        raise TimeoutError(f"Failed to extract project UUID from URL after {timeout}s: {current_url}")

    def rename_project(
        self, new_title: str, old_title: str | None = None, project_uuid: str | None = None
    ) -> bool:
        """Rename project by UUID or current title."""
        logger.info(f"Renaming project to '{new_title}' (uuid={project_uuid}, old_title={old_title})...")
        cards = self.tab.eles("css:flow-project-card")
        target_card = None
        for card in cards:
            if project_uuid:
                link_ele = card.ele("css:a.project-thumbnail-container")
                if link_ele and link_ele.attr("href") and project_uuid in (link_ele.attr("href") or ""):
                    target_card = card
                    break
            elif old_title:
                title_div = card.ele("css:div.project-title-label")
                if title_div and old_title in title_div.text:
                    target_card = card
                    break

        if not target_card:
            logger.error(f"Target project card not found (uuid={project_uuid}, old_title={old_title})")
            return False

        title_div = target_card.ele("css:div.project-title-label")
        edit_btn = title_div.ele("css:button") if title_div else None
        if not edit_btn:
            logger.error("Rename edit button not found in card.")
            return False

        edit_btn.click()
        input_ele = self.tab.ele("css:input.title-input", timeout=5)
        if not input_ele:
            logger.error("Rename input box did not appear.")
            return False

        input_ele.run_js("this.value = ''; this.dispatchEvent(new Event('input', {bubbles: true}));")
        input_ele.input(new_title + "\n")
        is_deleted = self.tab.wait.ele_deleted(input_ele, timeout=5)
        if is_deleted:
            logger.info(f"Project renamed successfully to '{new_title}'")
            return True
        return False

    def get_credits(self) -> Optional[int]:
        """Fetch available credits count from user account panel."""
        panel_opened = False
        try:
            account_btn = self.tab.ele(
                'xpath://div[@aria-label="账号详情" or @aria-label="Account details"]', timeout=5
            )
            if not account_btn:
                logger.warning("Account details button not found.")
                return None
            account_btn.click()
            panel_opened = True
            time.sleep(0.8)

            credits_ele = self.tab.ele('xpath://span[contains(@class, "credits-count")]', timeout=5)
            if not credits_ele:
                logger.warning("Credits count element not found.")
                return None

            text = credits_ele.text or ""
            match = re.search(r"([\d,]+)", text)
            credits = int(match.group(1).replace(",", "")) if match else None
            if credits is not None:
                logger.info(f"Flow account credits: {credits}")
            return credits
        except Exception as e:
            logger.warning(f"Error fetching credits: {e}")
            return None
        finally:
            if panel_opened:
                try:
                    close_btn = self.tab.ele(
                        'xpath://button[@aria-label="关闭账号面板" or @aria-label="Close account panel"]',
                        timeout=3,
                    )
                    if close_btn:
                        close_btn.click()
                except Exception:
                    pass

    def get_account_email(self) -> Optional[str]:
        """Fetch current logged-in Google account email from UI."""
        panel_opened = False
        try:
            account_btn = self.tab.ele(
                'xpath://div[@aria-label="账号详情" or @aria-label="Account details"]', timeout=5
            )
            if not account_btn:
                return None
            account_btn.click()
            panel_opened = True
            time.sleep(0.8)

            email_ele = self.tab.ele('xpath://div[contains(@class, "account-email") or contains(text(), "@")]', timeout=3)
            if email_ele:
                match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", email_ele.text or "")
                if match:
                    return match.group(0)
            return None
        except Exception:
            return None
        finally:
            if panel_opened:
                try:
                    close_btn = self.tab.ele(
                        'xpath://button[@aria-label="关闭账号面板" or @aria-label="Close account panel"]',
                        timeout=3,
                    )
                    if close_btn:
                        close_btn.click()
                except Exception:
                    pass
