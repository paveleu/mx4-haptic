"""Command-line utilities for MX Master 4 events and haptics."""

from __future__ import annotations

import argparse
import sys

from .events import MouseEvents
from .haptics import HapticController, HapticError, Waveform, _resolve_waveform


def _print_supported(controller: HapticController) -> None:
    supported = controller.get_supported_waveforms()
    print("Supported waveforms:")
    for waveform in supported:
        try:
            known = Waveform(int(waveform))
            print(f"  {int(known):2}: {known.name}")
        except ValueError:
            print(f"  {waveform:2}: UNKNOWN")


def _haptics_command(args: argparse.Namespace) -> int:
    controller = HapticController()
    try:
        if args.haptic_command == "status":
            state = controller.get_state()
            print(f"Haptics: {'enabled' if state.enabled else 'disabled'}; level {state.level}/100")
            _print_supported(controller)
        elif args.haptic_command == "play":
            waveform = _resolve_waveform(args.waveform)
            controller.play(waveform)
            try:
                name = Waveform(waveform).name
            except ValueError:
                name = "unknown"
            print(f"Played waveform {waveform} ({name}).")
        elif args.haptic_command == "level":
            state = controller.set_level(args.level)
            print(f"Haptics: {'enabled' if state.enabled else 'disabled'}; level {state.level}/100")
        return 0
    except (HapticError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        controller.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mouse input and haptics for Logitech MX Master 4")
    commands = parser.add_subparsers(dest="command", required=True)

    listen = commands.add_parser(
        "listen", help="listen for macOS mouse button and scroll events"
    )
    listen.add_argument(
        "--suppress",
        action="store_true",
        help="block events from reaching other apps",
    )

    haptics = commands.add_parser("haptics", help="read or control MX Master 4 haptics")
    haptic_commands = haptics.add_subparsers(dest="haptic_command", required=True)
    haptic_commands.add_parser("status", help="show state and supported waveforms")
    play = haptic_commands.add_parser("play", help="play one waveform by ID or name")
    play.add_argument("waveform", help="waveform ID or name such as KNOCK")
    level = haptic_commands.add_parser("level", help="set persistent haptic intensity (0–100)")
    level.add_argument("level", type=int)

    args = parser.parse_args(argv)
    if args.command == "haptics":
        if args.haptic_command == "level" and not 0 <= args.level <= 100:
            parser.error("haptic level must be between 0 and 100")
        return _haptics_command(args)

    def on_button(event) -> None:
        print(
            f"button {event.phase}: {event.button} at ({event.x:.1f}, {event.y:.1f})",
            flush=True,
        )

    def on_scroll(event) -> None:
        print(
            f"scroll {event.axis}: dx={event.dx:+g} dy={event.dy:+g} "
            f"at ({event.x:.1f}, {event.y:.1f})",
            flush=True,
        )

    listener = MouseEvents(on_button, on_scroll, suppress=args.suppress)
    print("Listening for macOS mouse events. Press Ctrl+C to stop.")
    try:
        listener.start().join()
    except KeyboardInterrupt:
        listener.stop()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
