"""Tests for the clip, note and track-creation methods of BitwigOSCClient"""

import unittest
from unittest.mock import MagicMock

import pytest

from bitwig_mcp_server.osc.client import BitwigOSCClient
from bitwig_mcp_server.osc.exceptions import InvalidParameterError


class TestTrackCreation(unittest.TestCase):
    """Test cases for adding tracks and arming them"""

    def setUp(self):
        """Set up test environment"""
        self.client = BitwigOSCClient()
        self.client.client = MagicMock()

    def test_add_tracks(self):
        """Each track type maps to its own address"""
        self.client.add_instrument_track()
        self.client.client.send_message.assert_called_with("/track/add/instrument", 1)

        self.client.add_audio_track()
        self.client.client.send_message.assert_called_with("/track/add/audio", 1)

        self.client.add_effect_track()
        self.client.client.send_message.assert_called_with("/track/add/effect", 1)

    def test_set_track_recarm(self):
        """Arming sends 1, disarming 0, and omitting the state toggles"""
        self.client.set_track_recarm(2, True)
        self.client.client.send_message.assert_called_with("/track/2/recarm", 1)

        self.client.set_track_recarm(2, False)
        self.client.client.send_message.assert_called_with("/track/2/recarm", 0)

        self.client.set_track_recarm(2)
        self.client.client.send_message.assert_called_with("/track/2/recarm", None)

    def test_set_track_recarm_rejects_bad_index(self):
        """Track indices are 1-based"""
        with pytest.raises(InvalidParameterError):
            self.client.set_track_recarm(0, True)

        with pytest.raises(InvalidParameterError):
            self.client.set_track_recarm("1", True)


class TestClipControls(unittest.TestCase):
    """Test cases for clip creation and launching"""

    def setUp(self):
        """Set up test environment"""
        self.client = BitwigOSCClient()
        self.client.client = MagicMock()

    def test_create_clip(self):
        """Clip creation carries the length in beats"""
        self.client.create_clip(1, 2, 16)
        self.client.client.send_message.assert_called_with("/track/1/clip/2/create", 16)

    def test_create_clip_validation(self):
        """Slot range and beat length are checked"""
        with pytest.raises(InvalidParameterError):
            self.client.create_clip(1, 9, 16)  # slots are 1-8

        with pytest.raises(InvalidParameterError):
            self.client.create_clip(1, 1, 0)  # needs at least one beat

        with pytest.raises(InvalidParameterError):
            self.client.create_clip(1, 1, 4.5)  # beats must be an integer

    def test_launch_and_record_clip(self):
        """Launch and record address the same slot"""
        self.client.launch_clip(3, 1)
        self.client.client.send_message.assert_called_with("/track/3/clip/1/launch", 1)

        self.client.launch_clip(3, 1, False)
        self.client.client.send_message.assert_called_with("/track/3/clip/1/launch", 0)

        self.client.record_clip(3, 1)
        self.client.client.send_message.assert_called_with("/track/3/clip/1/record", 1)

    def test_clip_name_and_quantize(self):
        """Naming and quantizing a clip

        Naming is asserted at the wire level only: Bitwig ignores the message
        in practice, which set_clip_name documents.
        """
        self.client.set_clip_name(1, 1, "Kick")
        self.client.client.send_message.assert_called_with(
            "/track/1/clip/1/name", "Kick"
        )

        self.client.quantize_clip()
        self.client.client.send_message.assert_called_with("/clip/quantize", 1)

    def test_remove_clip(self):
        """Removing a clip targets its slot"""
        self.client.remove_clip(2, 3)
        self.client.client.send_message.assert_called_with("/track/2/clip/3/remove", 1)

        with pytest.raises(InvalidParameterError):
            self.client.remove_clip(2, 0)

    def test_launch_scene(self):
        """Scene launching is 1-based"""
        self.client.launch_scene(1)
        self.client.client.send_message.assert_called_with("/scene/1/launch", 1)

        with pytest.raises(InvalidParameterError):
            self.client.launch_scene(0)


class TestTransportAndNotes(unittest.TestCase):
    """Test cases for recording transport and virtual-keyboard notes"""

    def setUp(self):
        """Set up test environment"""
        self.client = BitwigOSCClient()
        self.client.client = MagicMock()

    def test_record_and_overdub_and_click(self):
        """Recording helpers map to their addresses"""
        self.client.record()
        self.client.client.send_message.assert_called_with("/record", 1)

        self.client.set_overdub(True)
        self.client.client.send_message.assert_called_with("/overdub", 1)

        self.client.set_click(False)
        self.client.client.send_message.assert_called_with("/click", 0)

    def test_position_and_time_signature(self):
        """Playhead position and time signature"""
        self.client.set_position(8)
        self.client.client.send_message.assert_called_with("/time", 8)

        self.client.set_time_signature("4/4")
        self.client.client.send_message.assert_called_with("/time/signature", "4/4")

        with pytest.raises(InvalidParameterError):
            self.client.set_position(-1)

        with pytest.raises(InvalidParameterError):
            self.client.set_time_signature("four-four")

    def test_note_on_off(self):
        """Note on carries velocity, note off sends zero velocity"""
        self.client.note_on(60, 100)
        self.client.client.send_message.assert_called_with("/vkb_midi/1/note/60", 100)

        self.client.note_off(60)
        self.client.client.send_message.assert_called_with("/vkb_midi/1/note/60", 0)

        self.client.note_on(36, 120, channel=10)
        self.client.client.send_message.assert_called_with("/vkb_midi/10/note/36", 120)

    def test_note_validation(self):
        """Note number, velocity and channel ranges are enforced"""
        with pytest.raises(InvalidParameterError):
            self.client.note_on(128)

        with pytest.raises(InvalidParameterError):
            self.client.note_on(-1)

        with pytest.raises(InvalidParameterError):
            self.client.note_on(60, 200)

        with pytest.raises(InvalidParameterError):
            self.client.note_on(60, 100, channel=17)


if __name__ == "__main__":
    unittest.main()
