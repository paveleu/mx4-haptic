#!/usr/bin/env python3
"""Compatibility wrapper for the installed ``mx4-haptic haptics`` command."""

from __future__ import annotations

import sys

from mx4_haptic.cli import main


def main_legacy() -> int:
    args = sys.argv[1:]
    if not args:
        return main(["haptics", "status"])
    if args == ["--play-default"]:
        return main(["haptics", "play", "0"])
    if len(args) == 2 and args[0] == "--play":
        return main(["haptics", "play", args[1]])
    if len(args) == 2 and args[0] == "--level":
        return main(["haptics", "level", args[1]])
    print(
        "Use mx4-haptic haptics {status,play,level}; run with --help for details.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main_legacy())
