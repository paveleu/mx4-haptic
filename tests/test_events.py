import sys
from types import SimpleNamespace

import pytest

from mx4_haptic import MouseEvents
from mx4_haptic.events import ButtonEvent, ScrollEvent


@pytest.fixture
def mouse_backend(monkeypatch):
    class Listener:
        def __init__(self, *, on_click, on_scroll, suppress):
            self.on_click = lambda x, y, button, pressed, *extra: on_click(x, y, button, pressed)
            self.on_scroll = on_scroll
            self.suppress = suppress
            self.started = False
            self.ready = False
            self.stopped = False
            self.joined = False

        def start(self):
            self.started = True

        def wait(self):
            assert self.started
            self.ready = True

        def stop(self):
            # Like pynput, stop() does nothing until the listener thread starts running.
            if self.ready:
                self.stopped = True

        def join(self, timeout=None):
            assert self.stopped, "joining an unstopped listener would block"
            self.joined = True

        def is_alive(self):
            return self.started and not self.stopped

        def _handle_message(self, proxy, event_type, event, refcon, *extra):
            name = "middle" if event_type in (25, 26) else "left"
            self.on_click(*event.position, SimpleNamespace(name=name), event_type != 26, *extra)

    quartz = SimpleNamespace(
        kCGEventOtherMouseDown=25,
        kCGEventOtherMouseUp=26,
        kCGMouseEventButtonNumber=3,
        CGEventGetLocation=lambda event: event.position,
        CGEventGetIntegerValueField=lambda event, field: event.number,
    )
    monkeypatch.setitem(
        sys.modules, "pynput", SimpleNamespace(mouse=SimpleNamespace(Listener=Listener))
    )
    monkeypatch.setitem(sys.modules, "Quartz", quartz)
    monkeypatch.setattr(sys, "platform", "darwin")
    return Listener


def test_button_event_phase():
    assert ButtonEvent(10, 20, "x1", True).phase == "down"
    assert ButtonEvent(10, 20, "x1", False).phase == "up"


def test_scroll_event_axis():
    assert ScrollEvent(0, 0, 1, 0).axis == "horizontal"
    assert ScrollEvent(0, 0, 0, -1).axis == "vertical"
    assert ScrollEvent(0, 0, 1, -1).axis == "both"
    assert ScrollEvent(0, 0, 0, 0).axis == "none"


@pytest.mark.parametrize("number, name", [(2, "middle"), (3, "x1"), (4, "x2"), (5, "button_5")])
@pytest.mark.parametrize("event_type, pressed", [(25, True), (26, False)])
@pytest.mark.parametrize("extra", [(), (False,)])
def test_macos_preserves_button_number(mouse_backend, number, name, event_type, pressed, extra):
    buttons = []
    with MouseEvents(on_button=buttons.append) as events:
        raw_event = SimpleNamespace(position=(10, 20), number=number)
        events._listener._handle_message(None, event_type, raw_event, None, *extra)

    assert buttons == [ButtonEvent(10, 20, name, pressed)]


def test_macos_preserves_standard_callbacks_and_suppression(mouse_backend):
    buttons, scrolls = [], []
    with MouseEvents(buttons.append, scrolls.append, suppress=True) as events:
        raw_event = SimpleNamespace(position=(10, 20), number=0)
        events._listener._handle_message(None, 1, raw_event, None, False)
        events._listener.on_scroll(10, 20, -1, 2)
        assert events._listener.suppress is True

    assert buttons == [ButtonEvent(10, 20, "left", True)]
    assert scrolls == [ScrollEvent(10, 20, -1, 2)]


def test_context_can_stop_immediately_after_start(mouse_backend):
    with MouseEvents() as events:
        listener = events._listener
        assert events.start() is events
        assert events._listener is listener

    assert not events.is_alive
    assert listener.joined


def test_other_platforms_use_the_original_listener(mouse_backend, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    buttons = []
    with MouseEvents(on_button=buttons.append) as events:
        assert type(events._listener) is mouse_backend
        events._listener.on_click(10, 20, "Button.x1", False)

    assert buttons == [ButtonEvent(10, 20, "x1", False)]
