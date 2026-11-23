"""Faults: silent, close, garbage, trip, slow, per unit and timed; bus routing; reconnect."""

import time
import unittest

from helpers import Bus, Echo, LineClient, wait_until

from mist2sim.control import ControlClient, ControlError
from mist2sim.core import FakeClock, SimThread
from mist2sim.core.simulator import GARBAGE


class ProcessFaultTest(unittest.TestCase):
    """Fault logic without sockets, with a fake clock."""

    def setUp(self):
        self.clock = FakeClock()
        self.sim = Echo("echo", clock=self.clock)
        self.bus = Bus("bus", clock=self.clock)

    def test_silent_and_timed_clearing(self):
        self.sim.add_fault("silent", duration=2.0)
        self.assertEqual(self.sim.process(b"a"), [])
        self.clock.advance(1.9)
        self.assertEqual(self.sim.process(b"a"), [])
        self.clock.advance(0.2)
        self.assertEqual(self.sim.process(b"a"), [b"re:a"])
        self.assertEqual(self.sim.fault_list(), [])

    def test_garbage_keeps_length_and_never_parses(self):
        self.sim.add_fault("garbage")
        (reply,) = self.sim.process(b"abc")
        self.assertEqual(len(reply), len(b"re:abc"))
        self.assertTrue(set(reply) <= set(GARBAGE))
        self.sim.clear_faults()
        self.assertEqual(self.sim.process(b"abc"), [b"re:abc"])

    def test_trip_is_device_specific(self):
        self.sim.add_fault("trip", duration=1.0)
        self.assertEqual(self.sim.tripped, 1)
        self.assertEqual(self.sim.signals["out"].value, 0.0)
        self.clock.advance(1.5)
        self.sim.expire_faults()
        self.assertEqual(self.sim.cleared, 1)

    def test_trip_unsupported_is_an_error(self):
        with self.assertRaises(Exception) as ctx:
            self.bus.add_fault("trip")
        self.assertIn("no trip", str(ctx.exception))

    def test_bus_routing_and_silent_unit(self):
        self.assertEqual(self.bus.process(b"#1 Q"), [b"#1 A"])
        self.assertEqual(self.bus.process(b"#9 Q"), [])        # no such address: no answer
        self.assertEqual(self.bus.process(b"junk"), [])
        self.bus.add_fault("silent", unit=2)
        self.assertEqual(self.bus.process(b"#2 Q"), [])
        self.assertEqual(self.bus.process(b"#1 Q"), [b"#1 A"])
        self.assertEqual(self.bus.process(b"#3 Q"), [b"#3 A"])
        self.bus.process(b"#AL X")                             # broadcast: the silent unit is out
        self.assertEqual(self.bus.hits, {1: 3, 3: 2})
        self.assertEqual(self.bus.stats.per_unit["2"], {"requests": 2, "replies": 0})
        self.bus.clear_faults(unit=2)
        self.assertEqual(self.bus.process(b"#2 Q"), [b"#2 A"])

    def test_slow_second_delays_the_second_reply_once(self):
        """slow_second: the unit's first reply after the fault is on time, the second is late,
        then the fault is gone; replies of other units do not count."""
        self.bus.add_fault("slow_second", unit=2, ms=300)
        self.assertEqual(self.bus._process(b"#1 Q"), ([b"#1 A"], 0.0))     # other unit
        self.assertEqual(self.bus._process(b"#2 Q"), ([b"#2 A"], 0.0))     # first reply
        self.assertEqual(self.bus._process(b"#9 Q"), ([], 0.0))            # no reply
        self.assertEqual(self.bus._process(b"#2 Q"), ([b"#2 A"], 0.3))     # second: late
        self.assertEqual(self.bus.fault_list(), [])
        self.assertEqual(self.bus._process(b"#2 Q"), ([b"#2 A"], 0.0))
        with self.assertRaises(ValueError):
            self.bus.add_fault("slow_second", unit=2)                      # needs ms

    def test_bad_fault_arguments(self):
        for kwargs in ({"mode": "melt"}, {"mode": "slow"}, {"mode": "slow", "ms": -1},
                       {"mode": "silent", "duration": 0}, {"mode": "silent", "unit": 1},
                       {"mode": "silent", "ms": 5}):
            with self.assertRaises(ValueError, msg=kwargs):
                self.sim.add_fault(**kwargs)
        for kwargs in ({"mode": "silent", "unit": 7}, {"mode": "close", "unit": 1}):
            with self.assertRaises(ValueError, msg=kwargs):
                self.bus.add_fault(**kwargs)

    def test_device_exception_gives_no_reply_and_no_crash(self):
        with self.assertLogs("mist2sim", "ERROR"):
            self.assertEqual(self.sim.process(b"boom"), [])
        self.assertEqual(self.sim.process(b"a"), [b"re:a"])


class SocketFaultTest(unittest.TestCase):
    def setUp(self):
        self.sim = Echo("echo", baud=115200)
        self.bus = Bus("bus", baud=115200)
        self.runner = SimThread([self.sim, self.bus])
        self.runner.__enter__()
        self.addCleanup(self.runner.__exit__)
        self.ctl = ControlClient("127.0.0.1", self.sim.control_port)
        self.addCleanup(self.ctl.close)

    def client(self, sim=None):
        c = LineClient((sim or self.sim).port)
        self.addCleanup(c.close)
        return c

    def test_silent_with_duration_through_control(self):
        c = self.client()
        self.assertEqual(c.ask(b"a"), b"re:a")
        self.ctl.fault("silent", duration=0.3)
        self.assertIsNone(c.ask(b"b", timeout=0.2))
        time.sleep(0.2)
        self.assertEqual(c.ask(b"c"), b"re:c")

    def test_close_refuses_then_reconnect(self):
        c = self.client()
        self.assertEqual(c.ask(b"a"), b"re:a")
        self.ctl.fault("close")
        with self.assertRaises((ConnectionError, OSError)):
            c.ask(b"b")
            c.ask(b"b")
        # new connections are accepted and closed at once while the fault is active
        d = self.client()
        with self.assertRaises((ConnectionError, OSError)):
            d.ask(b"b")
        self.ctl.clear()
        e = self.client()
        self.assertEqual(e.ask(b"c"), b"re:c")

    def test_close_with_duration(self):
        self.ctl.fault("close", duration=0.3)
        time.sleep(0.4)
        self.assertEqual(self.client().ask(b"a"), b"re:a")

    def test_new_connection_replaces_old(self):
        a = self.client()
        self.assertEqual(a.ask(b"1"), b"re:1")
        b = self.client()
        self.assertEqual(b.ask(b"2"), b"re:2")
        with self.assertRaises((ConnectionError, OSError)):
            a.ask(b"3")
            a.ask(b"3")

    def test_garbage_is_timed(self):
        c = self.client()
        self.ctl.fault("garbage")
        t0 = time.monotonic()
        reply = c.ask(b"abc")
        dt = time.monotonic() - t0
        self.assertNotEqual(reply, b"re:abc")
        self.assertEqual(len(reply), 6)
        want = (4 + 7) * 10 / 115200.0
        self.assertAlmostEqual(dt, want, delta=0.002 + 0.02 * want)

    def test_slow(self):
        c = self.client()
        self.ctl.fault("slow", ms=100)
        t0 = time.monotonic()
        self.assertEqual(c.ask(b"a"), b"re:a")
        self.assertGreater(time.monotonic() - t0, 0.1)
        self.ctl.clear("slow")
        t0 = time.monotonic()
        self.assertEqual(c.ask(b"a"), b"re:a")
        self.assertLess(time.monotonic() - t0, 0.05)

    def test_trip_through_control(self):
        self.ctl.fault("trip")
        self.assertEqual(self.ctl.get("out")["value"], 0.0)
        with ControlClient("127.0.0.1", self.bus.control_port) as bus:
            with self.assertRaises(ControlError):
                bus.fault("trip")

    def test_bus_unit_silent_over_tcp(self):
        c = self.client(self.bus)
        with ControlClient("127.0.0.1", self.bus.control_port) as bus:
            bus.fault("silent", unit=2, duration=0.5)
            self.assertEqual(c.ask(b"#1 Q"), b"#1 A")
            self.assertIsNone(c.ask(b"#2 Q", timeout=0.2))
            self.assertEqual(c.ask(b"#3 Q"), b"#3 A")
            self.assertTrue(wait_until(lambda: c.ask(b"#2 Q", timeout=0.1) == b"#2 A", 1.0))
            stats = bus.stats()
            self.assertGreaterEqual(stats["per_unit"]["2"]["requests"], 2)


if __name__ == "__main__":
    unittest.main()
