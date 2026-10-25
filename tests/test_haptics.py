import pytest

from mx4_haptic.haptics import (
    HIDPP_LONG_LENGTH,
    HapticController,
    HapticError,
    Waveform,
    _resolve_waveform,
)


class FakeHID:
    def __init__(self, response):
        self.response = response
        self.written = None

    def write(self, packet):
        self.written = packet
        return len(packet)

    def read(self, _size, _timeout):
        response, self.response = self.response, []
        return response


def test_resolve_waveform_name_id_and_hex():
    assert _resolve_waveform(Waveform.KNOCK) == 12
    assert _resolve_waveform("subtle-collision") == 4
    assert _resolve_waveform("0x0c") == 12
    assert _resolve_waveform(5) == 5


@pytest.mark.parametrize("value", [-1, 32, "unknown-waveform"])
def test_resolve_waveform_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        _resolve_waveform(value)


def test_hidpp_request_writes_long_report_and_matches_reply():
    response = [0x11, 0xFF, 0x0B, 0x41, 0x01, *([0] * 15)]
    device = FakeHID(response)
    controller = HapticController(timeout=0.01)

    result = controller._request_on(device, 0xFF, 0x0B, 4, [12, 0, 0])

    assert len(device.written) == HIDPP_LONG_LENGTH
    assert device.written[:7] == [0x11, 0xFF, 0x0B, 0x41, 12, 0, 0]
    assert result[:3] == [0x01, 0, 0]


def test_hidpp_request_surfaces_device_error():
    device = FakeHID([0x11, 0xFF, 0xFF, 0x81, 0, 0x05, 0])
    controller = HapticController(timeout=0.01)

    with pytest.raises(HapticError, match="0x05"):
        controller._request_on(device, 0xFF, 0x0B, 0, [])
