import pytest

from mx4_haptic.cli import main
from mx4_haptic.haptics import (
    HIDPP_LONG_LENGTH,
    HapticController,
    HapticError,
    Waveform,
    _resolve_waveform,
)


class FakeHID:
    def __init__(self, response, *more_responses):
        self.responses = [response, *more_responses]
        self.written = None
        self.closed = False

    def write(self, packet):
        self.written = packet
        return len(packet)

    def read(self, _size, _timeout):
        return self.responses.pop(0) if self.responses else []

    def close(self):
        self.closed = True


def reply(function, payload, *, device_index=0xFF):
    return [0x11, device_index, 0x0B, (function << 4) | 1, *payload, *([0] * (16 - len(payload)))]


def connected_controller(device):
    controller = HapticController(timeout=0.01)
    controller._device = device
    controller._feature_index = 0x0B
    return controller


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
    # Model a long-report response for feature 0x0B and the function-4 waveform trigger.
    response = [0x11, 0xFF, 0x0B, 0x41, 0x01, *([0] * 15)]
    device = FakeHID(response)
    controller = HapticController(timeout=0.01)

    result = controller._request_on(device, 0xFF, 0x0B, 4, [12, 0, 0])

    assert len(device.written) == HIDPP_LONG_LENGTH
    assert device.written[:7] == [0x11, 0xFF, 0x0B, 0x41, 12, 0, 0]
    assert result[:3] == [0x01, 0, 0]


def test_hidpp_request_surfaces_device_error():
    # Error reports echo the requested feature and complete function/software address.
    device = FakeHID([0x11, 0xFF, 0xFF, 0x0B, 0x01, 0x05, 0])
    controller = HapticController(timeout=0.01)

    with pytest.raises(HapticError, match="0x05"):
        controller._request_on(device, 0xFF, 0x0B, 0, [])


def test_play_ignores_a_late_configuration_after_a_timeout():
    device = FakeHID([])
    controller = connected_controller(device)
    with pytest.raises(HapticError, match="No HID\\+\\+ response"):
        controller.get_state()

    device.responses = [
        reply(1, [1, 45]),  # The timed-out configuration arrives before the capabilities.
        reply(0, [0, 0, 0, 0, 0, 0, 0x10, 0]),
        reply(1, [1, 45]),
        reply(3, [0]),
        reply(4, [12]),
    ]
    controller.play(Waveform.KNOCK)

    assert not device.responses
    assert device.written[:7] == [0x11, 0xFF, 0x0B, 0x41, 12, 0, 0]


@pytest.mark.parametrize("device_index", [0xFF, 0])
def test_hidpp_request_accepts_bluetooth_device_aliases(device_index):
    controller = connected_controller(FakeHID(reply(1, [1, 45], device_index=device_index)))

    assert controller.get_state().level == 45


@pytest.mark.parametrize("feature, address", [(0x7A, 0x11), (0x0B, 0x21), (0x0B, 0x12)])
def test_hidpp_request_ignores_errors_for_other_requests(feature, address):
    unrelated_error = [0x11, 0xFF, 0xFF, feature, address, 0x07, 0]
    device = FakeHID(unrelated_error, reply(1, [1, 45]))
    controller = connected_controller(device)

    assert controller.get_state().level == 45
    assert not device.responses


@pytest.mark.parametrize("operation", ["read", "write"])
def test_hidpp_transport_errors_use_the_library_exception(monkeypatch, operation):
    device = FakeHID([])
    failure = OSError("device disconnected")

    def fail(*args):
        raise failure

    monkeypatch.setattr(device, operation, fail)
    controller = connected_controller(device)

    with pytest.raises(HapticError, match="device disconnected") as error:
        controller.get_state()

    assert error.value.__cause__ is failure


def test_cli_reports_a_read_failure_without_a_traceback(monkeypatch, capsys):
    device = FakeHID([])

    def fail(*args):
        raise OSError("read error")

    monkeypatch.setattr(device, "read", fail)
    monkeypatch.setattr("mx4_haptic.cli.HapticController", lambda: connected_controller(device))

    assert main(["haptics", "status"]) == 1
    assert "read error" in capsys.readouterr().err
    assert device.closed
