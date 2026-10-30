"""Tests for the record_pattern and related sequencing tools"""

from unittest.mock import MagicMock, patch

import pytest

from bitwig_mcp_server.mcp.tools import execute_tool, get_bitwig_tools


@pytest.fixture
def controller():
    """A controller whose OSC client records every call"""
    c = MagicMock()
    c.client = MagicMock()
    return c


@pytest.fixture(autouse=True)
def no_waiting():
    """Run the performance without spending real time on it"""

    async def instant(_seconds):
        return None

    with patch("bitwig_mcp_server.mcp.tools.asyncio.sleep", instant):
        yield


def test_sequencing_tools_are_registered():
    """The sequencing tools appear in the tool list"""
    names = {t.name for t in get_bitwig_tools()}
    for expected in (
        "add_track",
        "set_track_recarm",
        "create_clip",
        "launch_clip",
        "launch_scene",
        "quantize_clip",
        "set_metronome",
        "set_time_signature",
        "play_note",
        "record_pattern",
    ):
        assert expected in names


@pytest.mark.asyncio
async def test_add_track_maps_each_type(controller):
    """Each track type calls its own client method"""
    await execute_tool(controller, "add_track", {"track_type": "instrument"})
    controller.client.add_instrument_track.assert_called_once()

    await execute_tool(controller, "add_track", {"track_type": "audio"})
    controller.client.add_audio_track.assert_called_once()

    await execute_tool(controller, "add_track", {"track_type": "effect"})
    controller.client.add_effect_track.assert_called_once()


@pytest.mark.asyncio
async def test_add_track_rejects_unknown_type(controller):
    """An unknown track type is reported, not silently ignored"""
    result = await execute_tool(controller, "add_track", {"track_type": "midi"})
    assert "Error" in result[0].text
    controller.client.add_instrument_track.assert_not_called()


@pytest.mark.asyncio
async def test_record_pattern_performs_setup_and_teardown(controller):
    """The clip is created, armed, recorded, disarmed and quantized"""
    await execute_tool(
        controller,
        "record_pattern",
        {
            "track_index": 2,
            "slot_index": 1,
            "length_beats": 4,
            "bpm": 120,
            "notes": [{"note": 36, "start_beat": 0}],
        },
    )

    controller.client.create_clip.assert_called_once_with(2, 1, 4)
    controller.client.record_clip.assert_called_once_with(2, 1)
    controller.client.quantize_clip.assert_called_once()

    arm_calls = [c.args for c in controller.client.set_track_recarm.call_args_list]
    assert arm_calls == [(2, True), (2, False)]


@pytest.mark.asyncio
async def test_record_pattern_can_skip_quantize(controller):
    """Quantizing is opt-out"""
    await execute_tool(
        controller,
        "record_pattern",
        {
            "track_index": 1,
            "slot_index": 1,
            "length_beats": 4,
            "bpm": 120,
            "notes": [{"note": 60, "start_beat": 0}],
            "quantize": False,
        },
    )
    controller.client.quantize_clip.assert_not_called()


@pytest.mark.asyncio
async def test_record_pattern_releases_overlapping_notes(controller):
    """A chord holds all notes, then releases them -- no early note_off

    Two notes starting together with different lengths must not interleave so
    that the shorter one's release lands before the longer one's attack.
    """
    await execute_tool(
        controller,
        "record_pattern",
        {
            "track_index": 1,
            "slot_index": 1,
            "length_beats": 4,
            "bpm": 120,
            "notes": [
                {"note": 60, "start_beat": 0, "length_beats": 2},
                {"note": 64, "start_beat": 0, "length_beats": 1},
            ],
        },
    )

    ons = [c.args[0] for c in controller.client.note_on.call_args_list]
    offs = [c.args[0] for c in controller.client.note_off.call_args_list]

    assert sorted(ons) == [60, 64]
    # the shorter note (64, 1 beat) releases before the longer one (60, 2 beats)
    assert offs == [64, 60]


@pytest.mark.asyncio
async def test_record_pattern_orders_events_by_beat(controller):
    """Notes are performed in time order regardless of input order"""
    await execute_tool(
        controller,
        "record_pattern",
        {
            "track_index": 1,
            "slot_index": 1,
            "length_beats": 4,
            "bpm": 120,
            "notes": [
                {"note": 62, "start_beat": 2, "length_beats": 0.5},
                {"note": 60, "start_beat": 0, "length_beats": 0.5},
                {"note": 64, "start_beat": 1, "length_beats": 0.5},
            ],
        },
    )

    ons = [c.args[0] for c in controller.client.note_on.call_args_list]
    assert ons == [60, 64, 62]


@pytest.mark.asyncio
async def test_record_pattern_validates_arguments(controller):
    """Missing and malformed arguments are rejected"""
    missing = await execute_tool(
        controller, "record_pattern", {"track_index": 1, "slot_index": 1}
    )
    assert "Error" in missing[0].text

    bad_bpm = await execute_tool(
        controller,
        "record_pattern",
        {
            "track_index": 1,
            "slot_index": 1,
            "length_beats": 4,
            "bpm": 0,
            "notes": [{"note": 60, "start_beat": 0}],
        },
    )
    assert "Error" in bad_bpm[0].text

    no_notes = await execute_tool(
        controller,
        "record_pattern",
        {
            "track_index": 1,
            "slot_index": 1,
            "length_beats": 4,
            "bpm": 120,
            "notes": [],
        },
    )
    assert "Error" in no_notes[0].text

    note_without_start = await execute_tool(
        controller,
        "record_pattern",
        {
            "track_index": 1,
            "slot_index": 1,
            "length_beats": 4,
            "bpm": 120,
            "notes": [{"note": 60}],
        },
    )
    assert "Error" in note_without_start[0].text


@pytest.mark.asyncio
async def test_play_note_holds_then_releases(controller):
    """A single note is switched on and off again"""
    await execute_tool(controller, "play_note", {"note": 48, "velocity": 90})

    controller.client.note_on.assert_called_once_with(48, 90)
    controller.client.note_off.assert_called_once_with(48)
