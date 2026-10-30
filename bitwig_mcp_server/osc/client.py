"""
Bitwig OSC Client

Handles communication with Bitwig Studio via OSC
"""

import logging
import socket
from typing import Any, Dict, List, Optional

from pythonosc import udp_client

from .exceptions import (
    ConnectionError,
    InvalidParameterError,
)

logger = logging.getLogger(__name__)

# Default OSC settings (matching Bitwig/git-moss defaults)
DEFAULT_BITWIG_IP = "127.0.0.1"
DEFAULT_SEND_PORT = 8000  # Port Bitwig listens on


class BitwigOSCClient:
    """Client for sending OSC messages to Bitwig Studio"""

    def __init__(self, ip: str = DEFAULT_BITWIG_IP, port: int = DEFAULT_SEND_PORT):
        """Initialize the OSC client

        Args:
            ip: The IP address of the Bitwig instance
            port: The port Bitwig is listening on for OSC messages

        Raises:
            ConnectionError: If unable to create the UDP client
        """
        try:
            self.ip = ip
            self.port = port
            self.client = udp_client.SimpleUDPClient(ip, port)
            self.addr_log: List[str] = []  # Log of sent addresses for verification
        except socket.error as e:
            raise ConnectionError(details=f"Failed to create UDP client: {e}")
        except Exception as e:
            raise ConnectionError(details=str(e))

    def send(self, address: str, value: Any) -> None:
        """Send an OSC message to Bitwig

        Args:
            address: The OSC address to send to
            value: The value to send

        Raises:
            ConnectionError: If unable to send the message
        """
        try:
            logger.debug(f"Sending: {address} = {value}")
            self.client.send_message(address, value)
            self.addr_log.append(address)
        except socket.error as e:
            raise ConnectionError(details=f"Failed to send message to {address}: {e}")
        except Exception as e:
            raise ConnectionError(details=f"Error sending message to {address}: {e}")

    def get_sent_addresses(self) -> List[str]:
        """Get list of addresses that were sent

        Returns:
            List of OSC addresses that have been sent
        """
        return self.addr_log

    def refresh(self) -> None:
        """Request a refresh of all values from Bitwig

        Raises:
            ConnectionError: If unable to send the refresh command
        """
        self.send("/refresh", 1)

    # Transport controls
    def play(self, state: Optional[bool] = None) -> None:
        """Control playback

        Args:
            state: True to play, False to stop, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/play", None)  # Toggle
        else:
            self.send("/play", 1 if state else 0)

    def stop(self) -> None:
        """Stop playback

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/stop", 1)

    def set_tempo(self, bpm: float) -> None:
        """Set the tempo

        Args:
            bpm: Tempo in beats per minute (20-999)

        Raises:
            InvalidParameterError: If bpm is not a number
            ConnectionError: If unable to send the command
        """
        # Tempo range is effectively 20-999 in Bitwig
        if not isinstance(bpm, (int, float)):
            raise InvalidParameterError("bpm", bpm, "must be a number")

        # Give a wider range than Bitwig accepts to allow for clamping
        MAX_TEMPO = 999
        MIN_TEMPO = 20

        if bpm < MIN_TEMPO:
            logger.warning(f"Tempo {bpm} below minimum ({MIN_TEMPO}), clamping")
            bpm = MIN_TEMPO
        elif bpm > MAX_TEMPO:
            logger.warning(f"Tempo {bpm} above maximum ({MAX_TEMPO}), clamping")
            bpm = MAX_TEMPO

        self.send("/tempo/raw", bpm)

    # Track controls
    def set_track_volume(self, track_index: int, volume: float) -> None:
        """Set track volume

        Args:
            track_index: Track index (1-based)
            volume: Volume value (0-128, where 64 is 0dB)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(track_index, int):
            raise InvalidParameterError(
                "track_index", track_index, "must be an integer"
            )

        if track_index < 1:
            raise InvalidParameterError(
                "track_index", track_index, "must be at least 1 (1-based indexing)"
            )

        MAX_VALUE = 128
        MIN_VALUE = 0

        if not isinstance(volume, (int, float)):
            raise InvalidParameterError("volume", volume, "must be a number")

        if volume < MIN_VALUE:
            logger.warning(f"Volume {volume} below minimum ({MIN_VALUE}), clamping")
            volume = MIN_VALUE
        elif volume > MAX_VALUE:
            logger.warning(f"Volume {volume} above maximum ({MAX_VALUE}), clamping")
            volume = MAX_VALUE

        self.send(f"/track/{track_index}/volume", volume)

    def set_track_pan(self, track_index: int, pan: float) -> None:
        """Set track pan

        Args:
            track_index: Track index (1-based)
            pan: Pan value (0-128, where 64 is center)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(track_index, int):
            raise InvalidParameterError(
                "track_index", track_index, "must be an integer"
            )

        if track_index < 1:
            raise InvalidParameterError(
                "track_index", track_index, "must be at least 1 (1-based indexing)"
            )

        MAX_VALUE = 128
        MIN_VALUE = 0

        if not isinstance(pan, (int, float)):
            raise InvalidParameterError("pan", pan, "must be a number")

        if pan < MIN_VALUE:
            logger.warning(
                f"Pan {pan} below minimum ({MIN_VALUE}), clamping to left extreme"
            )
            pan = MIN_VALUE
        elif pan > MAX_VALUE:
            logger.warning(
                f"Pan {pan} above maximum ({MAX_VALUE}), clamping to right extreme"
            )
            pan = MAX_VALUE

        self.send(f"/track/{track_index}/pan", pan)

    def toggle_track_mute(self, track_index: int) -> None:
        """Toggle track mute state

        Args:
            track_index: Track index (1-based)

        Raises:
            InvalidParameterError: If track_index is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(track_index, int):
            raise InvalidParameterError(
                "track_index", track_index, "must be an integer"
            )

        if track_index < 1:
            raise InvalidParameterError(
                "track_index", track_index, "must be at least 1 (1-based indexing)"
            )

        self.send(f"/track/{track_index}/mute", None)

    def set_track_mute(self, track_index: int, mute: bool) -> None:
        """Set track mute state

        Args:
            track_index: Track index (1-based)
            mute: True to mute, False to unmute

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(track_index, int):
            raise InvalidParameterError(
                "track_index", track_index, "must be an integer"
            )

        if track_index < 1:
            raise InvalidParameterError(
                "track_index", track_index, "must be at least 1 (1-based indexing)"
            )

        if not isinstance(mute, bool):
            raise InvalidParameterError("mute", mute, "must be a boolean")

        self.send(f"/track/{track_index}/mute", 1 if mute else 0)

    # Device controls
    def set_device_parameter(self, param_index: int, value: float) -> None:
        """Set device parameter value

        Args:
            param_index: Parameter index (1-based)
            value: Parameter value (0-128)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(param_index, int):
            raise InvalidParameterError(
                "param_index", param_index, "must be an integer"
            )

        if param_index < 1:
            raise InvalidParameterError(
                "param_index", param_index, "must be at least 1 (1-based indexing)"
            )

        if param_index > 8:
            raise InvalidParameterError("param_index", param_index, "must be at most 8")

        MAX_VALUE = 128
        MIN_VALUE = 0

        if not isinstance(value, (int, float)):
            raise InvalidParameterError("value", value, "must be a number")

        if value < MIN_VALUE:
            logger.warning(
                f"Parameter value {value} below minimum ({MIN_VALUE}), clamping"
            )
            value = MIN_VALUE
        elif value > MAX_VALUE:
            logger.warning(
                f"Parameter value {value} above maximum ({MAX_VALUE}), clamping"
            )
            value = MAX_VALUE

        self.send(f"/device/param/{param_index}/value", value)

    def toggle_device_bypass(self) -> None:
        """Toggle bypass state of the currently selected device

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/device/bypass", None)

    def select_device_sibling(self, sibling_index: int) -> None:
        """Select a sibling device (in the same chain as current device)

        Args:
            sibling_index: Index of the sibling device (1-8)

        Raises:
            InvalidParameterError: If sibling_index is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(sibling_index, int):
            raise InvalidParameterError(
                "sibling_index", sibling_index, "must be an integer"
            )

        if sibling_index < 1 or sibling_index > 8:
            raise InvalidParameterError(
                "sibling_index", sibling_index, "must be between 1 and 8"
            )

        self.send(f"/device/sibling/{sibling_index}/select", 1)

    def navigate_device(self, direction: str) -> None:
        """Navigate to next/previous device

        Args:
            direction: Navigation direction, either "next" or "previous"

        Raises:
            InvalidParameterError: If direction is invalid
            ConnectionError: If unable to send the command
        """
        if direction not in ["next", "previous"]:
            raise InvalidParameterError(
                "direction", direction, "must be either 'next' or 'previous'"
            )

        # Map to OSC command
        nav_symbol = "+" if direction == "next" else "-"
        self.send(f"/device/{nav_symbol}", None)

    def enter_device_layer(self, layer_index: int) -> None:
        """Enter a device layer/chain

        Args:
            layer_index: Index of the layer to enter (1-8)

        Raises:
            InvalidParameterError: If layer_index is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(layer_index, int):
            raise InvalidParameterError(
                "layer_index", layer_index, "must be an integer"
            )

        if layer_index < 1 or layer_index > 8:
            raise InvalidParameterError(
                "layer_index", layer_index, "must be between 1 and 8"
            )

        self.send(f"/device/layer/{layer_index}/enter", None)

    def exit_device_layer(self) -> None:
        """Exit current device layer (go to parent)

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/device/layer/parent", None)

    def toggle_device_window(self) -> None:
        """Toggle device window visibility

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/device/window", None)

    def select_device_by_index(self, device_index: int) -> None:
        """Select a device by its index

        Args:
            device_index: Index of the device to select (1-based)

        Raises:
            InvalidParameterError: If device_index is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(device_index, int):
            raise InvalidParameterError(
                "device_index", device_index, "must be an integer"
            )

        if device_index < 1:
            raise InvalidParameterError(
                "device_index", device_index, "must be at least 1 (1-based indexing)"
            )

        self.send(f"/device/select/{device_index}", 1)

    # Browser controls based on OSC documentation
    def browse_for_device(self, position: str = "after") -> None:
        """Activate browser to insert a device

        Args:
            position: Where to insert the device ("after" or "before" the selected device)

        Raises:
            InvalidParameterError: If position is invalid
            ConnectionError: If unable to send the command
        """
        if position not in ["after", "before"]:
            raise InvalidParameterError(
                "position", position, "must be either 'after' or 'before'"
            )

        if position == "after":
            self.send("/browser/device", None)
        else:
            self.send("/browser/device/before", None)

    def browse_for_preset(self) -> None:
        """Activate browser to browse for presets of currently selected device

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/browser/preset", None)

    def commit_browser_selection(self) -> None:
        """Commit the current selection in the browser

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/browser/commit", None)

    def cancel_browser(self) -> None:
        """Cancel the current browser session

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/browser/cancel", None)

    def navigate_browser_tab(self, direction: str) -> None:
        """Navigate between browser tabs

        Args:
            direction: Direction to navigate ("+", "-")

        Raises:
            InvalidParameterError: If direction is invalid
            ConnectionError: If unable to send the command
        """
        if direction not in ["+", "-"]:
            raise InvalidParameterError(
                "direction", direction, "must be either '+' or '-'"
            )

        self.send(f"/browser/tab/{direction}", None)

    def navigate_browser_filter(self, filter_index: int, direction: str) -> None:
        """Navigate through filter options

        Args:
            filter_index: Index of the filter column (1-6)
            direction: Direction to navigate ("+", "-")

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(filter_index, int) or filter_index < 1 or filter_index > 6:
            raise InvalidParameterError(
                "filter_index", filter_index, "must be between 1 and 6"
            )

        if direction not in ["+", "-"]:
            raise InvalidParameterError(
                "direction", direction, "must be either '+' or '-'"
            )

        self.send(f"/browser/filter/{filter_index}/{direction}", None)

    def reset_browser_filter(self, filter_index: int) -> None:
        """Reset a browser filter

        Args:
            filter_index: Index of the filter column to reset (1-6)

        Raises:
            InvalidParameterError: If filter_index is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(filter_index, int) or filter_index < 1 or filter_index > 6:
            raise InvalidParameterError(
                "filter_index", filter_index, "must be between 1 and 6"
            )

        self.send(f"/browser/filter/{filter_index}/reset", None)

    def navigate_browser_result(self, direction: str) -> None:
        """Navigate through browser results

        Args:
            direction: Direction to navigate ("+", "-")

        Raises:
            InvalidParameterError: If direction is invalid
            ConnectionError: If unable to send the command
        """
        if direction not in ["+", "-"]:
            raise InvalidParameterError(
                "direction", direction, "must be either '+' or '-'"
            )

        self.send(f"/browser/result/{direction}", None)

    def navigate_browser_result_page(self, direction: str) -> None:
        """Navigate through browser result pages (each page contains up to 16 results)

        Args:
            direction: Direction to navigate ("+", "-")

        Raises:
            InvalidParameterError: If direction is invalid
            ConnectionError: If unable to send the command
        """
        if direction not in ["+", "-"]:
            raise InvalidParameterError(
                "direction", direction, "must be either '+' or '-'"
            )

        # Page navigation addresses based on DrivenByMoss implementation
        self.send(f"/browser/result/page/{direction}", None)

    # Higher-level convenience methods for common tasks
    def insert_device_after_selected(self) -> None:
        """Open browser to insert a device after the currently selected one

        Raises:
            ConnectionError: If unable to send the command
        """
        self.browse_for_device("after")

    def insert_device_before_selected(self) -> None:
        """Open browser to insert a device before the currently selected one

        Raises:
            ConnectionError: If unable to send the command
        """
        self.browse_for_device("before")

    def browse_device_presets(self) -> None:
        """Open browser to browse presets for the currently selected device

        Raises:
            ConnectionError: If unable to send the command
        """
        self.browse_for_preset()

    def select_next_browser_tab(self) -> None:
        """Select the next browser tab

        Raises:
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_tab("+")

    def select_previous_browser_tab(self) -> None:
        """Select the previous browser tab

        Raises:
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_tab("-")

    def select_next_filter_option(self, filter_index: int) -> None:
        """Select the next option in a filter column

        Args:
            filter_index: Index of the filter column (1-6)

        Raises:
            InvalidParameterError: If filter_index is invalid
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_filter(filter_index, "+")

    def select_previous_filter_option(self, filter_index: int) -> None:
        """Select the previous option in a filter column

        Args:
            filter_index: Index of the filter column (1-6)

        Raises:
            InvalidParameterError: If filter_index is invalid
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_filter(filter_index, "-")

    def select_next_browser_result(self) -> None:
        """Select the next result in the browser

        Raises:
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_result("+")

    def select_previous_browser_result(self) -> None:
        """Select the previous result in the browser

        Raises:
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_result("-")

    def select_next_browser_result_page(self) -> None:
        """Navigate to the next page of browser results (up to 16 results per page)

        Raises:
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_result_page("+")

    def select_previous_browser_result_page(self) -> None:
        """Navigate to the previous page of browser results (up to 16 results per page)

        Raises:
            ConnectionError: If unable to send the command
        """
        self.navigate_browser_result_page("-")

    # Workflow helper methods
    def browse_and_insert_device(
        self, num_tabs: int = 0, num_filters: List[int] = None, num_results: int = 0
    ) -> None:
        """Browse and insert a device using navigation commands

        Args:
            num_tabs: Number of tab navigations (positive = forward, negative = backward)
            num_filters: List of filter navigations by column index (e.g., [(1, 2), (4, -1)])
                        Format: List of tuples (filter_index, num_navigations)
            num_results: Number of result navigations (positive = forward, negative = backward)

        Raises:
            ConnectionError: If unable to send commands
        """
        # Open device browser
        self.browse_for_device("after")

        # Navigate to desired tab
        for _ in range(abs(num_tabs)):
            direction = "+" if num_tabs >= 0 else "-"
            self.navigate_browser_tab(direction)

        # Apply filter selections
        if num_filters:
            for filter_index, num_navigations in num_filters:
                for _ in range(abs(num_navigations)):
                    direction = "+" if num_navigations >= 0 else "-"
                    self.navigate_browser_filter(filter_index, direction)

        # Navigate to desired result
        for _ in range(abs(num_results)):
            direction = "+" if num_results >= 0 else "-"
            self.navigate_browser_result(direction)

        # Commit selection
        self.commit_browser_selection()

    def browse_and_load_preset(
        self, num_filters: List[int] = None, num_results: int = 0
    ) -> None:
        """Browse and load a preset using navigation commands

        Args:
            num_filters: List of filter navigations by column index (e.g., [(1, 2), (4, -1)])
                        Format: List of tuples (filter_index, num_navigations)
            num_results: Number of result navigations (positive = forward, negative = backward)

        Raises:
            ConnectionError: If unable to send commands
        """
        # Open preset browser
        self.browse_for_preset()

        # Apply filter selections
        if num_filters:
            for filter_index, num_navigations in num_filters:
                for _ in range(abs(num_navigations)):
                    direction = "+" if num_navigations >= 0 else "-"
                    self.navigate_browser_filter(filter_index, direction)

        # Navigate to desired result
        for _ in range(abs(num_results)):
            direction = "+" if num_results >= 0 else "-"
            self.navigate_browser_result(direction)

        # Commit selection
        self.commit_browser_selection()

    # Track creation
    def add_instrument_track(self) -> None:
        """Append a new instrument track to the project

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/track/add/instrument", 1)

    def add_audio_track(self) -> None:
        """Append a new audio track to the project

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/track/add/audio", 1)

    def add_effect_track(self) -> None:
        """Append a new effect track to the project

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/track/add/effect", 1)

    def set_track_recarm(self, track_index: int, state: Optional[bool] = None) -> None:
        """Arm or disarm a track for recording

        Args:
            track_index: Track index (1-based)
            state: True to arm, False to disarm, None to toggle

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)

        if state is None:
            self.send(f"/track/{track_index}/recarm", None)
        else:
            self.send(f"/track/{track_index}/recarm", 1 if state else 0)

    # Clip controls
    def create_clip(self, track_index: int, slot_index: int, beats: int) -> None:
        """Create an empty clip in a clip slot

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)
            beats: Length of the new clip in beats

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)

        if not isinstance(beats, int) or isinstance(beats, bool):
            raise InvalidParameterError("beats", beats, "must be an integer")

        if beats < 1:
            raise InvalidParameterError("beats", beats, "must be at least 1")

        self.send(f"/track/{track_index}/clip/{slot_index}/create", beats)

    def launch_clip(
        self, track_index: int, slot_index: int, state: bool = True
    ) -> None:
        """Launch or release a clip

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)
            state: True to launch, False to release

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)

        self.send(f"/track/{track_index}/clip/{slot_index}/launch", 1 if state else 0)

    def record_clip(self, track_index: int, slot_index: int) -> None:
        """Start recording into a clip slot

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)

        self.send(f"/track/{track_index}/clip/{slot_index}/record", 1)

    def set_clip_name(self, track_index: int, slot_index: int, name: str) -> None:
        """Name a clip

        Does not work, and cannot: /track/{i}/clip/{j}/name only exists as a
        sent message, reporting a clip's name out of the DAW. It is not in the
        protocol's received commands, so Bitwig never acts on it. Kept only so
        callers reaching for it find this explanation; use the cursor-clip
        route in set_cursor_clip_name instead, and read its caveat first.
        Deliberately not exposed as an MCP tool.

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)
            name: Name to give the clip

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)

        if not isinstance(name, str):
            raise InvalidParameterError("name", name, "must be a string")

        self.send(f"/track/{track_index}/clip/{slot_index}/name", name)

    def remove_clip(self, track_index: int, slot_index: int) -> None:
        """Delete the clip in a clip slot

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)

        self.send(f"/track/{track_index}/clip/{slot_index}/remove", 1)

    def quantize_clip(self) -> None:
        """Quantize the currently selected clip

        Bitwig quantizes to the grid configured in its own settings. This is how
        note timing is repaired after notes are performed over OSC, where send
        jitter puts them slightly off the beat.

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/clip/quantize", 1)

    def launch_scene(self, scene_index: int, state: bool = True) -> None:
        """Launch a scene

        Args:
            scene_index: Scene index (1-based)
            state: True to launch, False to release

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(scene_index, int) or isinstance(scene_index, bool):
            raise InvalidParameterError(
                "scene_index", scene_index, "must be an integer"
            )

        if scene_index < 1:
            raise InvalidParameterError(
                "scene_index", scene_index, "must be at least 1 (1-based indexing)"
            )

        self.send(f"/scene/{scene_index}/launch", 1 if state else 0)

    # Transport and recording
    def record(self) -> None:
        """Toggle the transport record button

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/record", 1)

    def set_overdub(self, state: Optional[bool] = None) -> None:
        """Set launcher overdub

        Args:
            state: True to enable, False to disable, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/overdub", None)
        else:
            self.send("/overdub", 1 if state else 0)

    def set_click(self, state: Optional[bool] = None) -> None:
        """Set the metronome

        Args:
            state: True to enable, False to disable, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/click", None)
        else:
            self.send("/click", 1 if state else 0)

    def set_position(self, beats: float) -> None:
        """Move the playhead to a position

        Args:
            beats: Position in beats from the start of the arrangement

        Raises:
            InvalidParameterError: If beats is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(beats, (int, float)) or isinstance(beats, bool):
            raise InvalidParameterError("beats", beats, "must be a number")

        if beats < 0:
            raise InvalidParameterError("beats", beats, "must not be negative")

        self.send("/time", beats)

    def set_time_signature(self, signature: str) -> None:
        """Set the project time signature

        Args:
            signature: Time signature as text, such as 4/4

        Raises:
            InvalidParameterError: If signature is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(signature, str) or "/" not in signature:
            raise InvalidParameterError(
                "signature", signature, "must be text such as 4/4"
            )

        self.send("/time/signature", signature)

    # Note input via the virtual keyboard
    def note_on(self, note: int, velocity: int = 100, channel: int = 1) -> None:
        """Play a note

        Notes sent this way are played live, exactly as if they arrived from a
        MIDI keyboard, so they are only captured if a clip is recording. There
        is no OSC address for writing notes into a clip directly.

        Args:
            note: MIDI note number (0-127)
            velocity: Note velocity (0-127)
            channel: MIDI channel (1-16)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_note(note)
        self._validate_channel(channel)

        if not isinstance(velocity, int) or isinstance(velocity, bool):
            raise InvalidParameterError("velocity", velocity, "must be an integer")

        if velocity < 0 or velocity > 127:
            raise InvalidParameterError("velocity", velocity, "must be 0-127")

        self.send(f"/vkb_midi/{channel}/note/{note}", velocity)

    def note_off(self, note: int, channel: int = 1) -> None:
        """Release a note

        Args:
            note: MIDI note number (0-127)
            channel: MIDI channel (1-16)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_note(note)
        self._validate_channel(channel)

        self.send(f"/vkb_midi/{channel}/note/{note}", 0)

    # Shared validation
    def _validate_track_index(self, track_index: int) -> None:
        """Check a 1-based track index

        Raises:
            InvalidParameterError: If the index is invalid
        """
        if not isinstance(track_index, int) or isinstance(track_index, bool):
            raise InvalidParameterError(
                "track_index", track_index, "must be an integer"
            )

        if track_index < 1:
            raise InvalidParameterError(
                "track_index", track_index, "must be at least 1 (1-based indexing)"
            )

    def _validate_slot_index(self, slot_index: int) -> None:
        """Check a 1-based clip slot index

        Raises:
            InvalidParameterError: If the index is invalid
        """
        if not isinstance(slot_index, int) or isinstance(slot_index, bool):
            raise InvalidParameterError("slot_index", slot_index, "must be an integer")

        if slot_index < 1 or slot_index > 8:
            raise InvalidParameterError("slot_index", slot_index, "must be 1-8")

    def _validate_note(self, note: int) -> None:
        """Check a MIDI note number

        Raises:
            InvalidParameterError: If the note is invalid
        """
        if not isinstance(note, int) or isinstance(note, bool):
            raise InvalidParameterError("note", note, "must be an integer")

        if note < 0 or note > 127:
            raise InvalidParameterError("note", note, "must be 0-127")

    def _validate_channel(self, channel: int) -> None:
        """Check a MIDI channel

        Raises:
            InvalidParameterError: If the channel is invalid
        """
        if not isinstance(channel, int) or isinstance(channel, bool):
            raise InvalidParameterError("channel", channel, "must be an integer")

        if channel < 1 or channel > 16:
            raise InvalidParameterError("channel", channel, "must be 1-16")

    # Track management
    def set_track_name(self, track_index: int, name: str) -> None:
        """Rename a track

        Args:
            track_index: Track index (1-based, within the visible bank of 8)
            name: New track name

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)

        if not isinstance(name, str):
            raise InvalidParameterError("name", name, "must be a string")

        self.send(f"/track/{track_index}/name", name)

    def select_track(self, track_index: int) -> None:
        """Select a track

        Args:
            track_index: Track index (1-based)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self.send(f"/track/{track_index}/select", 1)

    def duplicate_track(self, track_index: int) -> None:
        """Duplicate a track

        Args:
            track_index: Track index (1-based)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self.send(f"/track/{track_index}/duplicate", 1)

    def remove_track(self, track_index: int) -> None:
        """Delete a track

        Args:
            track_index: Track index (1-based)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self.send(f"/track/{track_index}/remove", 1)

    def set_track_solo(self, track_index: int, state: Optional[bool] = None) -> None:
        """Solo or unsolo a track

        Args:
            track_index: Track index (1-based)
            state: True to solo, False to clear, None to toggle

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)

        if state is None:
            self.send(f"/track/{track_index}/solo", None)
        else:
            self.send(f"/track/{track_index}/solo", 1 if state else 0)

    def toggle_track_monitor(self, track_index: int) -> None:
        """Toggle input monitoring on a track

        The protocol offers no explicit on/off for monitoring, only a toggle.

        Args:
            track_index: Track index (1-based)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self.send(f"/track/{track_index}/monitor", 1)

    def set_track_activated(
        self, track_index: int, state: Optional[bool] = None
    ) -> None:
        """Activate or deactivate a track

        Args:
            track_index: Track index (1-based)
            state: True to activate, False to deactivate, None to toggle

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)

        if state is None:
            self.send(f"/track/{track_index}/activated", None)
        else:
            self.send(f"/track/{track_index}/activated", 1 if state else 0)

    def set_track_color(
        self, track_index: int, red: int, green: int, blue: int
    ) -> None:
        """Colour a track

        Args:
            track_index: Track index (1-based)
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self.send(f"/track/{track_index}/color", self._format_color(red, green, blue))

    def set_track_send(self, track_index: int, send_index: int, volume: float) -> None:
        """Set a send level on a track

        Sends are how reverb and delay are shared between tracks, so this is
        the main routing control for a mix.

        Args:
            track_index: Track index (1-based)
            send_index: Send index (1-based, 1-8)
            volume: Send level (0-128, matching the track volume range)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_send_index(send_index)
        volume = self._clamp_value("volume", volume)

        self.send(f"/track/{track_index}/send/{send_index}/volume", volume)

    def set_track_send_activated(
        self, track_index: int, send_index: int, state: Optional[bool] = None
    ) -> None:
        """Enable or disable a send on a track

        Args:
            track_index: Track index (1-based)
            send_index: Send index (1-based, 1-8)
            state: True to enable, None to toggle

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_send_index(send_index)

        if state is None:
            self.send(f"/track/{track_index}/send/{send_index}/activated", None)
        else:
            self.send(
                f"/track/{track_index}/send/{send_index}/activated",
                1 if state else 0,
            )

    def set_track_record_quantization(self, track_index: int, value: str) -> None:
        """Set the MIDI record quantization for a track

        Args:
            track_index: Track index (1-based)
            value: One of OFF, 1/32, 1/16, 1/8, 1/4

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)

        allowed = ("OFF", "1/32", "1/16", "1/8", "1/4")
        if value not in allowed:
            raise InvalidParameterError(
                "value", value, f"must be one of {', '.join(allowed)}"
            )

        self.send(f"/track/{track_index}/recordQuantization", value)

    def navigate_track_bank(self, direction: str, by_page: bool = False) -> None:
        """Scroll the visible bank of 8 tracks

        Track addresses are relative to this bank, so projects with more than
        eight tracks need this to reach the rest.

        Args:
            direction: "+" for later tracks, "-" for earlier
            by_page: True to move a whole page of 8 instead of one track

        Raises:
            InvalidParameterError: If the direction is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_direction(direction)

        if by_page:
            self.send(f"/track/bank/page/{direction}", 1)
        else:
            self.send(f"/track/bank/{direction}", 1)

    # Master channel
    def set_master_volume(self, volume: float) -> None:
        """Set the master output volume

        Args:
            volume: Volume value (0-128, where 64 is roughly 0dB)

        Raises:
            InvalidParameterError: If the volume is invalid
            ConnectionError: If unable to send the command
        """
        self.send("/master/volume", self._clamp_value("volume", volume))

    def set_master_pan(self, pan: float) -> None:
        """Set the master output panorama

        Args:
            pan: Pan value (0-128, where 64 is centred)

        Raises:
            InvalidParameterError: If the pan is invalid
            ConnectionError: If unable to send the command
        """
        self.send("/master/pan", self._clamp_value("pan", pan))

    def set_master_mute(self, state: Optional[bool] = None) -> None:
        """Mute or unmute the master output

        Args:
            state: True to mute, False to unmute, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/master/mute", None)
        else:
            self.send("/master/mute", 1 if state else 0)

    # Equalizer
    def add_eq(self) -> None:
        """Add an EQ+ device as the last device on the selected track

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/eq/add", 1)

    def set_eq_band_type(self, band: int, band_type: str) -> None:
        """Set the filter type of an EQ band

        Args:
            band: Band number (1-8)
            band_type: One of off, lowcut, lowshelf, bell, highcut, highshelf,
                notch

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_eq_band(band)

        allowed = (
            "off",
            "lowcut",
            "lowshelf",
            "bell",
            "highcut",
            "highshelf",
            "notch",
        )
        if band_type not in allowed:
            raise InvalidParameterError(
                "band_type", band_type, f"must be one of {', '.join(allowed)}"
            )

        self.send(f"/eq/type/{band}", band_type)

    def set_eq_frequency(self, band: int, value: float) -> None:
        """Set the frequency of an EQ band

        The value is the normalised parameter position (0-128), not a value in
        Hz: OSC exposes EQ bands as generic parameters.

        Args:
            band: Band number (1-8)
            value: Normalised frequency (0-128)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_eq_band(band)
        self.send(f"/eq/freq/{band}", self._clamp_value("value", value))

    def set_eq_gain(self, band: int, value: float) -> None:
        """Set the gain of an EQ band

        Args:
            band: Band number (1-8)
            value: Normalised gain (0-128, where 64 is no change)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_eq_band(band)
        self.send(f"/eq/gain/{band}", self._clamp_value("value", value))

    def set_eq_q(self, band: int, value: float) -> None:
        """Set the Q factor of an EQ band

        Args:
            band: Band number (1-8)
            value: Normalised Q (0-128)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_eq_band(band)
        self.send(f"/eq/q/{band}", self._clamp_value("value", value))

    # Devices
    def duplicate_device(self) -> None:
        """Duplicate the selected device

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/device/duplicate", 1)

    def remove_device(self) -> None:
        """Delete the selected device

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/device/remove", 1)

    def select_device_page(self, page: int) -> None:
        """Select a page of device parameters

        A device exposes its parameters eight at a time, so reaching anything
        past the eighth means selecting the page that holds it.

        Args:
            page: Page number (1-8)

        Raises:
            InvalidParameterError: If the page is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(page, int) or isinstance(page, bool):
            raise InvalidParameterError("page", page, "must be an integer")

        if page < 1 or page > 8:
            raise InvalidParameterError("page", page, "must be 1-8")

        self.send("/device/page/selected", page)

    def navigate_device_page(self, direction: str) -> None:
        """Select the next or previous page of device parameters

        Args:
            direction: "+" for next, "-" for previous

        Raises:
            InvalidParameterError: If the direction is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_direction(direction)
        self.send(f"/device/param/{direction}", 1)

    def reset_device_parameter(self, param_index: int) -> None:
        """Reset a device parameter to its default

        Args:
            param_index: Parameter index (1-8, within the selected page)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(param_index, int) or isinstance(param_index, bool):
            raise InvalidParameterError(
                "param_index", param_index, "must be an integer"
            )

        if param_index < 1 or param_index > 8:
            raise InvalidParameterError("param_index", param_index, "must be 1-8")

        self.send(f"/device/param/{param_index}/reset", 1)

    def set_last_parameter(self, value: float) -> None:
        """Set the value of the most recently touched parameter in Bitwig

        Useful for dialling in whatever the user just clicked on, without
        needing to know which device or page it belongs to.

        Args:
            value: Normalised value (0-128)

        Raises:
            InvalidParameterError: If the value is invalid
            ConnectionError: If unable to send the command
        """
        self.send("/device/lastparam/value", self._clamp_value("value", value))

    def set_drumpad_volume(self, pad: int, volume: float) -> None:
        """Set the volume of a drum pad

        Args:
            pad: Pad number (1-16)
            volume: Volume value (0-128)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_drumpad(pad)
        self.send(f"/device/drumpad/{pad}/volume", self._clamp_value("volume", volume))

    def set_drumpad_pan(self, pad: int, pan: float) -> None:
        """Set the panorama of a drum pad

        Args:
            pad: Pad number (1-16)
            pan: Pan value (0-128, where 64 is centred)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_drumpad(pad)
        self.send(f"/device/drumpad/{pad}/pan", self._clamp_value("pan", pan))

    def set_drumpad_mute(self, pad: int, state: Optional[bool] = None) -> None:
        """Mute or unmute a drum pad

        Args:
            pad: Pad number (1-16)
            state: True to mute, False to unmute, None to toggle

        Raises:
            InvalidParameterError: If the pad is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_drumpad(pad)

        if state is None:
            self.send(f"/device/drumpad/{pad}/mute", None)
        else:
            self.send(f"/device/drumpad/{pad}/mute", 1 if state else 0)

    def set_device_layer_volume(self, layer: int, volume: float) -> None:
        """Set the volume of a device layer

        Args:
            layer: Layer number (1-8)
            volume: Volume value (0-128)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(layer, int) or isinstance(layer, bool):
            raise InvalidParameterError("layer", layer, "must be an integer")

        if layer < 1 or layer > 8:
            raise InvalidParameterError("layer", layer, "must be 1-8")

        self.send(f"/device/layer/{layer}/volume", self._clamp_value("volume", volume))

    # Shared helpers for the above
    def _format_color(self, red: int, green: int, blue: int) -> str:
        """Format an RGB colour the way the protocol expects

        Returns:
            The colour as rgb(r,g,b)

        Raises:
            InvalidParameterError: If any component is out of range
        """
        for label, component in (("red", red), ("green", green), ("blue", blue)):
            if not isinstance(component, int) or isinstance(component, bool):
                raise InvalidParameterError(label, component, "must be an integer")

            if component < 0 or component > 255:
                raise InvalidParameterError(label, component, "must be 0-255")

        return f"rgb({red},{green},{blue})"

    def _clamp_value(self, label: str, value: float) -> float:
        """Clamp a normalised 0-128 parameter value, warning if it was out of range

        Returns:
            The clamped value

        Raises:
            InvalidParameterError: If the value is not a number
        """
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise InvalidParameterError(label, value, "must be a number")

        MAX_VALUE = 128
        MIN_VALUE = 0

        if value < MIN_VALUE:
            logger.warning(f"{label} {value} below minimum ({MIN_VALUE}), clamping")
            return MIN_VALUE

        if value > MAX_VALUE:
            logger.warning(f"{label} {value} above maximum ({MAX_VALUE}), clamping")
            return MAX_VALUE

        return value

    def _validate_send_index(self, send_index: int) -> None:
        """Check a 1-based send index

        Raises:
            InvalidParameterError: If the index is invalid
        """
        if not isinstance(send_index, int) or isinstance(send_index, bool):
            raise InvalidParameterError("send_index", send_index, "must be an integer")

        if send_index < 1 or send_index > 8:
            raise InvalidParameterError("send_index", send_index, "must be 1-8")

    def _validate_eq_band(self, band: int) -> None:
        """Check an EQ band number

        Raises:
            InvalidParameterError: If the band is invalid
        """
        if not isinstance(band, int) or isinstance(band, bool):
            raise InvalidParameterError("band", band, "must be an integer")

        if band < 1 or band > 8:
            raise InvalidParameterError("band", band, "must be 1-8")

    def _validate_drumpad(self, pad: int) -> None:
        """Check a drum pad number

        Raises:
            InvalidParameterError: If the pad is invalid
        """
        if not isinstance(pad, int) or isinstance(pad, bool):
            raise InvalidParameterError("pad", pad, "must be an integer")

        if pad < 1 or pad > 16:
            raise InvalidParameterError("pad", pad, "must be 1-16")

    def _validate_direction(self, direction: str) -> None:
        """Check a +/- navigation direction

        Raises:
            InvalidParameterError: If the direction is invalid
        """
        if direction not in ("+", "-"):
            raise InvalidParameterError("direction", direction, "must be + or -")

    # Scenes
    def create_scene_from_playing(self) -> None:
        """Create a new scene from whatever clips are currently playing

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/scene/create", 1)

    def add_scene(self) -> None:
        """Append an empty scene to the end of the scene list

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/scene/add", 1)

    def select_scene(self, scene_index: int) -> None:
        """Select a scene

        Args:
            scene_index: Scene index (1-based, 1-8 within the visible bank)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_scene_index(scene_index)
        self.send(f"/scene/{scene_index}/select", 1)

    def duplicate_scene(self, scene_index: int) -> None:
        """Duplicate a scene

        Args:
            scene_index: Scene index (1-based, 1-8)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_scene_index(scene_index)
        self.send(f"/scene/{scene_index}/duplicate", 1)

    def remove_scene(self, scene_index: int) -> None:
        """Delete a scene

        Args:
            scene_index: Scene index (1-based, 1-8)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_scene_index(scene_index)
        self.send(f"/scene/{scene_index}/remove", 1)

    def set_scene_name(self, scene_index: int, name: str) -> None:
        """Name a scene

        Scene names are how a song's sections get labelled, for example
        intro, verse or drop.

        Args:
            scene_index: Scene index (1-based, 1-8)
            name: Name to give the scene

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_scene_index(scene_index)

        if not isinstance(name, str):
            raise InvalidParameterError("name", name, "must be a string")

        self.send(f"/scene/{scene_index}/name", name)

    def set_scene_color(
        self, scene_index: int, red: int, green: int, blue: int
    ) -> None:
        """Colour a scene

        Args:
            scene_index: Scene index (1-based, 1-8)
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_scene_index(scene_index)
        self.send(f"/scene/{scene_index}/color", self._format_color(red, green, blue))

    # More clip controls
    def select_clip(self, track_index: int, slot_index: int) -> None:
        """Select a clip, making it the cursor clip

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)
        self.send(f"/track/{track_index}/clip/{slot_index}/select", 1)

    def duplicate_clip(self, track_index: int, slot_index: int) -> None:
        """Duplicate a clip into the next free slot

        Duplicating and then editing is the usual way to build variations of a
        pattern, since OSC cannot edit the notes of an existing clip.

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)
        self.send(f"/track/{track_index}/clip/{slot_index}/duplicate", 1)

    def set_clip_color(
        self, track_index: int, slot_index: int, red: int, green: int, blue: int
    ) -> None:
        """Colour a clip

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)
        self.send(
            f"/track/{track_index}/clip/{slot_index}/color",
            self._format_color(red, green, blue),
        )

    def set_cursor_clip_name(self, name: str) -> None:
        """Name the cursor clip

        Unlike the per-slot name address this is a real received command, but
        it still does not work from OSC alone, verified against DrivenByMoss
        5.2 and Bitwig 6.1.4. Calling select_clip first sets the slot's
        isSelected to 1 while /clip/exists stays 0, so the cursor clip is
        never established and there is nothing to rename. The cursor clip
        appears to follow Bitwig's detail editor, which OSC cannot drive.

        Clip naming therefore has no working route over OSC; name clips by
        hand. Scene naming does work, so label sections with set_scene_name.

        Args:
            name: Name to give the clip

        Raises:
            InvalidParameterError: If the name is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(name, str):
            raise InvalidParameterError("name", name, "must be a string")

        self.send("/clip/name", name)

    def stop_track_clips(self, track_index: int) -> None:
        """Stop the playing clip on a track

        Args:
            track_index: Track index (1-based)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self.send(f"/track/{track_index}/clip/stop", 1)

    def stop_all_clips(self) -> None:
        """Stop every playing clip

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/clip/stopall", 1)

    def return_to_arrangement(self, track_index: int) -> None:
        """Hand a track's playback back to the arrangement

        Args:
            track_index: Track index (1-based)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self.send(f"/track/{track_index}/clip/returntoarrangement", 1)

    def insert_file_into_clip(
        self, track_index: int, slot_index: int, filepath: str
    ) -> None:
        """Load an audio or MIDI file into a clip slot

        This is the only route for getting sample content into a project over
        OSC.

        Args:
            track_index: Track index (1-based)
            slot_index: Clip slot index (1-based, 1-8)
            filepath: Absolute path to the file

        Raises:
            InvalidParameterError: If parameters are invalid
            ConnectionError: If unable to send the command
        """
        self._validate_track_index(track_index)
        self._validate_slot_index(slot_index)

        if not isinstance(filepath, str) or not filepath:
            raise InvalidParameterError(
                "filepath", filepath, "must be a non-empty string"
            )

        self.send(f"/track/{track_index}/clip/{slot_index}/insertFile", filepath)

    # More transport controls
    def restart(self) -> None:
        """Restart playback from the start of the timeline

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/restart", 1)

    def set_repeat(self, state: Optional[bool] = None) -> None:
        """Set the arrangement loop

        Args:
            state: True to loop, False to stop looping, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/repeat", None)
        else:
            self.send("/repeat", 1 if state else 0)

    def set_click_volume(self, volume: float) -> None:
        """Set the metronome volume

        Args:
            volume: Volume value (0-128)

        Raises:
            InvalidParameterError: If the volume is invalid
            ConnectionError: If unable to send the command
        """
        self.send("/click/volume", self._clamp_value("volume", volume))

    def set_preroll(self, bars: int) -> None:
        """Set how many bars of count-in precede recording

        Args:
            bars: One of 0, 1, 2 or 4

        Raises:
            InvalidParameterError: If bars is invalid
            ConnectionError: If unable to send the command
        """
        if bars not in (0, 1, 2, 4):
            raise InvalidParameterError("bars", bars, "must be 0, 1, 2 or 4")

        self.send("/preroll", bars)

    def set_punch_in(self, state: Optional[bool] = None) -> None:
        """Set punch in

        Args:
            state: True to enable, False to disable, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/punchIn", None)
        else:
            self.send("/punchIn", 1 if state else 0)

    def set_punch_out(self, state: Optional[bool] = None) -> None:
        """Set punch out

        Args:
            state: True to enable, False to disable, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/punchOut", None)
        else:
            self.send("/punchOut", 1 if state else 0)

    def toggle_launcher_overdub(self) -> None:
        """Toggle clip launcher overdub

        The protocol only offers a toggle for this one, unlike arranger
        overdub which set_overdub handles.

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/overdub/launcher", 1)

    def tap_tempo(self) -> None:
        """Tap the tempo once

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/tempo/tap", 1)

    def nudge_tempo(self, direction: str) -> None:
        """Move the tempo by one BPM

        Args:
            direction: "+" to speed up, "-" to slow down

        Raises:
            InvalidParameterError: If the direction is invalid
            ConnectionError: If unable to send the command
        """
        self._validate_direction(direction)
        self.send(f"/tempo/{direction}", 1)

    def set_launcher_quantization(self, value: str) -> None:
        """Set the default clip launcher quantization

        This decides how long a launched clip waits before it starts, which is
        what keeps scene changes musically in time.

        Args:
            value: One of none, 1, 2, 4, 8, 1/2, 1/4, 1/8, 1/16

        Raises:
            InvalidParameterError: If the value is invalid
            ConnectionError: If unable to send the command
        """
        allowed = ("none", "1", "2", "4", "8", "1/2", "1/4", "1/8", "1/16")
        if str(value) not in allowed:
            raise InvalidParameterError(
                "value", value, f"must be one of {', '.join(allowed)}"
            )

        self.send("/launcher/defaultQuantization", str(value))

    # Automation
    def toggle_arranger_automation_write(self) -> None:
        """Toggle automation write in the arranger

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/autowrite", 1)

    def toggle_launcher_automation_write(self) -> None:
        """Toggle automation write in the clip launcher

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/autowrite/launcher", 1)

    def set_automation_write_mode(self, mode: str) -> None:
        """Set how automation is written

        Args:
            mode: One of latch, touch or write

        Raises:
            InvalidParameterError: If the mode is invalid
            ConnectionError: If unable to send the command
        """
        allowed = ("latch", "touch", "write")
        if mode not in allowed:
            raise InvalidParameterError(
                "mode", mode, f"must be one of {', '.join(allowed)}"
            )

        self.send("/automationWriteMode", mode)

    # Project
    def save_project(self) -> None:
        """Save the current project

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/project/save", 1)

    def undo(self) -> None:
        """Undo the last action

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/undo", 1)

    def redo(self) -> None:
        """Redo the last undone action

        Raises:
            ConnectionError: If unable to send the command
        """
        self.send("/redo", 1)

    def set_audio_engine(self, state: Optional[bool] = None) -> None:
        """Turn the audio engine on or off

        Args:
            state: True to activate, False to deactivate, None to toggle

        Raises:
            ConnectionError: If unable to send the command
        """
        if state is None:
            self.send("/project/engine", None)
        else:
            self.send("/project/engine", 1 if state else 0)

    def launch_marker(self, marker_index: int) -> None:
        """Start playback from a cue marker

        Args:
            marker_index: Marker index (1-based, 1-8)

        Raises:
            InvalidParameterError: If the index is invalid
            ConnectionError: If unable to send the command
        """
        if not isinstance(marker_index, int) or isinstance(marker_index, bool):
            raise InvalidParameterError(
                "marker_index", marker_index, "must be an integer"
            )

        if marker_index < 1 or marker_index > 8:
            raise InvalidParameterError("marker_index", marker_index, "must be 1-8")

        self.send(f"/marker/{marker_index}/launch", 1)

    def _validate_scene_index(self, scene_index: int) -> None:
        """Check a 1-based scene index within the visible bank

        Raises:
            InvalidParameterError: If the index is invalid
        """
        if not isinstance(scene_index, int) or isinstance(scene_index, bool):
            raise InvalidParameterError(
                "scene_index", scene_index, "must be an integer"
            )

        if scene_index < 1 or scene_index > 8:
            raise InvalidParameterError("scene_index", scene_index, "must be 1-8")

    def get_status(self) -> Dict[str, Any]:
        """Get client status information

        Returns:
            Dict with status information
        """
        return {
            "ip": self.ip,
            "port": self.port,
            "messages_sent": len(self.addr_log),
            "last_addresses": self.addr_log[-5:] if self.addr_log else [],
        }
