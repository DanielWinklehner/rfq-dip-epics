"""The PID algorithm (mist2loop.pid) alone, without EPICS and without the emulation (test A).

    python3 -m unittest discover -s loops/tests -t loops -v      (from the repository root)
"""
import math
import unittest

from mist2loop import pid


def wide(kp, ki, kd, **kw):
    """Parameters whose limits do not matter: wide output range, fast slew, no filter."""
    p = dict(kp=kp, ki=ki, kd=kd, tf=0.0, out_min=-1e6, out_max=1e6, slew=1e6, dt_max=1.0)
    p.update(kw)
    return pid.Params(**p)


def run(s, p, sp, pv, dt, n):
    for _ in range(n):
        s, r = pid.step(s, p, sp, pv, dt)
    return s, r


class Terms(unittest.TestCase):
    def test_proportional(self):
        p = wide(2.0, 0.0, 0.0)
        s, _ = pid.start(p, 5.0, 5.0, 10.0)
        s, r = pid.step(s, p, 5.0, 4.0, 0.1)
        self.assertAlmostEqual(r.p, 2.0, places=12)
        self.assertAlmostEqual(r.out, 12.0, places=12)

    def test_integral(self):
        p = wide(0.0, 0.5, 0.0)
        s, _ = pid.start(p, 5.0, 5.0, 10.0)
        s, r = run(s, p, 5.0, 4.0, 0.1, 10)           # e = 1 for 1 s
        self.assertAlmostEqual(r.i, 10.5, places=9)
        self.assertAlmostEqual(r.out, 10.5, places=9)

    def test_derivative_on_the_measurement(self):
        p = wide(0.0, 0.0, 1.0)
        s, _ = pid.start(p, 5.0, 0.0, 10.0)
        for k in range(1, 6):                          # measurement rises 1 per s
            s, r = pid.step(s, p, 5.0, 0.1 * k, 0.1)
        self.assertAlmostEqual(r.d, -1.0, places=9)
        s, r = pid.step(s, p, 9.0, 0.6, 0.1)           # a set point step
        self.assertAlmostEqual(r.d, -1.0, places=9, msg="the set point does not reach D")

    def test_derivative_filter(self):
        p = wide(0.0, 0.0, 1.0, tf=1.0)
        s, _ = pid.start(p, 0.0, 0.0, 0.0)
        s, r = pid.step(s, p, 0.0, 1.0, 0.1)
        self.assertAlmostEqual(r.d, -1.0 / 1.1, places=9)


class Limits(unittest.TestCase):
    def test_output_limits_and_flags(self):
        p = wide(10.0, 0.0, 0.0, out_min=0.0, out_max=20.0)
        s, _ = pid.start(p, 0.0, 0.0, 10.0)
        s, r = pid.step(s, p, 5.0, 0.0, 0.1)
        self.assertEqual((r.out, r.limited), (20.0, pid.AT_MAX))
        s, r = pid.step(s, p, -5.0, 0.0, 0.1)
        self.assertEqual((r.out, r.limited), (0.0, pid.AT_MIN))
        s, r = pid.step(s, p, 0.5, 0.0, 0.1)
        self.assertEqual(r.limited, pid.FREE)

    def test_slew_limit(self):
        p = wide(10.0, 0.0, 0.0, slew=2.0)
        s, _ = pid.start(p, 0.0, 0.0, 10.0)
        s, r = pid.step(s, p, 1.0, 0.0, 0.1)
        self.assertAlmostEqual(r.out, 10.2, places=12)
        self.assertEqual(r.limited, pid.AT_SLEW)
        s, r = run(s, p, 1.0, 0.0, 0.1, 100)
        self.assertAlmostEqual(r.out, 20.0, places=9)
        self.assertEqual(r.limited, pid.FREE)
        p = wide(10.0, 0.0, 0.0, slew=2.0, out_max=15.0)
        s, r = pid.step(s, p, 1.0, 0.0, 0.1)
        self.assertAlmostEqual(r.out, 19.8, places=9, msg="a lowered maximum is reached at the slew rate")


class AntiWindup(unittest.TestCase):
    def test_leaves_the_maximum_at_once(self):
        p = wide(1.0, 1.0, 0.0, out_min=0.0, out_max=20.0)
        s, _ = pid.start(p, 10.0, 10.0, 10.0)
        s, r = run(s, p, 13.0, 10.0, 0.1, 1000)        # 100 s with e = +3
        self.assertEqual((r.out, r.limited), (20.0, pid.AT_MAX))
        self.assertAlmostEqual(r.i, 17.0, places=9, msg="the integral stopped at the limit")
        s, r = pid.step(s, p, 9.5, 10.0, 0.1)          # e = -0.5
        self.assertLess(r.out, 20.0)
        self.assertAlmostEqual(r.out, 17.0 - 0.5 - 0.05, places=9)

    def test_integral_bounded_when_the_maximum_is_lowered(self):
        p = wide(1.0, 1.0, 0.0, out_min=0.0, out_max=15.0)
        s, _ = pid.start(p, 10.0, 10.0, 18.0)
        s, r = run(s, p, 10.0, 10.0, 0.1, 100)
        self.assertAlmostEqual(r.out, 15.0, places=12)
        s, r = pid.step(s, p, 9.5, 10.0, 0.1)
        self.assertLess(r.out, 15.0, "leaves the lowered maximum at the first step with e < 0")

    def test_no_integration_while_slew_limited(self):
        p = wide(1.0, 1.0, 0.0, out_min=0.0, out_max=20.0, slew=0.1)
        s, _ = pid.start(p, 10.0, 10.0, 10.0)
        s, r = run(s, p, 13.0, 10.0, 0.1, 100)
        self.assertEqual(r.limited, pid.AT_SLEW)
        self.assertAlmostEqual(r.out, 11.0, places=9)
        self.assertAlmostEqual(r.i, 10.0, places=9)


class Bumpless(unittest.TestCase):
    def test_start_and_gain_changes(self):
        p = wide(2.0, 0.5, 1.0)
        s, r = pid.start(p, 20.0, 18.0, 88.0)
        self.assertEqual(r.out, 88.0, "the first output is the actuator's value")
        s, r = pid.step(s, p, 20.0, 18.0, 0.1)
        self.assertAlmostEqual(r.out, 88.1, places=12, msg="then only Ki e dt")
        before = r.out
        p = wide(6.0, 0.5, 1.0)
        s, r = pid.step(s, p, 20.0, 18.0, 0.1)
        self.assertAlmostEqual(r.out - before, 0.1, places=12, msg="Kp 2 -> 6: no jump")

        s, r = pid.start(p, 20.0, 18.0, 88.0)
        s, r = pid.step(s, p, 20.0, 18.1, 0.1)         # measurement rising: d_rate = 1
        before = r.out
        p = wide(6.0, 0.5, 3.0)
        s, r = pid.step(s, p, 20.0, 18.2, 0.1)
        self.assertAlmostEqual(r.out - before, 6.0 * -0.1 + 0.5 * 1.8 * 0.1, places=9,
                               msg="Kd 1 -> 3: no jump of the D term")
        before = r.out
        p = wide(6.0, 5.0, 3.0)
        s, r = pid.step(s, p, 20.0, 18.3, 0.1)
        self.assertAlmostEqual(r.out - before, 6.0 * -0.1 + 5.0 * 1.7 * 0.1, places=9,
                               msg="Ki 0.5 -> 5: no jump")

    def test_set_point_step_through_the_slew_limit(self):
        p = wide(2.0, 0.0, 0.0, slew=1.0)
        s, _ = pid.start(p, 20.0, 20.0, 88.0)
        s, r = pid.step(s, p, 22.0, 20.0, 0.1)
        self.assertAlmostEqual(r.out, 88.1, places=12)


class DtGuards(unittest.TestCase):
    def setUp(self):
        self.p = wide(1.0, 1.0, 1.0)
        s, _ = pid.start(self.p, 10.0, 9.0, 50.0)
        self.s, _ = pid.step(s, self.p, 10.0, 9.0, 0.1)

    def test_no_time_changes_nothing(self):
        for dt in (0.0, -1.0, math.nan):
            s, r = pid.step(self.s, self.p, 10.0, 5.0, dt)
            self.assertEqual(s, self.s, "dt = %r: the state stays" % dt)
            self.assertEqual(r.out, self.s.out)

    def test_long_gap(self):
        s, r = pid.step(self.s, self.p, 10.0, 9.0, 1000.0)     # dt_max = 1 s
        self.assertAlmostEqual(r.i, self.s.integral + 1.0, places=12)
        self.assertEqual(r.d, 0.0, "the derivative starts again, no kick")


if __name__ == "__main__":
    unittest.main()
