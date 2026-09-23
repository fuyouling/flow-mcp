"""Browser session singleton managing Chromium lifecycle."""
from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from DrissionPage import Chromium, ChromiumOptions
from loguru import logger

from flow_mcp.browser.launcher import get_browser_port, load_browser_flags
from flow_mcp.browser.utils import is_port_in_use, stop_browser
from flow_mcp.config import get_settings
from flow_mcp.utils.errors import BrowserOperationError

_browser: Chromium | None = None


def _build_options(settings) -> ChromiumOptions:
    """Build ChromiumOptions from settings and configuration files."""
    options = ChromiumOptions()
    port = get_browser_port(settings.browser_config_path)
    options.set_local_port(port)

    # User data directory
    if settings.chrome_user_data_dir:
        options.set_user_data_path(settings.chrome_user_data_dir)
    if settings.chrome_profile_directory:
        options.set_argument(f"--profile-directory={settings.chrome_profile_directory}")

    # Download directory
    if settings.chrome_download_dir:
        download_path = Path(settings.chrome_download_dir)
        download_path.mkdir(parents=True, exist_ok=True)
        options.set_download_path(str(download_path))
        options.set_argument("--default-download-directory", str(download_path))
        options.set_pref("download.default_directory", str(download_path))
        options.set_pref("savefile.default_directory", str(download_path))
        options.set_pref("download.prompt_for_download", False)

    # Custom binary path
    if settings.chrome_binary_path:
        options.set_browser_path(str(Path(settings.chrome_binary_path)))

    # Extra startup flags
    env_vars = {
        "CHROME_DOWNLOAD_DIR": settings.chrome_download_dir,
        "CHROME_USER_DATA_DIR": settings.chrome_user_data_dir,
        "CHROME_PROFILE_DIRECTORY": settings.chrome_profile_directory,
    }
    flags = load_browser_flags(settings.browser_config_path, env_vars=env_vars)
    for flag in flags:
        options.set_argument(flag)
        if flag.startswith("--headless"):
            options.headless()

    return options


def get_browser() -> Chromium:
    """Get or initialize the global singleton Chromium instance."""
    global _browser

    if _browser is not None:
        try:
            _ = _browser.version
            return _browser
        except Exception as e:
            logger.warning(f"Browser instance disconnected ({e}). Re-initializing...")
            _browser = None

    settings = get_settings()
    logger.info(f"Initializing browser on port {get_browser_port()} | Profile: {settings.chrome_user_data_dir}")

    for attempt in range(2):
        try:
            options = _build_options(settings)
            _browser = Chromium(addr_or_opts=options)
            logger.info("Browser instance connected successfully.")
            return _browser
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"Browser initialization attempt {attempt + 1} failed: {e}")
            if "BrowserConnectError" in err_msg or "Cannot connect" in err_msg:
                port = get_browser_port(settings.browser_config_path)
                stop_browser(port)
                if settings.chrome_user_data_dir:
                    lock_file = os.path.join(settings.chrome_user_data_dir, "SingletonLock")
                    if os.path.exists(lock_file):
                        try:
                            os.remove(lock_file)
                            logger.info(f"Removed stale lock: {lock_file}")
                        except Exception:
                            pass
                time.sleep(1)
                continue
            raise BrowserOperationError(f"Failed to launch browser: {e}") from e

    if _browser is None:
        raise BrowserOperationError("Unable to establish browser connection after retries.")
    return _browser


def set_browser(browser: Chromium | None) -> None:
    """Explicitly set browser instance (for testing/mocking)."""
    global _browser
    _browser = browser


def close_browser(force: bool = False) -> None:
    """Close and release the global browser instance."""
    global _browser
    if _browser:
        is_external = getattr(_browser, "_is_exists", False)
        if is_external and not force:
            logger.info("External browser instance detected. Releasing reference without killing process.")
            _browser = None
            return

        logger.info("Closing browser process...")
        try:
            _browser.quit()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
        finally:
            _browser = None
