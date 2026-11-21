"""The device module examples of README.md, run as written."""

import os
import re
import unittest

from helpers import LineClient

from mist2sim.control import ControlClient
from mist2sim.core import FakeClock, SimThread, build

README = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "README.md")


def blocks():
    with open(README) as f:
        return re.findall(r"```python\n(.*?)```", f.read(), re.S)


class ReadmeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code = blocks()
        assert len(code) == 3, "README.md should have three python examples"
        for block in code:
            exec(compile(block, README, "exec"), {})

    def test_single_device(self):
        clock = FakeClock()
        psu = build({"name": "psu", "type": "demo_psu", "port": 0}, clock=clock)
        self.assertEqual(psu.process(b"V 12\r"), [])
        self.assertEqual(psu.process(b"V?"), [b"V=0.000"])
        self.assertEqual(psu.process(b"OUT 1"), [b"OK"])
        clock.advance(5.0)
        self.assertAlmostEqual(float(psu.process(b"V?")[0][2:]), 12.0, delta=0.02)
        psu.add_fault("trip")
        self.assertEqual(psu.process(b"V?"), [b"V=0.000"])
        self.assertEqual(psu.process(b"V x"), [b"ERR"])

    def temp(self, c, unit):
        reply = c.ask(b"#%d T?" % unit)
        self.assertTrue(reply.startswith(b"#%d T=" % unit), reply)
        return float(reply.split(b"=")[1])

    def test_bus_over_tcp(self):
        bus = build({"name": "bus", "type": "demo_bus", "port": 0, "options": {"units": [1, 2, 3]}})
        with SimThread([bus]):
            c = LineClient(bus.port)
            self.addCleanup(c.close)
            self.assertAlmostEqual(self.temp(c, 2), 22.0, delta=0.3)
            self.assertIsNone(c.ask(b"#7 T?", timeout=0.1))
            with ControlClient("127.0.0.1", bus.control_port) as ctl:
                ctl.fault("silent", unit=3)
                ctl.set("1.temp", 50.0)
                self.assertIsNone(c.ask(b"#3 T?", timeout=0.1))
                self.assertAlmostEqual(self.temp(c, 1), 50.0, delta=0.3)
                c.send(b"#AL RST\n")
                ctl.release("1.temp")
                self.assertAlmostEqual(self.temp(c, 1), 20.0, delta=0.3)
                self.assertEqual(ctl.get("3.temp")["value"], 23.0)   # silent: did not reset


if __name__ == "__main__":
    unittest.main()
