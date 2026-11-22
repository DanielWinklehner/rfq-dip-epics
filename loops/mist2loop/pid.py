"""The PID algorithm of the MIST-2 loops. No EPICS: state and inputs in, output and new state out.

    u = Kp*e + I - Kd*d(pv_f)/dt        e = sp - pv        I += Ki*e*dt

Parallel form. The derivative acts on the filtered measurement pv_f, not on the error, so a set
point step does not kick the output. The output is limited to [out_min, out_max] and its rate to
`slew` per second, in this order; what step() returns is what the actuator is to get.

Anti-windup: conditional integration. The integral takes the step Ki*e*dt only as far as the
output stays within [out_min, out_max], and while the slew limit holds the output back in the
direction of the step, only as far as the output really moves: P + I + D then equals the output
sent, so the output moves by the full slew room every step (it never stands still while the
error persists) and the integral is never ahead of it. The integral itself stays within
[out_min, out_max]. So after a long time at a limit, output or slew, the output leaves it as
soon as the terms ask for less.

Bumpless: start() sets the integral so that the output equals the actuator's present value. A
change of Kp or Kd moves the integral by the change of its term, so that the output does not
jump. A change of the set point moves the output by Kp times the change, a change of a limit
moves it towards the new limit; both through the slew limit.

Usage (also in a notebook):

    p = Params(kp=0.5, ki=0.35, kd=0, tf=0.2, out_min=80, out_max=90, slew=1, dt_max=0.6)
    s, r = start(p, sp=22, pv=21.5, out_now=89.0)      # r.out == 89.0
    s, r = step(s, p, sp=22, pv=21.6, dt=0.2)
"""
from dataclasses import dataclass, replace

FREE, AT_MIN, AT_MAX, AT_SLEW = 0, 1, 2, 3       # which limit holds the output back


@dataclass(frozen=True)
class Params:
    kp: float           # output units per measurement unit
    ki: float           # output units per measurement unit and second
    kd: float           # output units per (measurement unit per second)
    tf: float           # time constant of the derivative's filter, s; 0: no filter
    out_min: float      # output limits, output units
    out_max: float
    slew: float         # largest change of the output, output units per second
    dt_max: float       # longest time step that is integrated, s


@dataclass(frozen=True)
class State:
    out: float          # last output
    integral: float     # the I term, output units
    pv_f: float         # filtered measurement
    d_rate: float       # d(pv_f)/dt of the last step
    kp: float           # gains of the last step: a change is compensated in the integral
    kd: float
    limited: int        # which limit held the last output back


@dataclass(frozen=True)
class Result:
    out: float          # the output: what the actuator is to be set to
    error: float        # sp - pv
    p: float            # the three terms; p + i + d is the output before the limits
    i: float
    d: float
    limited: int        # FREE, or which limit holds the output back


def _clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def _result(s, e):
    return Result(s.out, e, s.kp * e, s.integral, -s.kd * s.d_rate, s.limited)


def _limit(last, p, raw, dt):
    """The output limits, then the slew limit from the last output. Returns (out, slewed)."""
    target = _clamp(raw, p.out_min, p.out_max)
    room = p.slew * dt
    if target > last + room:
        return last + room, True
    if target < last - room:
        return last - room, True
    return target, False


def start(p, sp, pv, out_now):
    """Start from the actuator's present value: the first output is out_now."""
    s = State(out=out_now, integral=out_now - p.kp * (sp - pv), pv_f=pv, d_rate=0.0,
              kp=p.kp, kd=p.kd, limited=FREE)
    return s, _result(s, sp - pv)


def step(s, p, sp, pv, dt):
    """One step after dt seconds. dt <= 0 (or not a number): nothing changes, the last output is
    returned. dt longer than dt_max: integrated as dt_max, and the derivative's filter starts
    again from pv. Returns (new state, result)."""
    e = sp - pv
    if dt > p.dt_max:                   # a long gap: integrate at most dt_max, and restart the
        dt = p.dt_max                   # filter instead of differencing over the gap
        s = replace(s, pv_f=pv, d_rate=0.0)
    if not dt > 0.0:
        return s, _result(s, e)

    # A gain change moves the integral by the change of its term: no jump of the output.
    integral0 = s.integral + (s.kp - p.kp) * e + (p.kd - s.kd) * s.d_rate

    # Derivative of the measurement through a first-order filter (backward Euler: stable for
    # every dt and tf).
    pv_f = s.pv_f + (pv - s.pv_f) * dt / (max(p.tf, 0.0) + dt)
    d_rate = (pv_f - s.pv_f) / dt

    # Integrate, but only as far as the output stays within its limits ...
    pterm, dterm = p.kp * e, -p.kd * d_rate
    inc = p.ki * e * dt
    wanted = pterm + integral0 + inc + dterm
    integral = integral0 + inc
    if inc > 0.0 and wanted > p.out_max:
        integral = max(integral0, p.out_max - pterm - dterm)
    if inc < 0.0 and wanted < p.out_min:
        integral = min(integral0, p.out_min - pterm - dterm)
    integral = _clamp(integral, p.out_min, p.out_max)
    out, slewed = _limit(s.out, p, pterm + integral + dterm, dt)
    # ... and while the slew limit holds the output back in its direction, only as far as the
    # output really moves: between no step and the full step, the integral that makes P + I + D
    # equal the output sent. (With P alone past the slew room it does not grow at all.)
    if slewed and (out - s.out) * inc > 0.0:
        lo, hi = sorted((integral0, integral))
        integral = _clamp(_clamp(out - pterm - dterm, lo, hi), p.out_min, p.out_max)
        out, _ = _limit(s.out, p, pterm + integral + dterm, dt)

    if slewed:
        limited = AT_SLEW
    elif wanted > p.out_max and out >= p.out_max:
        limited = AT_MAX
    elif wanted < p.out_min and out <= p.out_min:
        limited = AT_MIN
    else:
        limited = FREE
    s = State(out=out, integral=integral, pv_f=pv_f, d_rate=d_rate, kp=p.kp, kd=p.kd,
              limited=limited)
    return s, _result(s, e)
