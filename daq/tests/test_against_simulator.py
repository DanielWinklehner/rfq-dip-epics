"""mist2daq's replies against the libcom1 simulator's (emulation/sim, itself proven line by line
against the real library), command by command, in the Opta's number format ("%g").

1. The fixed conversation of AVR/libcom1/tests/script.hpp (every command, errors, streaming,
   the communication timeout), on the script's device.
2. More lines on a device shaped like the dipole service (o1 read/write, i1 read-only).
The real library itself: daq/tools/compare_libcom1.sh (needs g++).
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "emulation", "sim"))
sys.path.insert(0, os.path.join(REPO, "daq", "tools"))

from mist2sim.devices import libcom1 as sim  # noqa: E402
import libcom1_replay  # noqa: E402

from mist2daq.protocol import Channel, Device, LineReader  # noqa: E402


def sim_script_device():
    values = [sim.f32(v) for v in (4091.71, 0.0, -2.5, 23.4609375, 1.5e-7, 0.0)]
    state = {"setpoint": 0.0, "timeouts": 0}

    def set_sp(v):
        state["setpoint"] = v

    def set_idx(v):
        values[5] = v

    def on_timeout():
        state["timeouts"] += 1
        state["setpoint"] = -1.0

    channels = [
        sim.Channel("a", 1, lambda: values[0]), sim.Channel("a", 2, lambda: values[1]),
        sim.Channel("a", 3, lambda: values[2]), sim.Channel("b", 1, lambda: values[3]),
        sim.Channel("b", 2, lambda: values[4]),
        sim.Channel("s", 1, lambda: state["setpoint"], set_sp), sim.Channel("w", 1, None, set_sp),
        sim.Channel("x", 1, lambda: sim.f32(values[5] * 2.0), set_idx),
    ]
    engine = sim.Engine(channels, "ScriptDevice", "1.2.3", "g", out_buffer=160)
    engine.set_comm_timeout(500, on_timeout)
    return engine, state


class ScriptConversation(unittest.TestCase):
    def test_every_step_identical(self):
        tool = libcom1_replay.sim_tool()
        with open(libcom1_replay.DEFAULT_SCRIPT) as f:
            text = f.read()
        tool.check_device(text)
        steps = tool.parse_steps(text)
        mine, mine_state = libcom1_replay.script_device()
        theirs, their_state = sim_script_device()
        for time_ms, line in steps:
            received = "" if line is None else line[:31]
            reply, frames, code = mine.service(time_ms, received)
            out = theirs.service(time_ms, received)
            self.assertEqual((reply, frames, code, mine.comm_lost),
                             (out.reply, out.frames, out.code, theirs.comm_lost), (time_ms, line))
        self.assertEqual(mine_state["timeouts"], their_state["timeouts"])
        self.assertGreater(len(steps), 50)


EXTRA = [
    "I", "A", "go1", "gi1", "So125", "So125.000000", "so17", "go1", "A", "Si15", "si15", "gz1",
    "Sz15", "So1", "So1 ", "So1 1", "So11 ", "So1\t2\r", "So1+3", "So1-0", "So1.5", "So15.",
    "So1e5", "So11e", "So10x10", "So10x1p-2", "So1INF", "So1-inf", "So1NaN", "So1nan(1)",
    "So11e38", "So13.5e38", "So1-1e39", "So11e-50", "go1", "q01o13", "q01i16", "q01o17", "q02o13",
    "q01o1", "q01z13", "g", "go", "goo", "S", "s", "P", "Px", "P10x", "P 10", "P0", "P4294967296",
    "P0", "?", "a", "i", "c", "n", "ga1\0junk", "\0", "A\0", "So15\0x", "Io", "Axyz",
]


def pair():
    """The same two-channel device in both: o1 read/write (a plain variable), i1 read-only."""
    st = {"o1": math.nan, "i1": 12.5}

    def set_o1(v):
        st["o1"] = v

    mine = Device([Channel("o", 1, lambda: st["o1"], set_o1), Channel("i", 1, lambda: st["i1"])],
                  "DipoleDAQ", "mist2daq-0.1", out_buffer=160)
    sst = {"o1": math.nan, "i1": 12.5}

    def sset_o1(v):
        sst["o1"] = v

    theirs = sim.Engine([sim.Channel("o", 1, lambda: sst["o1"], sset_o1),
                         sim.Channel("i", 1, lambda: sst["i1"])],
                        "DipoleDAQ", "mist2daq-0.1", "g", out_buffer=160)
    return mine, theirs


class MoreLines(unittest.TestCase):
    def test_line_by_line(self):
        mine, theirs = pair()
        for t, line in enumerate(EXTRA):
            reply, frames, code = mine.service(t, line)
            out = theirs.service(t, line)
            self.assertEqual((reply, frames, code), (out.reply, out.frames, out.code), repr(line))

    def test_line_framing(self):
        """LineReader against the simulator's model of LineBuffer<128> (from_line_buffer)."""
        for raw in ["A", "A\r", "\r", "", "x" * 127, "x" * 128, "S\ro15", "\r\r\rI"]:
            got = LineReader(128).feed(raw.encode("latin-1") + b"\n")
            expected = sim.from_line_buffer(raw, 128)
            self.assertEqual(got, [] if expected is None else [expected], repr(raw))


if __name__ == "__main__":
    unittest.main()
