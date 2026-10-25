#!/usr/bin/env python3
"""List Logitech HID interfaces and optionally watch macOS mouse events."""

from __future__ import annotations

import argparse
import sys

from mx4_haptic.events import MouseEvents

LOGITECH_VID = 0x046D


def list_devices() -> None:
    import hid

    devices = hid.enumerate(LOGITECH_VID, 0)
    if not devices:
        print("Nie znaleziono teraz interfejsów HID Logitech (VID 046D).")
        print("Sprawdź, czy MX Master 4 jest włączona i połączona przez Bluetooth albo Bolt.")
        return

    print(f"Interfejsy HID Logitech: {len(devices)}")
    for number, device in enumerate(devices, start=1):
        product = device.get("product_string") or "(brak nazwy)"
        path = device.get("path")
        if isinstance(path, bytes):
            path = path.decode("utf-8", errors="replace")
        print(f"\n{number}. {product}")
        print(f"   PID: 0x{device.get('product_id', 0):04x}")
        print(f"   Interfejs: {device.get('interface_number', 'n/a')}")
        print(
            f"   Usage page / usage: {device.get('usage_page', 'n/a')} / "
            f"{device.get('usage', 'n/a')}"
        )
        print(f"   Path: {path}")


def watch_mouse_events() -> None:
    print("Nasłuchuję zdarzeń myszy widocznych dla macOS. Ctrl+C kończy.")
    print("Kliknij po kolei dodatkowe przyciski; wynik pokaże nazwę zdarzenia.")

    def on_button(event) -> None:
        print(
            f"{event.phase:4}  button={event.button:12}  pozycja=({event.x}, {event.y})",
            flush=True,
        )

    def on_scroll(event) -> None:
        print(
            f"scroll  dx={event.dx:+g}  dy={event.dy:+g}  "
            f"pozycja=({event.x}, {event.y})",
            flush=True,
        )

    with MouseEvents(on_button=on_button, on_scroll=on_scroll) as listener:
        listener.join()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch",
        action="store_true",
        help="po wylistowaniu urządzeń nasłuchuj zdarzeń myszy widocznych dla macOS",
    )
    args = parser.parse_args()

    list_devices()
    if args.watch:
        print()
        watch_mouse_events()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
