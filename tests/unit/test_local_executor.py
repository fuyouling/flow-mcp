"""Unit tests for LocalExecutor."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flow_mcp.local.local_executor import LocalExecutor
from flow_mcp.models.params import ImageCreateByUploadParams


@pytest.mark.asyncio
async def test_ensure_project_url_cached():
    mock_dao = MagicMock()
    mock_dao.get_local_uuid = AsyncMock(return_value="uuid-abc-123")

    executor = LocalExecutor(project_dao=mock_dao, worker_id="master_local_worker")
    with patch("flow_mcp.local.local_executor.get_settings") as mock_settings:
        mock_settings.return_value.google_flow_base_url = "https://flow.google"
        url = await executor.ensure_project_url("my_project")

        assert url == "https://flow.google/project/uuid-abc-123"
        mock_dao.get_local_uuid.assert_called_once_with("my_project", "master_local_worker")


@pytest.mark.asyncio
async def test_create_image_by_upload_with_name():
    mock_dao = MagicMock()
    mock_dao.get_local_uuid = AsyncMock(return_value="uuid-abc-123")

    executor = LocalExecutor(project_dao=mock_dao)

    with patch("flow_mcp.local.local_executor.get_browser"), \
         patch("flow_mcp.local.local_executor.ImagePage") as mock_img_page_cls, \
         patch("flow_mcp.local.local_executor.get_settings") as mock_settings:
        mock_settings.return_value.google_flow_base_url = "https://flow.google"
        mock_page = MagicMock()
        mock_img_page_cls.return_value = mock_page

        params = ImageCreateByUploadParams(
            image_path="C:/path/to/my_photo.png",
            image_name="custom_art_name",
        )
        res = await executor.create_image_by_upload("my_proj", params)

        assert res == {"image_name": "custom_art_name"}
        mock_page.upload_image_on_project_page.assert_called_once_with(
            project_url="https://flow.google/project/uuid-abc-123",
            image_path="C:/path/to/my_photo.png",
            target_name="custom_art_name",
        )


@pytest.mark.asyncio
async def test_create_image_by_upload_stem_fallback():
    """Verify that when image_name is omitted, Path.stem is used without NameError."""
    mock_dao = MagicMock()
    mock_dao.get_local_uuid = AsyncMock(return_value="uuid-abc-123")

    executor = LocalExecutor(project_dao=mock_dao)

    with patch("flow_mcp.local.local_executor.get_browser"), \
         patch("flow_mcp.local.local_executor.ImagePage") as mock_img_page_cls, \
         patch("flow_mcp.local.local_executor.get_settings") as mock_settings:
        mock_settings.return_value.google_flow_base_url = "https://flow.google"
        mock_page = MagicMock()
        mock_img_page_cls.return_value = mock_page

        params = ImageCreateByUploadParams(
            image_path="C:/data/uploads/sunset_view.jpg",
            image_name="",
        )
        res = await executor.create_image_by_upload("my_proj", params)

        # Must extract filename stem 'sunset_view' via Path without error
        assert res == {"image_name": "sunset_view"}
        mock_page.upload_image_on_project_page.assert_called_once_with(
            project_url="https://flow.google/project/uuid-abc-123",
            image_path="C:/data/uploads/sunset_view.jpg",
            target_name="",
        )
