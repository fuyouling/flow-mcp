"""Unit tests to verify page locators and interaction flow alignment with google_flow_mcp."""
from unittest.mock import MagicMock

from flow_mcp.pages.character_page import CharacterPage
from flow_mcp.pages.home_page import HomePage
from flow_mcp.pages.image_edit_page import ImageEditPage
from flow_mcp.pages.image_page import ImagePage
from flow_mcp.pages.video_edit_page import VideoEditPage
from flow_mcp.pages.video_page import VideoPage


def test_home_page_locators():
    mock_tab = MagicMock()
    page = HomePage(mock_tab)

    mock_btn = MagicMock()
    mock_email = MagicMock()
    mock_email.text = "testuser@gmail.com"
    mock_close = MagicMock()

    mock_tab.ele.side_effect = lambda loc, **kwargs: (
        mock_btn if '账号详情' in loc
        else mock_email if 'account-email' in loc
        else mock_close if '关闭账号面板' in loc
        else None
    )

    email = page.get_account_email()
    assert email == "testuser@gmail.com"
    mock_tab.ele.assert_any_call(
        'xpath://button[@aria-label="关闭账号面板" or @aria-label="Close account panel"]',
        timeout=3
    )


def test_image_edit_page_locators():
    mock_tab = MagicMock()
    page = ImageEditPage(mock_tab)

    # Save button
    page.save_and_close()
    mock_tab.ele.assert_any_call('xpath://button[@aria-label="完成修改"]', timeout=5)


def test_video_edit_page_locators():
    mock_tab = MagicMock()
    page = VideoEditPage(mock_tab)

    # Save button
    page.save_and_close()
    mock_tab.ele.assert_any_call('xpath://button[@aria-label="完成场景编辑"]', timeout=5)


def test_image_page_add_assets_locator():
    mock_tab = MagicMock()
    mock_btn = MagicMock()
    mock_search = MagicMock()
    mock_item = MagicMock()
    mock_tab.ele.side_effect = lambda loc, **kwargs: (
        mock_btn if '在提示框中添加素材' in loc
        else mock_search if '搜索资源' in loc
        else mock_item if '添加到提示' in loc
        else None
    )

    page = ImagePage(mock_tab)
    page.add_assets_to_prompt(["test_asset"])

    mock_tab.ele.assert_any_call('xpath://button[@aria-label="在提示框中添加素材"]', timeout=2)
    mock_tab.ele.assert_any_call('xpath://input[@class="search-input" and @placeholder="搜索资源"]', timeout=2)


def test_video_page_frame_mode():
    mock_tab = MagicMock()
    mock_tab.url = "http://flow.google/project/123"
    page = VideoPage(mock_tab)

    mock_chip = MagicMock()
    mock_search = MagicMock()
    mock_add = MagicMock()
    mock_tab.ele.side_effect = lambda loc, **kwargs: (
        mock_chip if '开始' in loc
        else mock_search if '搜索资源' in loc
        else mock_add if '添加到提示' in loc
        else None
    )

    page.bind_frame_image("开始", "frame_start.png")
    mock_tab.ele.assert_any_call("tag:button@@text():开始", timeout=2)
    mock_tab.ele.assert_any_call("tag:input@@placeholder:搜索资源", timeout=2)


def test_character_page_rename_and_locators():
    mock_tab = MagicMock()
    page = CharacterPage(mock_tab)

    mock_input = MagicMock()
    mock_tab.ele.return_value = mock_input
    page.rename_character("HeroBob")

    mock_tab.ele.assert_called_with(
        'xpath://input[@placeholder="角色名称" or @aria-label="角色名称" or contains(@placeholder, "角色")]',
        timeout=3
    )
    mock_input.clear.assert_called_once()
    mock_input.input.assert_called_with("HeroBob")


def test_character_page_first_character_skips_new_button():
    mock_tab = MagicMock()
    mock_tab.url = "http://test/project/1"
    page = CharacterPage(mock_tab)

    mock_char_btn = MagicMock()
    mock_upload_btn = MagicMock()

    def ele_side_effect(loc, **kwargs):
        if 'mat-list-item' in loc:
            return mock_char_btn
        if 'span[text()="上传"]' in loc:
            return mock_upload_btn
        return None

    mock_tab.ele.side_effect = ele_side_effect

    is_first = page.navigate_to_characters("http://test/project/1")
    assert is_first is True
    assert page.is_first_character is True
    mock_char_btn.click.assert_called_once()

    # Now calling click_new_character should skip clicking new_btn
    mock_new_btn = MagicMock()
    mock_tab.ele.side_effect = lambda loc, **kwargs: mock_new_btn if '新角色' in loc else None
    res = page.click_new_character()
    assert res is True
    mock_new_btn.click.assert_not_called()


def test_character_page_subsequent_character_clicks_new_button():
    mock_tab = MagicMock()
    mock_tab.url = "http://test/project/1"
    page = CharacterPage(mock_tab)

    mock_char_btn = MagicMock()
    mock_new_btn = MagicMock()
    mock_editor = MagicMock()

    def ele_side_effect(loc, **kwargs):
        if 'mat-list-item' in loc:
            return mock_char_btn
        if 'span[text()="上传"]' in loc:
            return None  # No upload button -> already has characters
        if '新角色' in loc:
            return mock_new_btn
        if 'ProseMirror' in loc:
            return mock_editor
        return None

    mock_tab.ele.side_effect = ele_side_effect

    is_first = page.navigate_to_characters("http://test/project/1")
    assert is_first is False
    assert page.is_first_character is False
    mock_char_btn.click.assert_called_once()

    res = page.click_new_character()
    assert res is True
    mock_new_btn.click.assert_called_once()

