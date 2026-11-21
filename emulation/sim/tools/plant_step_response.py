#!/usr/bin/env python3
"""Step responses of the plant MODEL, for tuning the first control loop (discharge current
through the filament heating current, plan/controls.yaml software.loops).

    python3 emulation/sim/tools/plant_step_response.py [--config plant.yaml] [--step 1.0]

Runs the pure model (mist2sim.plant.model), no simulator, no socket. Prints, at three working
points, the steady-state gain, dead time and time constant of the discharge current after a step
of the filament current, and the same for a gas flow step on the source pressure.
"""

import argparse
import math
import os
import sys

SIM = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, SIM)

from mist2sim.core import load_config  # noqa: E402
from mist2sim.devices.tdk_genesys import TdkGenesys  # noqa: E402
from mist2sim.plant.model import PlantModel, idle_inputs, load_params  # noqa: E402

DT = 0.005
BASE = dict(idle_inputs(), rek_vset=100.0, rek_iset=24.0, rek_on=1, gas_flow=5.0,
            shutoff_open=1, foreline_open=1, turbo1_speed=1, turbo2_speed=1)
TARGETS_A = (5.0, 10.0, 15.0)      # discharge currents of the three working points


def steady(m, inputs, seconds=40.0):
    return m.settle(m.initial_state(), inputs, seconds, dt=0.05)


def filament_current_for(m, target):
    """Filament current at which the discharge settles at `target` A (bisection)."""
    lo, hi = 0.0, 300.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if steady(m, dict(BASE, filament_current=mid))[1]["discharge_current"] < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def step_response(m, state, inputs, key, seconds):
    """Apply `inputs` from `state`; return (times, values of out[key]) and the final value."""
    ts, ys = [], []
    t = 0.0
    for _ in range(int(round(seconds / DT))):
        state, out = m.step(state, inputs, DT)
        t += DT
        ts.append(t)
        ys.append(out[key])
    return ts, ys


def first_order_fit(ts, ys, y0):
    """Gain, dead time and time constant by the two-point method (28.3 % and 63.2 % of the
    final change, Smith): tau = 1.5 (t63 - t28), dead time = t63 - tau."""
    y_end = ys[-1]
    dy = y_end - y0

    def crossing(frac):
        level = y0 + frac * dy
        for t, y in zip(ts, ys):
            if (y - level) * math.copysign(1.0, dy) >= 0:
                return t
        return float("nan")

    t28, t63 = crossing(0.283), crossing(0.632)
    tau = 1.5 * (t63 - t28)
    return dy, max(0.0, t63 - tau), tau, t63


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", default=os.path.join(SIM, "config", "plant.yaml"))
    ap.add_argument("--step", type=float, default=1.0, help="filament current step, A")
    ap.add_argument("--gas-step", type=float, default=1.0, help="gas flow step, sccm")
    args = ap.parse_args(argv)
    params = load_params(args.config)
    m = PlantModel(params)

    print("PLANT MODEL STEP RESPONSES (%s)" % os.path.relpath(args.config))
    print()
    print("Every number below is a property of the MODEL, computed from the parameters in the")
    print("configuration file. None of them is measured on MIST-2. Tune a loop on them to test it")
    print("in the emulation; on the machine, measure the step responses again.")
    print()
    print("Working point: discharge supply %.0f V (limit %.0f A), gas %.1f sccm into the source,"
          % (BASE["rek_vset"], BASE["rek_iset"], BASE["gas_flow"]))
    print("both turbopumps at speed, extraction off. Model parameter filament_tau_s = %g s."
          % params["filament_tau_s"])
    print()

    print("1. Filament current step +%g A -> discharge current (REK current)" % args.step)
    print()
    print("   %-9s %-9s %-9s %-10s %-12s %-9s %-9s" % ("I_dis", "I_fil", "T_fil", "regime",
                                                       "gain", "dead", "tau"))
    print("   %-9s %-9s %-9s %-10s %-12s %-9s %-9s" % ("A", "A", "K", "", "A/A", "s", "s"))
    for target in TARGETS_A:
        i_fil = filament_current_for(m, target)
        inputs = dict(BASE, filament_current=i_fil)
        state, before = steady(m, inputs)
        ts, ys = step_response(m, state, dict(inputs, filament_current=i_fil + args.step),
                               "discharge_current", 15.0)
        dy, dead, tau, _ = first_order_fit(ts, ys, before["discharge_current"])
        regime = "emission" if before["discharge_current"] > 0.9 * before["emission"] else "mixed"
        print("   %-9.2f %-9.1f %-9.0f %-10s %-12.3f %-9.3f %-9.2f" % (
            before["discharge_current"], i_fil, before["filament_temperature"], regime,
            dy / args.step, dead, tau))
    print()
    print("   regime: emission = the discharge carries what the filament emits (dI_dis/dI_fil")
    print("   steep), mixed = the plasma limit (voltage, pressure) takes over and the gain falls.")
    print("   The gain rises steeply with the working point: Richardson's law is exponential in T.")
    print("   tau is longer than filament_tau_s because the filament resistance rises with T at")
    print("   constant current (model: tau / (1 - %g / 4) = %.2f s for small steps)."
          % (params["filament_r_exponent"], params["filament_tau_s"] / (1 - params["filament_r_exponent"] / 4)))
    print()

    print("2. Gas flow step +%g sccm -> source pressure (aim gauge) and discharge current" % args.gas_step)
    print()
    i_fil = filament_current_for(m, TARGETS_A[1])
    print("   %-9s %-14s %-9s %-9s %-16s" % ("gas", "gain", "dead", "tau", "discharge gain"))
    print("   %-9s %-14s %-9s %-9s %-16s" % ("sccm", "torr/sccm", "s", "s", "A/sccm"))
    for gas in (2.0, 5.0, 10.0):
        inputs = dict(BASE, filament_current=i_fil, gas_flow=gas)
        state, before = steady(m, inputs)
        stepped = dict(inputs, gas_flow=gas + args.gas_step)
        ts, ys = step_response(m, state, stepped, "source_pressure", 10.0)
        dy, dead, tau, _ = first_order_fit(ts, ys, before["source_pressure"])
        _, after = m.settle(state, stepped, 30.0, dt=0.05)
        print("   %-9.1f %-14.3e %-9.3f %-9.2f %-16.3f" % (
            gas, dy / args.gas_step, dead, tau,
            (after["discharge_current"] - before["discharge_current"]) / args.gas_step))
    print()
    print("   at filament current %.1f A. The source pressure lags by the source vessel"
          % i_fil)
    print("   (source_volume_l / pumping speed); the plasma chamber pressure, which sets the")
    print("   discharge, lags it by chamber_volume_l / aperture_conductance_l_s more.")
    print()

    tdk_tau = TdkGenesys.OPTIONS["tau_s"]
    mfc_tau = None
    for e in load_config(os.path.join(SIM, "config", "rack.yaml")):
        if e["type"] == "mks_rs485":
            mfc_tau = e["options"]["units"][0].get("tau_s")
    print("3. Not in the numbers above, but in the emulated loop (simulator settings, not MIST-2):")
    print("   TDK simulator: the measured current follows the programmed one with tau %g s." % tdk_tau)
    print("   MFC simulator: the flow follows the set point with tau %s s." % mfc_tau)
    print("   Plant process: one model step every 0.1 s (rate_hz 10) adds up to 0.1 s of delay.")
    print("   IOC polling of the REK and the TDK at 10 Hz adds up to 0.1 s more.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
