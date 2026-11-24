"""Replays AVR/devices/InterlockOpta/tests/conversation.txt through the simulator built from the
entry `interlockbox` of a simulator configuration, and prints the same transcript as
AVR/devices/InterlockOpta/tests/replay_device.cpp prints for the firmware.

    python3 tools/interlock_replay.py [--config config/rack.yaml] [--entry interlockbox]
                                      [--script .../conversation.txt]

The simulator is built exactly as `python -m mist2sim` builds it (load_config, build), with a
clock that only moves to the time of each step. The doors are given to it as the values of its
signals i1 and i2 (the "doors" column of the file: what the firmware reports at that time).
`make` in AVR/devices/InterlockOpta/tests diffs the two transcripts.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from mist2sim.core import FakeClock, build, load_config  # noqa: E402

ROOT = os.path.join(HERE, "..", "..", "..")
DEFAULT_CONFIG = os.path.join(HERE, "..", "config", "rack.yaml")
DEFAULT_SCRIPT = os.path.join(ROOT, "AVR", "devices", "InterlockOpta", "tests", "conversation.txt")


def parse(path):
    """[(ms, doors "ab", line or None), ...]"""
    steps = []
    with open(path) as handle:
        for number, text in enumerate(handle, 1):
            text = text.rstrip("\r\n")
            if not text or text.startswith("#"):
                continue
            parts = text.split(" ", 4)
            if len(parts) != 5 or len(parts[3]) != 2 or not parts[0].isdigit():
                raise SystemExit("%s:%d: cannot parse %r" % (path, number, text))
            line = None if parts[4] == "-" else parts[4]
            steps.append((int(parts[0]), parts[3], line))
    return steps


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--entry", default="interlockbox")
    parser.add_argument("--script", default=DEFAULT_SCRIPT)
    args = parser.parse_args()

    entries = [e for e in load_config(args.config) if e["name"] == args.entry]
    if len(entries) != 1:
        raise SystemExit("%s: no single entry %r" % (args.config, args.entry))
    entry = dict(entries[0], port=0, control_port=0)
    clock = FakeClock()
    sim = build(entry, clock=clock)

    out = sys.stdout
    for ms, doors, line in parse(args.script):
        clock.t = ms / 1000.0
        sim.signals["i1"].force(float(doors[0]))
        sim.signals["i2"].force(float(doors[1]))
        replies = [] if line is None else sim.process(line.encode("latin-1"))
        out.write("> %d doors=%s %s\n" % (ms, doors, "(nothing)" if line is None else line))
        for reply in replies:
            out.write(reply.decode("latin-1") + "\n")


if __name__ == "__main__":
    main()
