"""Clocks and signals.

A Signal is a named value that follows its target with a first-order time constant, carries a
little Gaussian noise when read, and can have limits and a quantisation step. Time comes from an
injectable clock, so unit tests can use FakeClock and never sleep.
"""

import math
import random
import time


class SystemClock:
    """Seconds from time.monotonic() (the same time base as the asyncio event loop)."""

    def now(self):
        return time.monotonic()


class FakeClock:
    """A clock that only moves when told to: FakeClock(); clock.advance(0.5)."""

    def __init__(self, start=0.0):
        self.t = float(start)

    def now(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class Signal:
    """One named value.

    value     the true value (no noise). Advanced lazily from the clock on every access.
    target    what the value moves to, with time constant `tau` seconds (0 = at once).
    read()    the value as a sensor would report it: noise, then limits, then quantisation.
    force(v)  external control (control interface, plant model): the value is held at v and
              no longer follows the target until release(). Writes to target are kept.
    """

    def __init__(self, name, value=0.0, tau=0.0, noise=0.0, lo=None, hi=None, step=None,
                 clock=None, rng=None):
        self.name = name
        self.tau = float(tau)
        self.noise = float(noise)
        self.lo = lo
        self.hi = hi
        self.step = step
        self.clock = clock or SystemClock()
        self.rng = rng or random.Random()
        self.external = False
        self._value = self._clamp(float(value))
        self._target = self._value
        self._t = self.clock.now()

    def _clamp(self, v):
        if self.lo is not None and v < self.lo:
            v = float(self.lo)
        if self.hi is not None and v > self.hi:
            v = float(self.hi)
        return v

    def _advance(self):
        now = self.clock.now()
        dt = now - self._t
        self._t = now
        if self.external or dt <= 0 or self._value == self._target:
            return
        if self.tau <= 0:
            self._value = self._target
        else:
            self._value = self._target + (self._value - self._target) * math.exp(-dt / self.tau)

    @property
    def value(self):
        self._advance()
        return self._value

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, v):
        self._advance()
        self._target = self._clamp(float(v))

    def read(self):
        v = self.value
        if self.noise > 0:
            v += self.rng.gauss(0.0, self.noise)
        v = self._clamp(v)
        if self.step:
            v = round(v / self.step) * self.step
        return v

    def force(self, v):
        self._advance()
        self.external = True
        self._value = self._clamp(float(v))

    def release(self):
        self._advance()
        self.external = False

    def state(self):
        return {"value": self.value, "target": self._target, "external": self.external}
