# mx4-haptic

Python mouse events and direct HID++ haptic control for the Logitech MX Master 4 on macOS. It does not use Logi Options+.

## Install

```bash
python -m pip install mx4-haptic
```

Python 3.10 or newer is required. The package installs `pynput` for mouse events and `hidapi` on macOS for haptics.

## Mouse buttons and scroll

`MouseEvents` reports the mouse events macOS makes available to the process. Events are global, and the library does not suppress them by default.

```python
from mx4_haptic import MXMaster4


def on_button(event):
    print(event.phase, event.button, event.x, event.y)


def on_scroll(event):
    print(event.axis, event.dx, event.dy)


with MXMaster4(on_button=on_button, on_scroll=on_scroll) as mx4:
    mx4.join()  # Run until the listener is stopped or the process exits.
```

`event.phase` is `"down"` or `"up"`. `event.button` is the button name reported by macOS, such as `left`, `right`, `middle`, `x1`, or `x2`. Scroll events carry raw `dx` and `dy` deltas; `event.axis` is `horizontal`, `vertical`, `both`, or `none`. macOS does not identify which physical wheel produced a delta, and Natural Scrolling can affect its sign.

The listener needs macOS Input Monitoring or Accessibility permission. These are OS-level events: a hardware control is available only if macOS exposes it as a mouse event. Raw HID++ button diversion is not included yet.

To listen without writing code:

```bash
mx4-haptic listen
```

## Haptics

Haptic requests go directly to the mouse's HID++ feature `0x19B0`. The current implementation supports a directly connected MX Master 4 over Bluetooth. It discovers waveform support and refuses to play an ID the device does not advertise.

```python
from mx4_haptic import HapticController, Waveform


with HapticController() as haptics:
    print(haptics.get_state())
    print(haptics.get_supported_waveforms())
    haptics.play(Waveform.KNOCK)
    haptics.set_level(45)  # Writes the intensity to the mouse.
```

Playback does not change the mouse configuration. `set_level()` is an explicit, persistent device setting change and preserves the other configuration flags.

```bash
mx4-haptic haptics status
mx4-haptic haptics play KNOCK
mx4-haptic haptics level 45
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check src tests
pytest
python -m build
python -m twine check dist/*
```

The tests do not require a mouse. Physical event delivery and haptic feedback require an MX Master 4 and macOS permissions.

## Release and PyPI publishing

GitHub Actions runs lint, hardware-free tests, and package build checks. Publishing runs only when a GitHub Release is published. It uses PyPI Trusted Publishing (OIDC); no long-lived PyPI API token is stored in GitHub.

Before the first release, add a pending Trusted Publisher in your PyPI account. PyPI can create the project automatically on the first successful publish; a pending publisher does not reserve the name until then. Follow the [PyPI setup guide](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) and enter:

- Project name: `mx4-haptic`
- Owner: `paveleu`
- Repository: `mx4-haptic`
- Workflow: `publish.yml`
- Environment: `pypi`

Then update the version in `pyproject.toml`, push the commit, and publish a GitHub Release for the matching tag, for example `v0.1.0`. The release workflow builds and checks the package, then publishes the built files to PyPI.

## License

MIT. See [LICENSE](LICENSE).
