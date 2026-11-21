#!/usr/bin/env python3
"""Step responses of the plant MODEL, for tuning the first control loop (discharge current
through the filament heating current, plan/controls.yaml software.loops).

    python3 emulation/sim/tools/plant_step_response.py [--config plant.yaml] [--step 0.5]

Runs the pure model (mist2sim.plant.model), no simulator, no socket. Prints the calibration
from the owner's working point, then the steady-state gain, dead time and time constant of the
discharge current after a step of the filament current at the working point and at two points
below it, and the same for a gas flow step on the cross pressure.
"""

import argparse
import math
import os
import sys

SIM = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, SIM)

from mist2sim.core import load_config  # noqa: E402
from mist2sim.devices.tdk_genesys import TdkGenesys  # noqa: E402
from mist2sim.plant.model import PlantModel, load_params, working_point_inputs  # noqa: E402

DT = 0.005
BELOW_A = (18.0, 12.0)      # discharge currents of the two points below the working point


def steady(m, inputs, seconds=40.0):
    return m.settle(m.initial_state(), inputs, seconds, dt=0.05)


def filament_current_for(m, base, target):
    """Filament current at which the discharge settles at `target` A (bisection)."""
    lo, hi = 0.0, 300.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if steady(m, dict(base, filament_current=mid))[1]["discharge_current"] < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def response(m, state, inputs, key, seconds):
    ts, ys, t = [], [], 0.0
    for _ in range(int(round(seconds / DT))):
        state, out = m.step(state, inputs, DT)
        t += DT
        ts.append(t)
        ys.append(out[key])
    return ts, ys


def first_order_fit(ts, ys, y0):
    """Change, dead time and time constant by the two-point method (28.3 % and 63.2 % of the
    final change, Smith): tau = 1.5 (t63 - t28), dead time = t63 - tau."""
    dy = ys[-1] - y0
    if abs(dy) < 1e-12 * max(1.0, abs(y0)):
        return 0.0, float("nan"), float("nan")

    def crossing(frac):
        level = y0 + frac * dy
        for t, y in zip(ts, ys):
            if (y - level) * math.copysign(1.0, dy) >= 0:
                return t
        return float("nan")

    t28, t63 = crossing(0.283), crossing(0.632)
    tau = 1.5 * (t63 - t28)
    return dy, max(0.0, t63 - tau), tau


def fmt(x, spec):
    return "-" if isinstance(x, float) and math.isnan(x) else spec % x


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", default=os.path.join(SIM, "config", "plant.yaml"))
    ap.add_argument("--step", type=float, default=0.5, help="filament current step, A")
    ap.add_argument("--gas-step", type=float, default=0.2, help="gas flow step, sccm")
    args = ap.parse_args(argv)
    p = load_params(args.config)
    m = PlantModel(p)
    d = m.derived
    wp = working_point_inputs(p)

    print("PLANT MODEL STEP RESPONSES (%s)" % os.path.relpath(args.config))
    print()
    print("Filament and discharge are calibrated to ONE working point the owner gave from memory")
    print("(2026-11-21) and reproduce it; every slope, gain and time constant below is a property")
    print("of the MODEL, not measured on MIST-2. Tune a loop on them to test it in the emulation;")
    print("on the machine, measure the step responses again.")
    print()
    _, o = m.settle(m.initial_state(), wp, 60.0, dt=0.02)
    print("Working point (owner -> model):")
    print("   filament   %4.1f V at %5.1f A   ->  %5.2f V, %5.0f W, T %4.0f K" % (
        p["wp_filament_voltage_v"], p["wp_filament_current_a"], o["filament_voltage"],
        o["filament_power"], o["filament_temperature"]))
    print("   discharge  %4.0f V at %5.1f A   ->  %5.1f V, %5.2f A (REK limit %g A = its full scale)" % (
        p["wp_discharge_voltage_v"], p["wp_discharge_current_a"], o["discharge_voltage"],
        o["rek_current"], wp["rek_iset"]))
    print("Derived: hot filament %.4f ohm, %.0f K, area %.1f cm2 (a tungsten wire of %.2f mm x %.1f cm),"
          % (d["filament_r_hot_ohm"], d["filament_t_hot_k"], d["filament_area_cm2"],
             d["wire_diameter_mm"], d["wire_length_cm"]))
    print("   emission %.1f A, plasma limit %.0f A at 150 V, plasma chamber %.1e torr."
          % (d["emission_a"], d["plasma_limit_a"], d["chamber_wp_torr"]))
    print()
    lo, hi = p["wp_cross_reading_low_torr"], p["wp_cross_reading_high_torr"]
    pred = d["aim_wp_reading_torr"]
    print("Pressure in the cross at the working point: PREDICTED from the pump's data, not calibrated")
    print("   pumping speed %.0f l/s N2 (data sheet TURBOVAC 1000 C, 250 ISO-K; the owner thinks it"
          % p["turbo_speed_n2_l_s"])
    print("   is that pump) x %.3f (H2/N2, estimate) = %.0f l/s H2"
          % (p["turbo_h2_n2_ratio"], d["turbo_speed_l_s"]))
    print("   %.1f sccm H2 -> true pressure %.2e torr -> nAIM reading %.2e torr (x %.2f for H2);"
          % (p["wp_gas_sccm"], d["cross_wp_torr"], pred, p["aim_h2_factor"]))
    print("   the model in operation: nAIM %.2e torr, APG %.0e (its floor)"
          % (o["aim_reading"], o["apg_reading"]))
    if lo <= pred <= hi:
        verdict = "INSIDE the range"
    elif pred < lo:
        verdict = "BELOW the range, a factor %.1f under its low end" % (lo / pred)
    else:
        verdict = "ABOVE the range, a factor %.1f over its high end" % (pred / hi)
    print("   owner's range %.0e to %.0e torr: the prediction is %s." % (lo, hi, verdict))
    if not lo <= pred <= hi:
        print("   Possible reasons, none chosen: the gauge's calibration for hydrogen (without the")
        print("   H2 factor the reading would be %.1e torr); the gauge on a side flange away from the"
              % d["cross_wp_torr"])
        print("   pump; a conductance between pump and chamber (flange, valve, screen) that lowers the")
        print("   effective speed; the remembered flow (20 % of 5 sccm); a different pump or speed;")
        print("   the base pressure (a free choice, %.0e torr reading)." % p["cross_base_reading_torr"])
    print()

    print("1. Filament current step %+g A -> discharge current (REK current limit at %g A)" % (
        args.step, wp["rek_iset"]))
    print()
    print("   %-12s %-9s %-9s %-7s %-9s %-10s %-8s %-8s" % (
        "point", "I_dis", "I_fil", "T_fil", "step", "gain", "dead", "tau"))
    print("   %-12s %-9s %-9s %-7s %-9s %-10s %-8s %-8s" % ("", "A", "A", "K", "A", "A/A", "s", "s"))
    rows = [("working pt", p["wp_filament_current_a"], (-args.step, +args.step))]
    for target in BELOW_A:
        rows.append(("below", filament_current_for(m, wp, target), (+args.step,)))
    for name, i_fil, steps in rows:
        inputs = dict(wp, filament_current=i_fil)
        state, before = steady(m, inputs)
        for step in steps:
            ts, ys = response(m, state, dict(inputs, filament_current=i_fil + step),
                              "discharge_current", 15.0)
            dy, dead, tau = first_order_fit(ts, ys, before["discharge_current"])
            print("   %-12s %-9.2f %-9.2f %-7.0f %-9s %-10.3f %-8s %-8s" % (
                name, before["discharge_current"], i_fil, before["filament_temperature"],
                "%+g" % step, dy / step, fmt(dead, "%.3f"), fmt(tau, "%.2f")))
    print()
    print("   At the working point the REK is at its current limit (24 A, the full scale of the")
    print("   REK150-24): a step up cannot raise the current, the supply goes into constant current")
    print("   and its voltage falls. A discharge current loop around this point only acts downward;")
    print("   it needs a set point below 24 A or a larger supply (REK150-55, plan/controls.yaml).")
    print("   Below the limit the discharge is emission limited and the gain rises steeply with the")
    print("   working point (Richardson's law). tau is longer than filament_tau_s = %g s because the"
          % p["filament_tau_s"])
    print("   filament resistance rises with T at constant current (model: tau / (1 - %g / 4) = %.2f s)."
          % (p["filament_r_exponent"], p["filament_tau_s"] / (1 - p["filament_r_exponent"] / 4)))
    print()

    print("2. Gas flow step %+g sccm -> cross pressure (nAIM reading) and discharge current" % args.gas_step)
    print()
    print("   %-9s %-14s %-9s %-9s %-16s" % ("gas", "gain", "dead", "tau", "discharge gain"))
    print("   %-9s %-14s %-9s %-9s %-16s" % ("sccm", "torr/sccm", "s", "s", "A/sccm"))
    below = filament_current_for(m, wp, BELOW_A[0])
    for gas in (0.5, 1.0, 2.0):
        inputs = dict(wp, filament_current=below, gas_flow=gas)
        state, before = steady(m, inputs)
        stepped = dict(inputs, gas_flow=gas + args.gas_step)
        ts, ys = response(m, state, stepped, "aim_reading", 5.0)
        dy, dead, tau = first_order_fit(ts, ys, before["aim_reading"])
        _, after = m.settle(state, stepped, 30.0, dt=0.05)
        print("   %-9.2f %-14.3e %-9s %-9s %-16.3f" % (
            gas, dy / args.gas_step, fmt(dead, "%.3f"), fmt(tau, "%.3f"),
            (after["discharge_current"] - before["discharge_current"]) / args.gas_step))
    print()
    print("   at filament current %.2f A (discharge %.0f A). The cross pressure lags by" % (below, BELOW_A[0]))
    print("   cross_volume_l / pumping speed; the plasma chamber, which sets the discharge, lags by")
    print("   chamber_volume_l / aperture_conductance_l_s.")
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
