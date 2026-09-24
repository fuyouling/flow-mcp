"""Page Object Model package for flow-mcp."""
from flow_mcp.pages.base_page import BasePage
from flow_mcp.pages.character_page import CharacterPage
from flow_mcp.pages.home_page import HomePage
from flow_mcp.pages.image_edit_page import ImageEditPage
from flow_mcp.pages.image_page import ImagePage
from flow_mcp.pages.video_edit_page import VideoEditPage
from flow_mcp.pages.video_page import VideoPage

__all__ = [
    "BasePage",
    "HomePage",
    "ImagePage",
    "VideoPage",
    "CharacterPage",
    "ImageEditPage",
    "VideoEditPage",
]
