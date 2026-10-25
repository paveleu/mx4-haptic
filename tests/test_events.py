from mx4_haptic.events import ButtonEvent, ScrollEvent


def test_button_event_phase():
    assert ButtonEvent(10, 20, "x1", True).phase == "down"
    assert ButtonEvent(10, 20, "x1", False).phase == "up"


def test_scroll_event_axis():
    assert ScrollEvent(0, 0, 1, 0).axis == "horizontal"
    assert ScrollEvent(0, 0, 0, -1).axis == "vertical"
    assert ScrollEvent(0, 0, 1, -1).axis == "both"
    assert ScrollEvent(0, 0, 0, 0).axis == "none"
