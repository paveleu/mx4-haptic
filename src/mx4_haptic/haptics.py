"""Direct HID++ haptic controls for the Logitech MX Master 4."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

LOGITECH_VID = 0x046D
MX_MASTER_4_PID = 0xB042
HIDPP_USAGE_PAGE_MIN = 0xFF00

# HID++ long reports have a fixed width; 0xFF addresses the direct Bluetooth connection.
HIDPP_LONG_REPORT = 0x11
HIDPP_LONG_LENGTH = 20
DIRECT_BLUETOOTH_DEVICE_INDEX = 0xFF
SOFTWARE_ID = 0x01
FEATURE_ROOT = 0x0000
FEATURE_HAPTIC = 0x19B0


class Waveform(IntEnum):
    """Known MX Master 4 waveform IDs. Check device support before playback."""

    SHARP_STATE_CHANGE = 0
    DAMP_STATE_CHANGE = 1
    SHARP_COLLISION = 2
    DAMP_COLLISION = 3
    SUBTLE_COLLISION = 4
    HAPPY_ALERT = 5
    ANGRY_ALERT = 6
    COMPLETED = 7
    SQUARE = 8
    WAVE = 9
    FIREWORK = 10
    MAD = 11
    KNOCK = 12
    JINGLE = 13
    RINGING = 14
    WHISPER_COLLISION = 27


class MX4Error(RuntimeError):
    """Base error raised by this library."""


class HapticError(MX4Error):
    """HID++ communication or haptic actuator error."""


class DeviceNotFoundError(HapticError):
    """No directly connected MX Master 4 HID++ interface was found."""


@dataclass(frozen=True, slots=True)
class HapticState:
    """Current device haptics configuration."""

    enabled: bool
    level: int
    flags: int


def _resolve_waveform(waveform: Waveform | int | str) -> int:
    if isinstance(waveform, Waveform):
        return int(waveform)
    if isinstance(waveform, int):
        wave_id = waveform
    elif isinstance(waveform, str):
        try:
            return int(Waveform[waveform.strip().replace("-", "_").replace(" ", "_").upper()])
        except KeyError:
            try:
                wave_id = int(waveform, 0)
            except ValueError:
                raise ValueError(f"Unknown haptic waveform: {waveform!r}") from None
    else:
        raise TypeError("waveform must be a Waveform, integer ID, or name")
    if not 0 <= wave_id <= 31:
        raise ValueError("waveform ID must be between 0 and 31")
    return wave_id


class HapticController:
    """Read and control the MX Master 4 actuator over direct Bluetooth HID++.

    The HID connection is opened lazily and stays open until :meth:`close`.
    No Logi Options+ process is used. Configuration writes happen only when
    :meth:`set_level` is explicitly called.
    """

    def __init__(self, *, timeout: float = 1.5) -> None:
        self.timeout = timeout
        self._device: Any | None = None
        self._feature_index: int | None = None
        self._lock = threading.RLock()

    def connect(self) -> HapticController:
        """Open the MX4 HID++ interface and discover its haptics feature."""
        with self._lock:
            self._ensure_connected()
        return self

    def _ensure_connected(self) -> None:
        if self._device is not None and self._feature_index is not None:
            return

        try:
            import hid
        except ImportError as exc:
            raise HapticError(
                "Install the macOS HID dependency with `pip install mx4-haptic`."
            ) from exc

        interfaces = [
            info
            for info in hid.enumerate(LOGITECH_VID, MX_MASTER_4_PID)
            if int(info.get("usage_page", 0) or 0) >= HIDPP_USAGE_PAGE_MIN
        ]
        if not interfaces:
            raise DeviceNotFoundError(
                "No MX Master 4 HID++ interface found. Connect it directly over Bluetooth."
            )

        last_error: Exception | None = None
        for info in interfaces:
            device = hid.device()
            try:
                device.open_path(info["path"])
                # Feature Root resolves the haptics feature ID to this device's feature index.
                response = self._request_on(
                    device,
                    DIRECT_BLUETOOTH_DEVICE_INDEX,
                    FEATURE_ROOT,
                    0,
                    [(FEATURE_HAPTIC >> 8) & 0xFF, FEATURE_HAPTIC & 0xFF, 0],
                )
                feature_index = response[0] if response else 0
                if feature_index == 0:
                    raise HapticError("MX Master 4 does not advertise HID++ haptics (0x19B0).")
                self._device = device
                self._feature_index = feature_index
                return
            except Exception as exc:
                last_error = exc
                try:
                    device.close()
                except Exception:
                    pass

        if isinstance(last_error, HapticError):
            raise last_error
        raise HapticError(f"Could not open the MX Master 4 HID++ interface: {last_error}")

    def _request_on(
        self,
        device: Any,
        device_index: int,
        feature_index: int,
        function: int,
        params: list[int] | None = None,
    ) -> list[int]:
        params = params or []
        # The header byte packs the function in its upper nibble and this client's ID below.
        packet = [
            HIDPP_LONG_REPORT,
            device_index,
            feature_index,
            ((function & 0x0F) << 4) | SOFTWARE_ID,
            *[value & 0xFF for value in params[: HIDPP_LONG_LENGTH - 4]],
        ]
        # Pad the payload so every write is a complete 20-byte HID++ long report.
        packet.extend([0] * (HIDPP_LONG_LENGTH - len(packet)))
        if device.write(packet) <= 0:
            raise HapticError("macOS did not accept the HID++ report.")

        deadline = time.monotonic() + self.timeout
        expected_functions = {function & 0x0F, (function + 1) & 0x0F}
        while time.monotonic() < deadline:
            remaining_ms = max(1, min(400, int((deadline - time.monotonic()) * 1000)))
            raw = device.read(64, remaining_ms)
            if not raw or len(raw) < 7:
                continue

            report = list(raw)
            reply_device = report[1]
            # Some Bluetooth replies identify the device as slot 0 instead of the 0xFF address.
            is_our_device = reply_device == device_index or (
                device_index == DIRECT_BLUETOOTH_DEVICE_INDEX and reply_device == 0
            )
            if not is_our_device:
                continue

            reply_feature = report[2]
            reply_address = report[3]
            reply_function = reply_address >> 4
            reply_software_id = reply_address & 0x0F
            if reply_feature == 0xFF:
                code = report[5] if len(report) > 5 else 0
                raise HapticError(f"Device returned HID++ error 0x{code:02X}.")

            if (
                reply_feature == feature_index
                and reply_software_id == SOFTWARE_ID
                and reply_function in expected_functions
            ):
                return report[4:]

        raise HapticError(
            f"No HID++ response for feature 0x{feature_index:02X}, function {function}."
        )

    def _request(self, function: int, params: list[int] | None = None) -> list[int]:
        self._ensure_connected()
        assert self._device is not None and self._feature_index is not None
        return self._request_on(
            self._device,
            DIRECT_BLUETOOTH_DEVICE_INDEX,
            self._feature_index,
            function,
            params,
        )

    def get_state(self) -> HapticState:
        """Read whether haptics are enabled and the current intensity (0–100)."""
        with self._lock:
            response = self._request(1)
            if len(response) < 2:
                raise HapticError("The haptic configuration response was too short.")
            flags, level = response[0], response[1]
            return HapticState(bool(flags & 0x01), level, flags)

    def get_supported_waveforms(self) -> tuple[Waveform | int, ...]:
        """Return waveform IDs advertised by the connected mouse."""
        with self._lock:
            response = self._request(0)
            if len(response) < 8:
                raise HapticError("The haptic capability response was too short.")
            # Each bit in this big-endian bitmap advertises support for the matching waveform ID.
            mask = int.from_bytes(bytes(response[4:8]), "big")
            supported: list[Waveform | int] = []
            for wave_id in range(32):
                if mask & (1 << wave_id):
                    try:
                        supported.append(Waveform(wave_id))
                    except ValueError:
                        supported.append(wave_id)
            return tuple(supported)

    def play(self, waveform: Waveform | int | str) -> None:
        """Play one supported haptic waveform without changing device settings."""
        wave_id = _resolve_waveform(waveform)
        with self._lock:
            supported = self.get_supported_waveforms()
            if wave_id not in {int(item) for item in supported}:
                raise HapticError(f"The mouse does not advertise waveform ID {wave_id}.")
            if not self.get_state().enabled:
                raise HapticError("Haptics are disabled in the mouse configuration.")
            # Confirm the actuator is idle before sending the waveform trigger.
            status = self._request(3)
            if not status or status[0] != 0:
                raw_status = status[0] if status else "missing"
                raise HapticError(f"The haptic actuator is not ready (status {raw_status}).")
            self._request(4, [wave_id, 0, 0])

    def set_level(self, level: int) -> HapticState:
        """Write and verify the persistent device intensity (0–100).

        The existing configuration flags are preserved. A level of zero may
        make the haptic actuator imperceptible.
        """
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 100:
            raise ValueError("level must be an integer between 0 and 100")
        with self._lock:
            current = self.get_state()
            # Keep enable/mode flags intact while changing only the intensity byte.
            response = self._request(2, [current.flags, level, 0])
            if len(response) < 2 or response[1] != level:
                actual = response[1] if len(response) >= 2 else "missing"
                raise HapticError(f"The mouse did not confirm level {level}; read back {actual}.")
            return HapticState(bool(response[0] & 0x01), response[1], response[0])

    def close(self) -> None:
        """Close the HID++ connection if one is open."""
        with self._lock:
            if self._device is not None:
                self._device.close()
            self._device = None
            self._feature_index = None

    def __enter__(self) -> HapticController:
        return self.connect()

    def __exit__(self, *_: object) -> None:
        self.close()
