"""The control interface over TCP, including bad input."""

import json
import socket
import unittest

from helpers import Bus, Echo, LineClient

from mist2sim.control import ControlClient, ControlError
from mist2sim.core import SimThread


class ControlTest(unittest.TestCase):
    def setUp(self):
        self.sim = Echo("echo", baud=115200, options={"greeting": "hello"})
        self.bus = Bus("bus", baud=115200)
        runner = SimThread([self.sim, self.bus])
        runner.__enter__()
        self.addCleanup(runner.__exit__)
        self.c = ControlClient("127.0.0.1", self.sim.control_port)
        self.addCleanup(self.c.close)

    def test_info(self):
        info = self.c.info()
        self.assertEqual(info["name"], "echo")
        self.assertEqual(info["type"], "test_echo")
        self.assertEqual(info["port"], self.sim.port)
        self.assertEqual(info["signals"], ["out"])
        self.assertEqual(info["units"], [])
        self.assertEqual(info["settings"]["baud"], 115200)
        self.assertEqual(info["options"], {"greeting": "hello"})
        with ControlClient("127.0.0.1", self.bus.control_port) as b:
            self.assertEqual(b.info()["units"], [1, 2, 3])

    def test_get_set_release(self):
        self.assertEqual(self.c.get("out")["value"], 5.0)
        everything = self.c.get()
        self.assertEqual(set(everything["signals"]), {"out"})
        self.assertEqual(everything["faults"], [])
        r = self.c.set("out", 2.5)
        self.assertEqual((r["value"], r["external"]), (2.5, True))
        self.sim.signals["out"].target = 9.0          # device writes; outside keeps control
        self.assertEqual(self.c.get("out")["value"], 2.5)
        r = self.c.release("out")
        self.assertFalse(r["external"])
        self.assertEqual(self.c.get("out")["value"], 9.0)

    def test_fault_clear_listing(self):
        self.c.fault("slow", ms=20, duration=60)
        self.c.fault("garbage")
        faults = self.c.get()["faults"]
        self.assertEqual([f["mode"] for f in faults], ["slow", "garbage"])
        self.assertGreater(faults[0]["remaining_s"], 59)
        self.assertEqual(self.c.clear("garbage")["cleared"], 1)
        self.assertEqual(self.c.clear()["cleared"], 1)
        with ControlClient("127.0.0.1", self.bus.control_port) as b:
            b.fault("silent", unit="2")              # units given as text are found too
            self.assertEqual(b.get()["faults"][0]["unit"], 2)

    def test_stats_and_reset(self):
        line = LineClient(self.sim.port)
        self.addCleanup(line.close)
        line.ask(b"abc")
        line.ask(b"quiet", timeout=0.05)
        s = self.c.stats(reset=True)
        self.assertEqual((s["requests"], s["replies"]), (2, 1))
        self.assertEqual(s["bytes_in"], 4 + 6)
        self.assertEqual(s["bytes_out"], 7)
        self.assertAlmostEqual(s["busy_s"], (4 + 7 + 6) * 10 / 115200.0, places=6)
        s = self.c.stats()
        self.assertEqual((s["requests"], s["bytes_in"]), (0, 0))

    def test_bad_input_gives_error_objects(self):
        bad = [
            "not json", "[1, 2]", "{}", '{"cmd": "explode"}', '{"cmd": 5}',
            '{"cmd": "fault"}', '{"cmd": "fault", "mode": "melt"}',
            '{"cmd": "fault", "mode": "slow"}', '{"cmd": "fault", "mode": "silent", "unit": 1}',
            '{"cmd": "fault", "mode": "silent", "duration": "long"}',
            '{"cmd": "get", "signal": "nope"}', '{"cmd": "set", "signal": "out"}',
            '{"cmd": "set", "signal": "out", "value": "high"}', '{"cmd": "set", "value": 1}',
            '{"cmd": "release", "signal": 3}', '{"cmd": "stats", "reset": "yes"}',
            '{"cmd": "info", "verbose": true}', '{"cmd": "clear", "unit": 9}',
            '{"cmd": "fault", "mode": "trip", "unit": 1}',
        ]
        for line in bad:
            reply = self.c.call(line)
            self.assertIs(reply["ok"], False, line)
            self.assertIsInstance(reply["error"], str)
        self.assertTrue(self.c.call({"cmd": "info"})["ok"])   # still alive
        with self.assertRaises(ControlError):
            self.c.set("nope", 1)

    def test_binary_junk_and_blank_lines(self):
        s = socket.create_connection(("127.0.0.1", self.sim.control_port), timeout=2)
        self.addCleanup(s.close)
        s.sendall(b"\n\xff\xfe\x00\n")
        reply = json.loads(s.makefile("rb").readline())
        self.assertFalse(reply["ok"])


if __name__ == "__main__":
    unittest.main()
