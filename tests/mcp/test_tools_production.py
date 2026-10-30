"""Tests for the consolidated production tools: mixing, EQ, scenes, transport"""

from unittest.mock import MagicMock

import pytest

from bitwig_mcp_server.mcp.tools import execute_tool, get_bitwig_tools


@pytest.fixture
def controller():
    """A controller whose OSC client records every call"""
    c = MagicMock()
    c.client = MagicMock()
    return c


def test_production_tools_are_registered():
    """Every consolidated tool appears in the tool list"""
    names = {t.name for t in get_bitwig_tools()}
    for expected in (
        "track_control",
        "set_track_send",
        "master_control",
        "eq_control",
        "device_control",
        "drumpad_control",
        "scene_control",
        "clip_control",
        "transport_control",
        "automation_control",
        "project_control",
    ):
        assert expected in names


@pytest.mark.asyncio
async def test_track_control_actions(controller):
    """Track actions reach the matching client call"""
    await execute_tool(
        controller,
        "track_control",
        {"action": "rename", "track_index": 2, "name": "Bass"},
    )
    controller.client.set_track_name.assert_called_once_with(2, "Bass")

    await execute_tool(
        controller, "track_control", {"action": "solo", "track_index": 3, "state": True}
    )
    controller.client.set_track_solo.assert_called_once_with(3, True)

    await execute_tool(
        controller,
        "track_control",
        {"action": "color", "track_index": 1, "red": 255, "green": 0, "blue": 64},
    )
    controller.client.set_track_color.assert_called_once_with(1, 255, 0, 64)

    await execute_tool(
        controller, "track_control", {"action": "scroll_bank", "direction": "+"}
    )
    controller.client.navigate_track_bank.assert_called_once_with("+", False)


@pytest.mark.asyncio
async def test_track_control_solo_toggles_when_state_omitted(controller):
    """Leaving state out means toggle, not False"""
    await execute_tool(
        controller, "track_control", {"action": "solo", "track_index": 1}
    )
    controller.client.set_track_solo.assert_called_once_with(1, None)


@pytest.mark.asyncio
async def test_track_control_rejects_unknown_action(controller):
    """An unknown action is reported"""
    result = await execute_tool(
        controller, "track_control", {"action": "explode", "track_index": 1}
    )
    assert "Error" in result[0].text


@pytest.mark.asyncio
async def test_track_control_requires_track_index(controller):
    """Actions that need a track say so"""
    result = await execute_tool(controller, "track_control", {"action": "select"})
    assert "Error" in result[0].text
    controller.client.select_track.assert_not_called()


@pytest.mark.asyncio
async def test_set_track_send(controller):
    """Send level and enablement are independent"""
    await execute_tool(
        controller,
        "set_track_send",
        {"track_index": 1, "send_index": 2, "volume": 40},
    )
    controller.client.set_track_send.assert_called_once_with(1, 2, 40)
    controller.client.set_track_send_activated.assert_not_called()

    await execute_tool(
        controller,
        "set_track_send",
        {"track_index": 1, "send_index": 2, "enabled": True},
    )
    controller.client.set_track_send_activated.assert_called_once_with(1, 2, True)


@pytest.mark.asyncio
async def test_eq_control(controller):
    """EQ add and band shaping"""
    await execute_tool(controller, "eq_control", {"action": "add"})
    controller.client.add_eq.assert_called_once()

    await execute_tool(
        controller, "eq_control", {"action": "type", "band": 1, "band_type": "lowcut"}
    )
    controller.client.set_eq_band_type.assert_called_once_with(1, "lowcut")

    await execute_tool(
        controller, "eq_control", {"action": "frequency", "band": 2, "value": 30}
    )
    controller.client.set_eq_frequency.assert_called_once_with(2, 30)

    await execute_tool(
        controller, "eq_control", {"action": "gain", "band": 3, "value": 80}
    )
    controller.client.set_eq_gain.assert_called_once_with(3, 80)


@pytest.mark.asyncio
async def test_eq_control_band_required_for_band_actions(controller):
    """Shaping a band needs the band number"""
    result = await execute_tool(
        controller, "eq_control", {"action": "gain", "value": 80}
    )
    assert "Error" in result[0].text


@pytest.mark.asyncio
async def test_device_and_drumpad_control(controller):
    """Device pages and drum pad mixing"""
    await execute_tool(
        controller, "device_control", {"action": "select_page", "page": 3}
    )
    controller.client.select_device_page.assert_called_once_with(3)

    await execute_tool(
        controller, "device_control", {"action": "last_parameter", "value": 100}
    )
    controller.client.set_last_parameter.assert_called_once_with(100)

    await execute_tool(
        controller, "drumpad_control", {"action": "volume", "pad": 4, "value": 90}
    )
    controller.client.set_drumpad_volume.assert_called_once_with(4, 90)


@pytest.mark.asyncio
async def test_scene_control(controller):
    """Scene creation, naming and launching"""
    await execute_tool(controller, "scene_control", {"action": "add"})
    controller.client.add_scene.assert_called_once()

    await execute_tool(controller, "scene_control", {"action": "create_from_playing"})
    controller.client.create_scene_from_playing.assert_called_once()

    await execute_tool(
        controller,
        "scene_control",
        {"action": "rename", "scene_index": 1, "name": "Drop"},
    )
    controller.client.set_scene_name.assert_called_once_with(1, "Drop")

    await execute_tool(
        controller, "scene_control", {"action": "launch", "scene_index": 2}
    )
    controller.client.launch_scene.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_clip_control(controller):
    """Clip actions, including ones that need no slot"""
    await execute_tool(controller, "clip_control", {"action": "stop_all"})
    controller.client.stop_all_clips.assert_called_once()

    await execute_tool(controller, "clip_control", {"action": "rename", "name": "Kick"})
    controller.client.set_cursor_clip_name.assert_called_once_with("Kick")

    await execute_tool(
        controller,
        "clip_control",
        {"action": "select", "track_index": 1, "slot_index": 2},
    )
    controller.client.select_clip.assert_called_once_with(1, 2)

    await execute_tool(
        controller, "clip_control", {"action": "stop_track", "track_index": 3}
    )
    controller.client.stop_track_clips.assert_called_once_with(3)


@pytest.mark.asyncio
async def test_transport_control(controller):
    """Transport actions covering both stateful and bare commands"""
    await execute_tool(
        controller, "transport_control", {"action": "play", "state": True}
    )
    controller.client.play.assert_called_once_with(True)

    await execute_tool(controller, "transport_control", {"action": "stop"})
    controller.client.stop.assert_called_once()

    await execute_tool(
        controller, "transport_control", {"action": "repeat", "state": True}
    )
    controller.client.set_repeat.assert_called_once_with(True)

    await execute_tool(
        controller, "transport_control", {"action": "tempo", "value": 128}
    )
    controller.client.set_tempo.assert_called_once_with(128)

    await execute_tool(
        controller,
        "transport_control",
        {"action": "launcher_quantization", "value": "1"},
    )
    controller.client.set_launcher_quantization.assert_called_once_with("1")


@pytest.mark.asyncio
async def test_transport_play_toggles_without_state(controller):
    """Omitting state toggles playback rather than stopping it"""
    await execute_tool(controller, "transport_control", {"action": "play"})
    controller.client.play.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_automation_and_project_control(controller):
    """Automation write and project actions"""
    await execute_tool(controller, "automation_control", {"action": "arranger_write"})
    controller.client.toggle_arranger_automation_write.assert_called_once()

    await execute_tool(
        controller, "automation_control", {"action": "mode", "mode": "latch"}
    )
    controller.client.set_automation_write_mode.assert_called_once_with("latch")

    await execute_tool(controller, "project_control", {"action": "save"})
    controller.client.save_project.assert_called_once()

    await execute_tool(
        controller, "project_control", {"action": "launch_marker", "marker_index": 2}
    )
    controller.client.launch_marker.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_master_control(controller):
    """Master volume, pan and mute"""
    await execute_tool(controller, "master_control", {"action": "volume", "value": 100})
    controller.client.set_master_volume.assert_called_once_with(100)

    await execute_tool(controller, "master_control", {"action": "mute", "state": False})
    controller.client.set_master_mute.assert_called_once_with(False)
