"""The statistics of one channel over one dwell. No EPICS import.

A Channel Access monitor delivers a value when it changes (and when the alarm state changes),
not at a fixed rate. Between two deliveries the PV holds its value: what the scan sees is a step
function of time. The mean of a step function over the dwell is its integral divided by the
dwell, that is the mean of the values weighted by the time each one held inside the dwell. An
arithmetic mean of the deliveries would count a value that held for 0.9 s the same as one that
held for 10 ms, and would make a quiet detector look like a noisy one.

Input: the samples of one dwell [t0, t1], each (arrival time, value or None, reason), sorted by
time, the first one at t0 (the value read fresh when the dwell started). A sample with a value
is valid; a sample without one (INVALID, not connected, no answer) starts an invalid stretch
that lasts until the next sample. Only valid stretches count.
"""
import math

OK, PARTIAL, MISSING = "ok", "partial", "missing"


class Summary:
    """mean, spread (time-weighted standard deviation), n (valid values), minimum, maximum,
    valid (fraction of the dwell with a valid value), status (ok, partial, missing) and reason
    (why values are missing, empty when none are)."""

    __slots__ = ("mean", "spread", "n", "minimum", "maximum", "valid", "status", "reason")

    def __init__(self, mean, spread, n, minimum, maximum, valid, status, reason):
        self.mean, self.spread, self.n = mean, spread, n
        self.minimum, self.maximum = minimum, maximum
        self.valid, self.status, self.reason = valid, status, reason

    def __repr__(self):
        return "Summary(%s)" % ", ".join("%s=%r" % (k, getattr(self, k)) for k in self.__slots__)


def missing(reason):
    nan = float("nan")
    return Summary(nan, nan, 0, nan, nan, 0.0, MISSING, reason)


def summarize(samples, t0, t1):
    if not samples:
        return missing("no value")
    duration = t1 - t0
    weighted = []                       # (value, seconds held inside [t0, t1])
    values, reasons = [], []
    for k, (t, value, reason) in enumerate(samples):
        start = max(t0, min(t1, t))
        end = t1 if k + 1 == len(samples) else max(t0, min(t1, samples[k + 1][0]))
        if value is None:
            if reason and reason not in reasons:
                reasons.append(reason)
            continue
        values.append(value)
        weighted.append((value, max(0.0, end - start)))
    if not values:
        return missing(", ".join(reasons) or "no value")
    held = sum(dt for _, dt in weighted)
    if held > 0:
        mean = sum(v * dt for v, dt in weighted) / held
        spread = math.sqrt(sum((v - mean) ** 2 * dt for v, dt in weighted) / held)
    else:                               # a dwell of 0 s: the values read, all alike
        mean = sum(values) / len(values)
        spread = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    valid = held / duration if duration > 0 else 1.0
    if reasons:
        status = PARTIAL
    else:
        status, valid = OK, 1.0
    return Summary(mean, spread, len(values), min(values), max(values), valid, status,
                   ", ".join(reasons))
