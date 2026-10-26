"""OS-level mouse button and scroll events delivered by macOS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ButtonEvent:
    """A mouse button press or release reported by the operating system."""

    x: float
    y: float
    button: str
    pressed: bool

    @property
    def phase(self) -> str:
        """Return ``"down"`` for a press and ``"up"`` for a release."""
        return "down" if self.pressed else "up"


@dataclass(frozen=True, slots=True)
class ScrollEvent:
    """A scroll delta reported by the operating system."""

    x: float
    y: float
    dx: float
    dy: float

    @property
    def axis(self) -> str:
        """Classify the event by axis; macOS does not identify the physical wheel."""
        if self.dx and self.dy:
            return "both"
        if self.dx:
            return "horizontal"
        if self.dy:
            return "vertical"
        return "none"


ButtonCallback = Callable[[ButtonEvent], None]
ScrollCallback = Callable[[ScrollEvent], None]


class MouseEvents:
    """Listen for system mouse clicks and scroll deltas.

    On macOS, grant the Python process Input Monitoring or Accessibility
    permission if the listener receives no events. The callbacks run on the
    listener thread. ``suppress`` defaults to false so events continue to the
    foreground application.
    """

    def __init__(
        self,
        on_button: ButtonCallback | None = None,
        on_scroll: ScrollCallback | None = None,
        *,
        suppress: bool = False,
    ) -> None:
        self.on_button = on_button
        self.on_scroll = on_scroll
        self.suppress = suppress
        self._listener = None

    def start(self) -> MouseEvents:
        """Start listening in the background and return this listener."""
        if self._listener is not None and self._listener.is_alive():
            return self

        try:
            from pynput import mouse
        except ImportError as exc:
            raise RuntimeError("Mouse event listening requires the 'pynput' package.") from exc

        def on_click(x: float, y: float, button: object, pressed: bool) -> None:
            if self.on_button is None:
                return

            # Expose plain button names instead of leaking pynput's enum type to callers.
            name = getattr(button, "name", None)
            if name is None:
                name = str(button).removeprefix("Button.")
            self.on_button(ButtonEvent(float(x), float(y), str(name), bool(pressed)))

        def on_scroll(x: float, y: float, dx: float, dy: float) -> None:
            if self.on_scroll is not None:
                # The OS provides deltas, but does not identify which physical wheel moved.
                self.on_scroll(ScrollEvent(float(x), float(y), float(dx), float(dy)))

        self._listener = mouse.Listener(
            on_click=on_click,
            on_scroll=on_scroll,
            suppress=self.suppress,
        )
        self._listener.start()
        return self

    def stop(self) -> None:
        """Stop listening. Safe to call more than once."""
        if self._listener is not None:
            self._listener.stop()

    def join(self, timeout: float | None = None) -> None:
        """Wait for the listener thread to finish."""
        if self._listener is not None:
            self._listener.join(timeout)

    @property
    def is_alive(self) -> bool:
        """Whether the listener thread is running."""
        return self._listener is not None and self._listener.is_alive()

    def __enter__(self) -> MouseEvents:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()
        self.join()
