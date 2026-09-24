"""Unit tests for credit calculation."""
from flow_mcp.models.job import TaskType
from flow_mcp.utils.credit_calc import calc_task_credits, calc_video_credits, parse_quantity_multiplier


def test_parse_quantity_multiplier():
    assert parse_quantity_multiplier("x1") == 1
    assert parse_quantity_multiplier("x2") == 2
    assert parse_quantity_multiplier("x4") == 4
    assert parse_quantity_multiplier(4) == 4
    assert parse_quantity_multiplier(None) == 1
    assert parse_quantity_multiplier("invalid") == 1


def test_calc_video_credits():
    # Omni Flash 360p = 6
    assert calc_video_credits("Omni 1.1 Flash", "360p", "x1") == 6
    assert calc_video_credits("Omni 1.1 Flash", "360p", "x2") == 12

    # Omni Flash 720p = 12
    assert calc_video_credits("Omni 1.1 Flash", "720p", "x1") == 12
    assert calc_video_credits("Omni 1.1 Flash", "720p", "x4") == 48

    # Veo Lite = 10
    assert calc_video_credits("Veo 3.1 - Lite", "720p", "x1") == 10

    # Veo Fast = 20
    assert calc_video_credits("Veo 3.1 - Fast", "720p", "x1") == 20

    # Veo Quality = 100
    assert calc_video_credits("Veo 3.1 - Quality", "720p", "x1") == 100


def test_calc_task_credits():
    # Image is 0 credits
    assert calc_task_credits(TaskType.IMAGE_CREATE, {}) == 0
    assert calc_task_credits(TaskType.CHARACTER_CREATE, {}) == 0

    # Video uses calculation
    assert calc_task_credits(TaskType.VIDEO_CREATE, {"model_name": "Omni 1.1 Flash", "resolution": "720p", "quantity": 1}) == 12
