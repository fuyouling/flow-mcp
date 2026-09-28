"""Base Page Object encapsulating common browser actions."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Sequence, Union

from DrissionPage import ChromiumPage
from DrissionPage.items import ChromiumTab, MixTab
from loguru import logger

from flow_mcp.utils.errors import ElementNotFoundError, PageTimeoutError


class BasePage:
    """Base page object encapsulating common browser actions and robust element handling."""

    def __init__(self, tab: Union[ChromiumTab, MixTab, ChromiumPage]):
        self.tab: Any = tab

    @staticmethod
    def _op_time() -> str:
        """Get formatted current operation time."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def navigate(self, url: str) -> None:
        """Navigate to a specified URL."""
        logger.info(f"Navigating to URL: {url}")
        try:
            if hasattr(self.tab, "set") and hasattr(self.tab.set, "load_mode"):
                self.tab.set.load_mode.eager()
        except Exception as e:
            logger.debug(f"Could not set eager load mode: {e}")

        try:
            success = self.tab.get(url, show_errmsg=True, retry=2)
            if success is False:
                logger.error(f"DrissionPage tab.get returned False for {url}")
                raise PageTimeoutError(f"Navigation to {url} failed or timed out")
        except Exception as e:
            logger.error(f"Failed navigating to {url}: {e}")
            raise PageTimeoutError(f"Navigation to {url} failed: {e}") from e

    def check_and_handle_refresh_prompt(self) -> None:
        """Check for '刷新并重试' prompt and refresh the page if present."""
        try:
            prompt = self.tab.ele('xpath://div[contains(text(),"刷新并重试")]', timeout=1)
            if prompt:
                logger.warning("Detected '刷新并重试' prompt. Refreshing the page...")
                self.tab.refresh()
                time.sleep(2)
        except Exception as e:
            logger.debug(f"Refresh prompt check failed: {e}")

    def find_button(
        self,
        selector: Union[str, Sequence[str]],
        name: str = "按钮",
        timeout: float = 2.0,
        scope: Any = None,
        silent_fail: bool = False,
    ) -> Any:
        """
        Find button element with timing and logging for both success and failure.
        Supports single selector string or sequence of fallback selectors.
        """
        target = scope if scope is not None else self.tab
        selectors = [selector] if isinstance(selector, str) else list(selector)
        start_time = time.time()

        for sel in selectors:
            try:
                ele = target.ele(sel, timeout=timeout)
                if ele:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取按钮成功: '{name}' (匹配选择器: '{sel}')"
                    )
                    return ele
            except Exception as e:
                logger.debug(f"Error checking selector '{sel}' for button '{name}': {e}")

        elapsed = time.time() - start_time
        if not silent_fail:
            logger.warning(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取按钮失败: '{name}' (尝试选择器: {selectors})"
            )
        return None

    def find_buttons(
        self,
        selector: str,
        name: str = "按钮列表",
        timeout: float = 2.0,
        scope: Any = None,
    ) -> list[Any]:
        """
        Find multiple button elements with timing and logging.
        """
        target = scope if scope is not None else self.tab
        start_time = time.time()
        try:
            eles = target.eles(selector, timeout=timeout)
            elapsed = time.time() - start_time
            count = len(eles) if eles else 0
            if count > 0:
                logger.info(
                    f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取按钮列表成功: '{name}' (找到 {count} 个, 选择器: '{selector}')"
                )
                return eles
            else:
                logger.warning(
                    f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取按钮列表为空: '{name}' (选择器: '{selector}')"
                )
                return []
        except Exception as e:
            elapsed = time.time() - start_time
            logger.warning(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取按钮列表失败: '{name}' (选择器: '{selector}') - {e}"
            )
            return []

    def find_input(
        self,
        selector: Union[str, Sequence[str]],
        name: str = "输入框",
        timeout: float = 2.0,
        scope: Any = None,
        silent_fail: bool = False,
    ) -> Any:
        """
        Find input element with timing and logging for both success and failure.
        """
        target = scope if scope is not None else self.tab
        selectors = [selector] if isinstance(selector, str) else list(selector)
        start_time = time.time()

        for sel in selectors:
            try:
                ele = target.ele(sel, timeout=timeout)
                if ele:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取输入框成功: '{name}' (匹配选择器: '{sel}')"
                    )
                    return ele
            except Exception as e:
                logger.debug(f"Error checking selector '{sel}' for input '{name}': {e}")

        elapsed = time.time() - start_time
        if not silent_fail:
            logger.warning(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取输入框失败: '{name}' (尝试选择器: {selectors})"
            )
        return None

    def find_element(
        self,
        selector: Union[str, Sequence[str]],
        name: str = "元素",
        timeout: float = 2.0,
        scope: Any = None,
        silent_fail: bool = False,
    ) -> Any:
        """
        Find element with timing and logging for both success and failure.
        """
        target = scope if scope is not None else self.tab
        selectors = [selector] if isinstance(selector, str) else list(selector)
        start_time = time.time()

        for sel in selectors:
            try:
                ele = target.ele(sel, timeout=timeout)
                if ele:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取元素成功: '{name}' (匹配选择器: '{sel}')"
                    )
                    return ele
            except Exception as e:
                logger.debug(f"Error checking selector '{sel}' for element '{name}': {e}")

        elapsed = time.time() - start_time
        if not silent_fail:
            logger.warning(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 获取元素失败: '{name}' (尝试选择器: {selectors})"
            )
        return None

    def click_btn(
        self,
        target: Any,
        name: str = "按钮",
        timeout: float = 2.0,
        by_js: bool = False,
        scope: Any = None,
    ) -> bool:
        """
        Click button or element with timing and logging.
        """
        if isinstance(target, (str, list, tuple)):
            ele = self.find_button(target, name=name, timeout=timeout, scope=scope)
            if not ele:
                return False
        else:
            ele = target

        if not ele:
            logger.warning(f"[{self._op_time()}] 点击按钮失败: '{name}' (元素为空)")
            return False

        start_time = time.time()
        actual_by_js = by_js
        try:
            if by_js:
                ele.click(by_js=True)
            else:
                try:
                    ele.click()
                except Exception as click_err:
                    logger.debug(f"Direct click failed for '{name}' ({click_err}), trying by_js=True fallback...")
                    ele.click(by_js=True)
                    actual_by_js = True
            elapsed = time.time() - start_time
            logger.info(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 点击按钮成功: '{name}' (by_js={actual_by_js})"
            )
            return True
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 点击按钮失败: '{name}' (by_js={actual_by_js}) - 错误: {e}"
            )
            return False

    def input_text(
        self,
        target: Any,
        text: str,
        name: str = "输入框",
        timeout: float = 5.0,
        clear: bool = True,
        scope: Any = None,
    ) -> bool:
        """
        Input text into element with timing and logging.
        """
        if isinstance(target, (str, list, tuple)):
            ele = self.find_input(target, name=name, timeout=timeout, scope=scope)
            if not ele:
                return False
        else:
            ele = target

        if not ele:
            logger.warning(f"[{self._op_time()}] 输入文本失败: '{name}' (元素为空)")
            return False

        start_time = time.time()
        preview = (text[:30] + "...") if len(text) > 30 else text
        clean_preview = preview.replace("\n", "\\n")
        try:
            if clear and hasattr(ele, "clear"):
                ele.clear()
            ele.input(text)
            elapsed = time.time() - start_time
            logger.info(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 输入内容成功: '{name}' (内容: '{clean_preview}')"
            )
            return True
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[{self._op_time()} | 耗时: {elapsed:.2f}s] 输入内容失败: '{name}' - 错误: {e}"
            )
            return False

    def wait_for_element(self, selector: str, timeout: float = 10.0) -> Any:
        """Wait for an element to appear in DOM and be accessible."""
        logger.debug(f"Waiting for element: '{selector}' (timeout={timeout}s)")
        try:
            ele = self.tab.ele(selector, timeout=timeout)
            if ele:
                return ele
        except Exception as e:
            logger.warning(f"Error querying element '{selector}': {e}")

        raise ElementNotFoundError(f"Element '{selector}' not found within {timeout} seconds")

    def click_element(self, selector: str, timeout: float = 10.0) -> None:
        """Wait for an element and click it."""
        success = self.click_btn(selector, name=selector, timeout=timeout)
        if not success:
            raise ElementNotFoundError(f"Failed to click element '{selector}'")

    def screenshot(self) -> bytes:
        """Capture screenshot of the current page as bytes."""
        try:
            return self.tab.get_screenshot(as_bytes="png")
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")
            return b""

    @property
    def current_url(self) -> str:
        """Get current URL."""
        return getattr(self.tab, "url", "")

    @property
    def title(self) -> str:
        """Get page title."""
        return getattr(self.tab, "title", "")

    @property
    def html(self) -> str:
        """Get page HTML."""
        return getattr(self.tab, "html", "")
