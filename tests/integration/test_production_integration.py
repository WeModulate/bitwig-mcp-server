"""
Live verification of the production capabilities against Bitwig Studio.

Every check sends a command and reads the value back, because OSC writes are
unacknowledged UDP: a send that "succeeds" proves nothing about whether Bitwig
acted on it. Several addresses in this project turned out to be sent-only, and
only readback catches that.

Tracks are resolved by name rather than by index. /track/{1-8} addresses the
visible bank of eight, and that order changes when tracks are reordered, so a
hardcoded index silently targets the wrong track.
"""

import logging
import time

import pytest

from bitwig_mcp_server.osc.controller import BitwigOSCController
from tests.conftest import skip_if_bitwig_not_running

logger = logging.getLogger(__name__)

pytestmark = skip_if_bitwig_not_running

SETTLE = 1.0
REFRESH_WAIT = 2.2


@pytest.fixture
def controller():
    """A started controller, stopped again afterwards"""
    c = BitwigOSCController()
    c.start()
    if not c.ready:
        c.stop()
        pytest.skip("Could not connect to Bitwig Studio")
    yield c
    c.stop()


def read_all(controller):
    """Refresh and return every cached message

    Returns:
        The controller's received messages
    """
    controller.client.refresh()
    time.sleep(REFRESH_WAIT)
    return controller.server.received_messages


def find_spare_track(controller, wanted_type="audio"):
    """Find a track of a given type, by name rather than by index

    Returns:
        The 1-based bank index of a matching track, or None
    """
    messages = read_all(controller)
    for index in range(1, 9):
        if messages.get(f"/track/{index}/exists") != 1:
            continue
        if messages.get(f"/track/{index}/type") == wanted_type:
            return index
    return None


def test_track_rename_round_trip(controller):
    """A renamed track reports its new name back"""
    index = find_spare_track(controller)
    if index is None:
        pytest.skip("No audio track available to rename")

    messages = read_all(controller)
    original = messages.get(f"/track/{index}/name")

    try:
        controller.client.set_track_name(index, "OSCRenameProbe")
        time.sleep(SETTLE)
        assert read_all(controller).get(f"/track/{index}/name") == "OSCRenameProbe"
    finally:
        controller.client.set_track_name(index, original or f"Audio {index}")
        time.sleep(SETTLE)


def test_track_solo_round_trip(controller):
    """Solo reports 1 when set and 0 when cleared"""
    index = find_spare_track(controller)
    if index is None:
        pytest.skip("No audio track available")

    controller.client.set_track_solo(index, True)
    time.sleep(SETTLE)
    assert read_all(controller).get(f"/track/{index}/solo") == 1

    controller.client.set_track_solo(index, False)
    time.sleep(SETTLE)
    assert read_all(controller).get(f"/track/{index}/solo") == 0


def test_master_volume_round_trip(controller):
    """The master volume takes a new value"""
    original = read_all(controller).get("/master/volume")

    try:
        controller.client.set_master_volume(100)
        time.sleep(SETTLE)
        actual = read_all(controller).get("/master/volume")
        assert actual is not None
        assert abs(float(actual) - 100) < 3
    finally:
        if original is not None:
            controller.client.set_master_volume(float(original))
            time.sleep(SETTLE)


def test_transport_flags_round_trip(controller):
    """Loop and metronome report their new states"""
    controller.client.set_repeat(True)
    controller.client.set_click(True)
    time.sleep(SETTLE)

    messages = read_all(controller)
    assert messages.get("/repeat") == 1
    assert messages.get("/click") == 1

    controller.client.set_repeat(False)
    controller.client.set_click(False)
    time.sleep(SETTLE)

    messages = read_all(controller)
    assert messages.get("/repeat") == 0
    assert messages.get("/click") == 0


def test_launcher_quantization_and_automation_mode(controller):
    """Launcher quantization and the automation write mode both stick"""
    controller.client.set_launcher_quantization("1")
    controller.client.set_automation_write_mode("latch")
    time.sleep(SETTLE)

    messages = read_all(controller)
    assert str(messages.get("/launcher/defaultQuantization")) == "1"
    assert messages.get("/automationWriteMode") == "latch"


def test_scene_rename_round_trip(controller):
    """Scene naming works, unlike clip naming"""
    messages = read_all(controller)
    original = messages.get("/scene/1/name")

    try:
        controller.client.set_scene_name(1, "OSCSceneProbe")
        time.sleep(SETTLE)
        assert read_all(controller).get("/scene/1/name") == "OSCSceneProbe"
    finally:
        controller.client.set_scene_name(1, original or "Scene 1")
        time.sleep(SETTLE)


def test_eq_add_and_band_type(controller):
    """Adding an EQ and setting a band type both take effect

    Readback lives at /eq/type/{band}/value, not /eq/type/{band}: the bare
    address reports nothing, which looks identical to the command failing.
    """
    index = find_spare_track(controller, "audio")
    if index is None:
        pytest.skip("No audio track available to host a probe EQ")

    controller.client.select_track(index)
    time.sleep(SETTLE)

    messages = read_all(controller)
    if messages.get("/device/name"):
        pytest.skip("Selected track already has devices; not touching them")

    try:
        controller.client.add_eq()
        time.sleep(2.0)

        messages = read_all(controller)
        assert messages.get("/device/name") == "EQ+"
        assert messages.get("/eq/exists") == 1

        controller.client.set_eq_band_type(1, "lowcut")
        time.sleep(SETTLE)
        assert read_all(controller).get("/eq/type/1/value") == "lowcut"

        controller.client.set_eq_gain(1, 80)
        time.sleep(SETTLE)
        gain = read_all(controller).get("/eq/gain/1/value")
        assert gain is not None
        assert abs(float(gain) - 80) < 4
    finally:
        controller.client.select_track(index)
        time.sleep(SETTLE)
        if read_all(controller).get("/device/name") == "EQ+":
            controller.client.remove_device()
            time.sleep(SETTLE)


def test_clip_naming_has_no_working_route(controller):
    """Clip naming does not work over OSC, and this records why

    Selecting a slot sets isSelected but leaves /clip/exists at 0, so the
    cursor clip is never established. If a future DrivenByMoss fixes this,
    this test fails and the caveats in set_clip_name and set_cursor_clip_name
    should come off.
    """
    index = find_spare_track(controller, "instrument")
    if index is None:
        pytest.skip("No instrument track available")

    messages = read_all(controller)
    slot = next(
        (
            j
            for j in range(1, 9)
            if messages.get(f"/track/{index}/clip/{j}/hasContent") == 1
        ),
        None,
    )
    if slot is None:
        pytest.skip("No clip available to attempt naming on")

    controller.client.select_clip(index, slot)
    time.sleep(SETTLE)
    controller.client.set_cursor_clip_name("OSCClipProbe")
    time.sleep(SETTLE)

    messages = read_all(controller)
    assert messages.get(f"/track/{index}/clip/{slot}/isSelected") == 1
    assert messages.get("/clip/exists") == 0
    assert messages.get(f"/track/{index}/clip/{slot}/name") != "OSCClipProbe"
