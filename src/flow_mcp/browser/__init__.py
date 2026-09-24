"""Browser automation package for flow-mcp."""
from flow_mcp.browser.launcher import get_browser_port, load_browser_flags
from flow_mcp.browser.session import close_browser, get_browser, set_browser

__all__ = [
    "get_browser",
    "set_browser",
    "close_browser",
    "get_browser_port",
    "load_browser_flags",
]
