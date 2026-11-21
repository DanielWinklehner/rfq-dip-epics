"""Signals and couplings with a fake clock: no sleeping."""

import math
import random
import statistics
import unittest

import helpers  # noqa: F401  (sys.path)

from mist2sim.core import FakeClock, Signal

from helpers import Echo


class SignalTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def sig(self, **kw):
        return Signal("x", clock=self.clock, rng=random.Random(1), **kw)

    def test_first_order(self):
        s = self.sig(value=0.0, tau=2.0)
        s.target = 10.0
        self.assertEqual(s.value, 0.0)
        self.clock.advance(2.0)
        self.assertAlmostEqual(s.value, 10.0 * (1 - math.exp(-1)), places=9)
        self.clock.advance(18.0)
        self.assertAlmostEqual(s.value, 10.0, places=3)

    def test_steps_do_not_change_the_curve(self):
        a, b = self.sig(tau=1.0), self.sig(tau=1.0)
        a.target = b.target = 1.0
        for _ in range(100):
            self.clock.advance(0.01)
            a.value
        self.assertAlmostEqual(a.value, b.value, places=12)

    def test_zero_tau_follows_at_once(self):
        s = self.sig(value=1.0)
        s.target = 3.0
        self.assertEqual(s.value, 3.0)

    def test_noise_on_read_only(self):
        s = self.sig(value=5.0, noise=0.1)
        reads = [s.read() for _ in range(2000)]
        self.assertAlmostEqual(statistics.mean(reads), 5.0, delta=0.01)
        self.assertAlmostEqual(statistics.stdev(reads), 0.1, delta=0.01)
        self.assertEqual(s.value, 5.0)

    def test_limits_and_step(self):
        s = self.sig(value=0.0, lo=0.0, hi=10.0, step=0.25)
        s.target = 20.0
        self.assertEqual(s.value, 10.0)
        s.target = 3.3
        self.assertEqual(s.read(), 3.25)
        s.target = -1
        self.assertEqual(s.read(), 0.0)

    def test_force_and_release(self):
        s = self.sig(value=0.0, tau=1.0)
        s.force(7.0)
        s.target = 1.0                      # the device writes, the outside keeps control
        self.clock.advance(10.0)
        self.assertEqual(s.value, 7.0)
        self.assertTrue(s.state()["external"])
        s.release()
        self.clock.advance(1.0)
        self.assertAlmostEqual(s.value, 1.0 + 6.0 * math.exp(-1), places=9)


class CouplingTest(unittest.TestCase):
    def test_relay_ramps_speed_which_sets_status(self):
        clock = FakeClock()
        sim = Echo("pump", clock=clock)
        relay = sim.add_signal("relay", 0.0)
        speed = sim.add_signal("speed", 0.0, tau=10.0)
        normal = sim.add_signal("normal", 0.0)
        seen = []

        def pump(dt, signals):
            seen.append(dt)
            signals["speed"].target = 1000.0 if signals["relay"].value else 0.0
            signals["normal"].target = 1.0 if signals["speed"].value > 800.0 else 0.0

        sim.add_coupling(pump)
        relay.target = 1.0
        sim.process(b"x")                  # couplings are stepped before every request
        self.assertEqual(normal.value, 0.0)
        clock.advance(30.0)
        sim.process(b"x")
        self.assertGreater(speed.value, 800.0)
        sim.step_couplings()
        self.assertEqual(normal.value, 1.0)
        self.assertEqual(seen[1], 30.0)


if __name__ == "__main__":
    unittest.main()
