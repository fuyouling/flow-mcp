"""Browser automation package for flow-mcp."""
from flow_mcp.browser.session import get_browser, set_browser, close_browser
from flow_mcp.browser.launcher import get_browser_port, load_browser_flags

__all__ = [
    "get_browser",
    "set_browser",
    "close_browser",
    "get_browser_port",
    "load_browser_flags",
]
