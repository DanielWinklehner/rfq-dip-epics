"""The loop's logic (mist2loop.loop) with a fake Channel Access side: no EPICS, no emulation.

    python3 -m unittest discover -s loops/tests -t loops -v      (from the repository root)
"""
import logging
import unittest
from unittest import mock

from mist2loop import loop as L


class FakeIO:
    """The loop's records as a dictionary: values, severities, and every write in order."""

    def __init__(self):
        self.values = {s: 0.0 for s in set(L.READS) | set(L.WRITES)}
        self.values.update({"value:setpoint": 22.0, "spmin:setpoint": 0.0, "spmax:setpoint": 23.0,
                            "value:read": 21.0, "_act": 85.0, "_write.OVAL": 85.0,
                            "kp:setpoint": 0.5, "ki:setpoint": 0.35, "dfilter:setpoint": 0.2,
                            "outmin:setpoint": 80.0, "outmax:setpoint": 90.0,
                            "slew:setpoint": 1.0, "stale:setpoint": 3.0})
        self.severities = {}
        self.writes = []
        self.up = True

    def connected(self):
        return self.up

    def value(self, suffix):
        return float(self.values[suffix])

    def severity(self, suffix):
        return self.severities.get(suffix, 0)

    def put(self, suffix, value):
        self.writes.append((suffix, value))
        self.values[suffix] = value

    def written(self, suffix):
        return [v for s, v in self.writes if s == suffix]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.io, self.clock = FakeIO(), Clock()
        self.loop = L.Loop("TEST", self.io, 0.2, clock=self.clock)

    def run_cycles(self, n=1):
        """n cycles 0.2 s apart; the heartbeat counts once per second."""
        for _ in range(n):
            self.clock.t += 0.2
            self.io.values["_hb"] = int(self.clock.t)
            self.loop.cycle()

    def started(self):
        """Past the start, the heartbeat seen changing: ready for a request."""
        self.run_cycles(8)
        self.io.writes.clear()

    def reason(self):
        return self.io.values["reason:get"]

    def go_pid(self):
        self.started()
        self.io.values["mode:setpoint"] = 1
        self.run_cycles(1)
        self.assertTrue(self.loop.pid, L.REASONS[int(self.reason())])


class Start(LoopTest):
    def test_a_start_of_the_service_is_manual(self):
        self.io.values.update({"mode:setpoint": 1, "_active": 1})
        self.run_cycles(1)
        self.assertEqual(self.io.values["mode:setpoint"], 0)
        self.assertEqual(self.io.values["_active"], 0)
        self.assertEqual(self.reason(), L.SERVICE_START)
        self.assertFalse(self.loop.pid)

    def test_a_reconnect_is_not_a_service_start(self):
        self.started()
        self.io.up = False
        with self.assertLogs("mist2loop.TEST", logging.WARNING):
            self.run_cycles(1)
        self.io.up = True
        self.io.values["reason:get"] = L.IOC_START       # the IOC started meanwhile
        self.run_cycles(1)
        self.assertEqual(self.reason(), L.IOC_START, "the IOC's reason stays")
        self.assertEqual(self.io.written("_active")[-1:], [0])
        self.assertEqual(self.io.written("mode:setpoint")[-1:], [0])


class Refusal(LoopTest):
    def test_refused_while_a_permit_is_not_fulfilled(self):
        self.started()
        self.io.values.update({"permit2:get": 1, "mode:setpoint": 1})
        self.run_cycles(1)
        self.assertEqual(self.io.values["mode:setpoint"], 0)
        self.assertEqual(self.reason(), L.PERMIT1 + 1)
        self.assertNotIn(1, self.io.written("_active"))

    def test_refused_when_a_permit_is_invalid_with_its_old_value(self):
        """A lost link: the record keeps 0 but is INVALID."""
        self.started()
        self.io.severities["permit1:get"] = L.INVALID
        self.io.values["mode:setpoint"] = 1
        self.run_cycles(1)
        self.assertEqual(self.reason(), L.NODATA1)

    def test_refused_outside_the_output_limits(self):
        self.started()
        self.io.values.update({"_act": 79.0, "mode:setpoint": 1})
        self.run_cycles(1)
        self.assertEqual(self.reason(), L.RANGE)


class Pid(LoopTest):
    def test_bumpless_start(self):
        self.go_pid()
        self.assertEqual(self.reason(), L.NONE)
        out, active = self.io.written("_out"), self.io.writes.index(("_active", 1))
        self.assertEqual(out[0], 85.0, "the first output is the actuator's set point")
        self.assertLess(self.io.writes.index(("_out", 85.0)), active,
                        "the writer's target is set before PID is accepted")

    def test_hand_back_order(self):
        """Measurement before the permits: the first in the order of check() is the reason."""
        self.go_pid()
        self.io.severities["value:read"] = L.INVALID
        self.io.values["permit1:get"] = 1
        self.run_cycles(1)
        self.assertFalse(self.loop.pid)
        self.assertEqual(self.reason(), L.MEASUREMENT)
        self.assertEqual(self.io.values["mode:setpoint"], 0)
        self.assertEqual(self.io.values["_active"], 0)

    def test_hand_back_when_someone_else_writes(self):
        self.go_pid()
        self.loop.on_oval(85.1)
        self.loop.on_act(85.1)                 # the writer's own value
        self.run_cycles(1)
        self.assertTrue(self.loop.pid)
        self.loop.on_act(86.0)                 # someone else's
        self.run_cycles(1)
        self.assertEqual(self.reason(), L.OVERRIDDEN)

    def test_hand_back_when_stale(self):
        self.go_pid()
        for _ in range(20):                    # the heartbeat stands still
            self.clock.t += 0.2
            self.loop.cycle()
        self.assertEqual(self.reason(), L.STALE)

    def test_stop_leaves_manual(self):
        self.go_pid()
        self.loop.stop()
        self.assertEqual(self.io.values["mode:setpoint"], 0)
        self.assertEqual(self.reason(), L.SERVICE_STOPPED)


class Counting(LoopTest):
    def test_a_cycle_counts_only_when_it_completed(self):
        self.go_pid()
        self.io.writes.clear()
        with mock.patch.object(L.pid, "step", side_effect=ValueError("broken")):
            with self.assertLogs("mist2loop.TEST", logging.ERROR) as logs:
                for _ in range(25):            # 5 s of failing cycles
                    self.clock.t += 0.2
                    self.io.values["_hb"] = int(self.clock.t)
                    self.loop.safe_cycle()
        self.assertEqual(self.io.written("_count"), [], "a failing cycle does not count")
        self.assertEqual(len(logs.records), 1, "the error is logged once")
        with self.assertLogs("mist2loop.TEST", logging.INFO) as logs:
            self.run_cycles(0)
            self.clock.t += 0.2
            self.loop.safe_cycle()
        self.assertEqual(len(self.io.written("_count")), 1, "counts again")
        self.assertIn("cycles complete again", logs.output[-1])


if __name__ == "__main__":
    unittest.main()
