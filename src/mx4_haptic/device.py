"""Convenience object combining global mouse events and MX4 haptics."""

from __future__ import annotations

from .events import ButtonCallback, MouseEvents, ScrollCallback
from .haptics import HapticController


class MXMaster4(MouseEvents):
    """Listen for macOS mouse events and trigger the MX Master 4 actuator.

    Mouse events are supplied by macOS and are not filtered to this device.
    Haptic commands are sent directly to the MX Master 4 over HID++.
    """

    def __init__(
        self,
        on_button: ButtonCallback | None = None,
        on_scroll: ScrollCallback | None = None,
        *,
        suppress: bool = False,
    ) -> None:
        super().__init__(on_button, on_scroll, suppress=suppress)
        self.haptics = HapticController()

    def close(self) -> None:
        """Stop mouse events and close the HID++ connection, if it was opened."""
        self.stop()
        self.haptics.close()

    def __exit__(self, *_: object) -> None:
        self.close()
        self.join()
