"""Mouse events and haptic feedback for the Logitech MX Master 4."""

from .device import MXMaster4
from .events import ButtonEvent, MouseEvents, ScrollEvent
from .haptics import (
    DeviceNotFoundError,
    HapticController,
    HapticError,
    HapticState,
    MX4Error,
    Waveform,
)

__all__ = [
    "ButtonEvent",
    "DeviceNotFoundError",
    "HapticController",
    "HapticError",
    "HapticState",
    "MX4Error",
    "MXMaster4",
    "MouseEvents",
    "ScrollEvent",
    "Waveform",
]

__version__ = "0.1.2"
