"""The PID at its slew limit (review point F8): with a persistent error and the output between its
limits, the output never stands still, and the integral does not wind up behind the slew limit.
Without EPICS and without the emulation.

    python3 -m unittest discover -s loops/tests -t loops -v      (from the repository root)
"""
import itertools
import math
import unittest

from mist2loop import pid

DT = 0.2                               # the loops' period


def params(kp=0.5, ki=0.35, slew=1.0, lo=80.0, hi=90.0, kd=0.0):
    return pid.Params(kp=kp, ki=ki, kd=kd, tf=0.2, out_min=lo, out_max=hi, slew=slew,
                      dt_max=3 * DT)


class HandCases(unittest.TestCase):
    """The lead's two cases: a bumpless start with Ki*e larger than the slew limit."""

    def ramp(self, p, sp, pv, out_now):
        s, r = pid.start(p, sp, pv, out_now)
        outs, flags = [r.out], []
        while r.out < p.out_max - 1e-9 and len(outs) < 200:
            s, r = pid.step(s, p, sp, pv, DT)
            outs.append(r.out)
            flags.append(r.limited)
        return outs, flags

    def check(self, p, sp, pv, out_now):
        outs, flags = self.ramp(p, sp, pv, out_now)
        steps = [b - a for a, b in zip(outs, outs[1:])]
        room = p.slew * DT
        self.assertTrue(steps, "the output moved")
        for k, (step, flag) in enumerate(zip(steps[:-1], flags[:-1])):
            self.assertAlmostEqual(step, room, places=9, msg="step %d: %r" % (k, steps[:12]))
            self.assertEqual(flag, pid.AT_SLEW, "step %d flagged slew limited" % k)
        self.assertLessEqual(steps[-1], room + 1e-9)
        self.assertAlmostEqual(outs[-1], p.out_max, places=9)
        self.assertEqual(flags[-1] in (pid.AT_SLEW, pid.AT_MAX), True)

    def test_18_to_22_a_at_slew_1(self):
        """MANUAL at 18.0 A (TDK 88.20 A), set point 22 A, kp 0.5, ki 0.35, slew 1 A/s."""
        self.check(params(slew=1.0), 22.0, 18.0, 88.2)

    def test_20_to_22_a_at_slew_0_5(self):
        self.check(params(slew=0.5), 22.0, 20.0, 88.2)


class Sweep(unittest.TestCase):
    """A grid of gains, slew limits and constant errors of both signs, the output starting in the
    middle of its limits. With ki > 0 the output moves every step in the direction of the error
    until it reaches the limit, within distance / min(slew, ki |e|) plus two steps: the slower
    of the two rates is the one the output can at least follow (the integral alone, or the slew
    limit), the first step adds kp e at once, the last step can be a partial one."""

    def test_grid(self):
        lo, hi, start = 80.0, 90.0, 85.0
        cases = 0
        for kp, ki, slew, e in itertools.product((0.0, 0.5, 2.0), (0.0, 0.1, 0.35, 1.0, 5.0),
                                                 (0.5, 1.0), (-6.0, -2.0, -0.5, 0.5, 2.0, 6.0)):
            if kp == 0.0 and ki == 0.0:
                continue
            p = params(kp=kp, ki=ki, slew=slew, lo=lo, hi=hi)
            sp, pv = 20.0 + e, 20.0
            s, r = pid.start(p, sp, pv, start)
            target = hi if e > 0 else lo
            sign = math.copysign(1.0, e)
            outs = [r.out]
            if ki > 0.0:
                limit = abs(target - start) / min(slew, ki * abs(e)) + 2 * DT
                steps = int(math.ceil(limit / DT))
            else:
                steps = 200
            for _ in range(steps):
                s, r = pid.step(s, p, sp, pv, DT)
                outs.append(r.out)
            moves = [(b - a) * sign for a, b in zip(outs, outs[1:])]
            label = "kp %g ki %g slew %g e %g: %s" % (kp, ki, slew, e, outs[:12])
            self.assertTrue(all(m >= -1e-12 for m in moves), "monotonic: " + label)
            self.assertTrue(all(m <= slew * DT + 1e-9 for m in moves), "slew limit: " + label)
            if ki > 0.0:
                reached = next((k for k, v in enumerate(outs) if abs(v - target) < 1e-9), None)
                self.assertIsNotNone(reached, "reaches the limit within %d steps: %s" % (steps, label))
                self.assertTrue(all(m > 1e-12 for m in moves[:reached]),
                                "never stands still before the limit: " + label)
            else:   # P alone: the bumpless start holds kp e in the integral, which is kept
                    # within the limits, so the output stays, or moves towards kp e + that
                want = min(max(kp * e + min(max(start - kp * e, lo), hi), lo), hi)
                self.assertAlmostEqual(outs[-1], want, places=9, msg=label)
            cases += 1
        self.assertGreater(cases, 150)


class FirstOrderPlant:
    """y follows K (u - u0) + y0 with time constant tau, u delayed by `delay` periods: the plant
    model's numbers at its steepest point (3.56 A/A, 1.45 s), plus the polling as dead time."""

    def __init__(self, u0, y0, gain=3.56, tau=1.45, delay=2):
        self.u0, self.y0, self.gain = u0, y0, gain
        self.a = math.exp(-DT / tau)
        self.queue = [u0] * delay
        self.y = y0

    def step(self, u):
        self.queue.append(u)
        u_now = self.queue.pop(0)
        target = self.y0 + self.gain * (u_now - self.u0)
        self.y = target + (self.y - target) * self.a
        return self.y


class ClosedLoop(unittest.TestCase):
    """Set point steps of 2 A and 6 A from 18 A with slew 0.5 and 1 A/s on a first-order plant
    with the model's gain and time constant and a dead time of two periods.

    Limits: the set point is reached (within 0.05 A) within the slew ramp (du / slew) plus
    8 time constants; overshoot under 10 % (SIMC tuning gives a few per cent; 10 % is the usual
    limit); and no wind-up behind the slew limit: in a step where the slew limit holds the
    output back and the integral grows, the integral is no further than the output really sent
    (P + I + D <= out), so the output leaves the slew limit as soon as the terms ask for less."""

    def run_step(self, size, slew):
        u0, y0 = 88.2, 18.0
        p = params(slew=slew, lo=80.0, hi=95.0)
        plant = FirstOrderPlant(u0, y0)
        sp = y0 + size
        s, r = pid.start(p, sp, y0, u0)
        y, ys, previous_i = y0, [], r.i
        ramp = size / 3.56 / slew
        n = int((ramp + 8 * 1.45) / DT)
        for k in range(n):
            s, r = pid.step(s, p, sp, y, DT)
            if r.limited == pid.AT_SLEW and r.i > previous_i + 1e-12:
                self.assertLessEqual(r.p + r.i + r.d, r.out + 1e-9,
                                     "step %d: the integral is ahead of the sent output" % k)
            previous_i = r.i
            y = plant.step(r.out)
            ys.append(y)
        overshoot = max(0.0, (max(ys) - sp) / size * 100.0)
        self.assertLess(overshoot, 10.0, "overshoot %.1f %%" % overshoot)
        self.assertLess(abs(ys[-1] - sp), 0.05, "reached: %.3f of %.1f" % (ys[-1], sp))
        return overshoot

    def test_steps(self):
        for size, slew in itertools.product((2.0, 6.0), (0.5, 1.0)):
            with self.subTest(size=size, slew=slew):
                self.run_step(size, slew)


if __name__ == "__main__":
    unittest.main()
