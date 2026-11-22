"""Test C: the discharge current loop closed on the plant model (`make -C emulation test-loop`).

Not part of the system suite (its file name does not start with test_): run.sh runs it with the
plant (MIST2_PLANT=1) and stops what it started. Steps, in this order, on every loop of the
registry whose measurement is the discharge current the plant drives:

  1. the source brought to about 20 A of discharge current in MANUAL (pump, gas, filament,
     discharge supply), from the model's numbers;
  2. MANUAL to PID: bumpless;
  3. a set point step from 20 A to 22 A (the owner's set point): rise time, overshoot, settling
     time, steady-state error;
  4. an emission drift of the plant (-5 %/min for 30 s, then the emission back at once): the
     largest deviation and the error at the end;
  4b. the output maximum lowered under the TDK's set point in PID and restored (a limit change):
     the TDK goes to the new maximum at the slew rate with the flag, and back without a bump;
  5. a set point the supply cannot reach (the REK's current limit lowered under the set point):
     the output ends at its maximum with the flag, holds there, and comes back when the limit
     is restored;
  5b. PID requested with a large error (about 18 A, set point 22 A; review point F8): the TDK
     rises at the slew rate from the first period on and the set point is reached;
  6. a hand-back in closed loop (the REK silent): the filament current stays where it was;
  7. rates: writes per second to the TDK, read-back rates of TDK and REK in MANUAL and in PID.

Pass limits and where they come from: LIMITS below. Every number of the plant is a property of
the MODEL (emulation/sim/config/plant.yaml), not of MIST-2; so are the results.
"""
import threading
import time

import epics
import pytest

import system as S
from system import reg
from mist2sim.control import ControlClient

PLANT = ("plant", 6090)              # the plant's control port (emulation/sim/README.md)
START_A, STEP_A = 20.0, 22.0         # discharge current: start and the owner's set point
LARGE_FROM_A = 18.0                  # PID requested here with the set point at STEP_A (step 5b)
SECONDS = {"step": 20.0, "drift": 30.0, "after_drift": 15.0, "unreachable": 15.0,
           "back": 20.0, "rates": 5.0}

# Pass limits. The model's discharge current answers a filament current step with a gain of
# about 3.3 A/A and a time constant of 1.45 s (plant_step_response.py, 18 A and 24 A points).
LIMITS = {
    # +2 A needs about 0.6 A more filament current; at the slew limit of 1 A/s that alone takes
    # 0.6 s. The design closed-loop time constant is 0.5 s (SIMC): 10 to 90 % in about 2.2 x 0.5
    # s plus the slew time. Limit: 3 s, twice that.
    "rise_s": 3.0,
    # SIMC tuning with tau_c = 0.5 s gives a few per cent; 10 % is the usual limit for it.
    "overshoot_pct": 10.0,
    # within +-0.1 A (5 % of the step): within 4 open-loop time constants (5.8 s), i.e. at least
    # as fast as the plant settles on its own. Limit: 6 s.
    "settling_s": 6.0,
    "band_a": 0.1,
    # PID requested at 18 A with the set point at 22 A: about 1.2 A more filament current, 1.2 s
    # at the slew limit of 1 A/s, then the closed loop (0.5 s) and the plant (1.45 s): into the
    # band within the ramp plus 4 time constants, 7 s; limit 10 s. Overshoot as for the step.
    "large_s": 10.0,
    # steady state: integral action, so the mean error is noise only (REK monitor 12 bit of
    # 24 A, 6 mA per count, and the simulator's noise). Limit: 0.03 A.
    "sse_a": 0.03,
    # MANUAL to PID: in the 5 s after the switch the discharge current stays within +-0.2 A
    # (noise and the small error at the switch) and the first set sent differs from the TDK's
    # set point before by no more than slew x DT (the backstop's step).
    "bump_a": 0.2,
    # drift -5 %/min of the emission: a ramp disturbance; a PI loop follows it with a constant
    # error of about the drift rate over Ki. Largest deviation 0.3 A, at the end of the 30 s
    # within 0.15 A; after the emission returns at once (+ about 2.5 %), back within the band
    # within 6 s.
    "drift_max_a": 0.3,
    "drift_end_a": 0.15,
    # writes per second to the TDK: at most one per period of the writer (DT 0.2 s)
    "writes_per_s": 5.0,
    # read-back rates: the TDK keeps at least 90 % of its MANUAL rate in PID
    "rate_ratio": 0.9,
}


def plant():
    return ControlClient(*PLANT, timeout=5.0)


def valve(label):
    dev = next(d for d in reg.devices.values() if d["class"] == "valve")
    ch = next(c for c in dev["channels"].values() if c.get("label") == label)
    return ch["roles"]["cmd"]


def device_with(role, value_pv):
    return next(d for d, dev in reg.devices.items() if dev.get("roles", {}).get(role) == value_pv)


class Recorder:
    """Every processing of some records: (monotonic time, value), one entry per time stamp of the
    record (a monitor may deliver the same processing twice)."""

    def __init__(self, names):
        self.events = {n: [] for n in names}
        self.stamps = {n: None for n in names}
        self.pvs = [epics.PV(n, form="time", auto_monitor=True, callback=self._cb) for n in names]
        for pv in self.pvs:
            pv.wait_for_connection(5.0)

    def _cb(self, pvname=None, value=None, timestamp=None, **kw):
        if timestamp is not None and timestamp == self.stamps[pvname]:
            return
        self.stamps[pvname] = timestamp
        self.events[pvname].append((time.monotonic(), value))

    def since(self, name, t0, t1=None):
        return [(t, v) for t, v in self.events[name] if t >= t0 and (t1 is None or t <= t1)]

    def rate(self, name, t0, t1):
        return len(self.since(name, t0, t1)) / (t1 - t0)


def mdel_all(names, value):
    for n in names:
        S.put_field(n, "MDEL", value)


def step_metrics(samples, t_step, y0, y1, band):
    """Rise time 10-90 %, overshoot %, settling time into +-band (stays), steady-state error."""
    dy = y1 - y0
    t10 = next(t for t, v in samples if (v - y0) / dy >= 0.1)
    t90 = next(t for t, v in samples if (v - y0) / dy >= 0.9)
    peak = max(v for _, v in samples) if dy > 0 else min(v for _, v in samples)
    overshoot = max(0.0, (peak - y1) / dy * 100.0)
    outside = [t for t, v in samples if abs(v - y1) > band]
    settled = (outside[-1] if outside else t_step) - t_step
    end = samples[-1][0]
    tail = [v for t, v in samples if t >= end - 5.0]
    sse = sum(tail) / len(tail) - y1
    return {"rise_s": t90 - t10, "overshoot_pct": overshoot, "settling_s": settled, "sse_a": sse}


def defaults(prefix):
    """The loop's settings in limits.defaults of its IOC: the table is for those."""
    path = S.REPO / "EPICS" / "ioc" / "iocBoot" / "iocHV" / "limits.defaults"
    out = {}
    for line in path.read_text().splitlines():
        words = line.split()
        if len(words) == 2 and words[0].startswith(prefix + ":"):
            out[words[0]] = float(words[1])
    return out


def put_setting(name, value):
    if "." in name:
        record, fld = name.split(".")
        S.put_field(record, fld, value)
    else:
        S.put(name, value)


def get_setting(name):
    if "." in name:
        record, fld = name.split(".")
        return float(S.field(record, fld))
    return S.get(name)


def test_closed_loop(capsys):
    lp = next(d for d in reg.devices.values() if d["class"] == "loop")
    settings = defaults(lp["loads"][0]["macros"]["P"])
    found = {n: get_setting(n) for n in settings}
    for n, v in settings.items():
        put_setting(n, v)
    try:
        closed_loop(capsys)
    finally:
        for n, v in found.items():
            put_setting(n, v)
        time.sleep(6.0)                 # autosave saves within 5 s: before the emulation stops


def closed_loop(capsys):
    lp = next(d for d in reg.devices.values() if d["class"] == "loop")
    r, m = lp["roles"], lp["loads"][0]["macros"]
    meas, act = m["MEAS"], m["ACT"]
    rek, tdk = device_with("iread", meas), device_with("iset", act)
    R, T = reg.devices[rek]["roles"], reg.devices[tdk]["roles"]
    turbo = next(d for d, dev in reg.devices.items() if dev["class"] == "turbo"
                 and "run_cmd" in dev["roles"] and not dev.get("flags", {}).get("not_installed"))
    mfc = next(d for d, dev in reg.devices.items() if dev["class"] == "mfc")
    rows, table = [], {}
    S.wait_for(lambda: S.get(r["service"]) == 1, 30.0, "the loop service is alive")

    # --- 1. the source in MANUAL --------------------------------------------------------------
    S.put(r["mode_cmd"], 0)
    S.put(reg.role(turbo, "run_cmd"), 1)
    S.put(valve("Foreline Valve"), 1)
    S.put(valve("MFC Shutoff Valve"), 1)
    S.put(reg.role(mfc, "sp_cmd"), 20.0)            # 20 % of 5 sccm: the owner's working point
    S.wait_for(lambda: S.get(reg.role(turbo, "atspeed")) == 1, 150.0, "turbopump at speed")
    S.put(T["vset"], 8.0)                           # filament 8 V: CC below the working point
    S.put(T["iset"], 88.0)
    S.put(T["out_cmd"], 1)
    S.put(R["vset"], 150.0)
    S.put(R["out_cmd"], 1)
    S.wait_for(lambda: S.get(R["status"]) == 1, 5.0, "REK on")
    for _ in range(6):                              # the model's gain is about 3.3 A/A
        time.sleep(8.0)
        i = S.get(meas)
        if abs(i - START_A) < 0.1:
            break
        S.put(T["iset"], round(S.get(T["iset"]) + (START_A - i) / 3.3, 2))
    time.sleep(8.0)
    assert abs(S.get(meas) - START_A) < 0.3, "discharge current near %g A in MANUAL: %s" % (
        START_A, S.describe([meas, T["iset"]]))

    rec = Recorder([meas, act, r["limit"], r["mode"], T["iread"], R["iread"]])
    mdel_all([T["iread"], R["iread"]], -1)          # every processing posted: rates
    try:
        # --- 7a. rates in MANUAL ------------------------------------------------------------
        t0 = time.monotonic()
        time.sleep(SECONDS["rates"])
        t1 = time.monotonic()
        manual = {k: rec.rate(k, t0, t1) for k in (T["iread"], R["iread"])}

        # --- 2. MANUAL to PID ---------------------------------------------------------------
        S.put(r["sp_cmd"], round(S.get(meas), 3))
        before = S.get(act)
        y_before = S.get(meas)
        S.put(r["mode_cmd"], 1)
        S.wait_for(lambda: S.get(r["mode"]) == 1, 1.0, "PID")
        t_pid = time.monotonic()
        time.sleep(5.0)
        sets = [v for _, v in rec.since(act, t_pid)]
        first = sets[0] if sets else before
        bump = max(abs(v - y_before) for _, v in rec.since(meas, t_pid))
        slew_dt = S.get(r["slew"]) * float(m["DT"])
        table["bump"] = (bump, abs(first - before))
        assert abs(first - before) <= slew_dt + 1e-9, "first set %g after %g" % (first, before)
        assert bump <= LIMITS["bump_a"], "discharge moved %.3f A at the switch" % bump

        # --- 3. set point step to 22 A --------------------------------------------------------
        y0 = sum(v for _, v in rec.since(meas, time.monotonic() - 2.0)) / max(
            1, len(rec.since(meas, time.monotonic() - 2.0)))
        t_step = time.monotonic()
        S.put(r["sp_cmd"], STEP_A)
        time.sleep(SECONDS["step"])
        t_end = time.monotonic()
        samples = rec.since(meas, t_step, t_end)
        res = step_metrics(samples, t_step, y0, STEP_A, LIMITS["band_a"])
        table["step"] = res
        writes = rec.rate(act, t_step, t_end)
        pid_rates = {k: rec.rate(k, t_step, t_end) for k in (T["iread"], R["iread"])}

        # --- 4. emission drift ----------------------------------------------------------------
        t_d = time.monotonic()
        plant().set("emission_drift_per_min", -0.05)
        time.sleep(SECONDS["drift"])
        plant().release("emission_drift_per_min")
        t_de = time.monotonic()
        drift = rec.since(meas, t_d, t_de)
        drift_max = max(abs(v - STEP_A) for _, v in drift)
        drift_end = abs(sum(v for t, v in drift if t >= t_de - 3.0) /
                        max(1, len([1 for t, _ in drift if t >= t_de - 3.0])) - STEP_A)
        plant().release("emission_factor")          # the emission back at once
        t_r = time.monotonic()
        time.sleep(SECONDS["after_drift"])
        back = rec.since(meas, t_r)
        outside = [t for t, v in back if abs(v - STEP_A) > LIMITS["band_a"]]
        recover = (outside[-1] - t_r) if outside else 0.0
        table["drift"] = (drift_max, drift_end, recover)

        # --- 4b. the output maximum moved past the TDK's set point and back ------------------------
        out_max = S.get(r["outmax"])
        res = float(m["RES"])
        lowered = round(S.get(act) - 0.5, 2)
        S.put(r["outmax"], lowered)
        time.sleep(5.0)
        lim = (S.get(act), S.get(r["out"]), S.get(r["limit"], as_string=True), S.get(r["mode"]))
        held = [v for _, v in rec.since(meas, time.monotonic() - 1.0)]
        at_restore = sum(held) / len(held)
        S.put(r["outmax"], out_max)
        t_l = time.monotonic()
        time.sleep(15.0)
        after = rec.since(meas, t_l)
        outside = [t for t, v in after if abs(v - STEP_A) > LIMITS["band_a"]]
        table["limit"] = (lowered, lim, at_restore, min(v for _, v in after),
                          (outside[-1] - t_l) if outside else 0.0)

        # --- 5. a set point the supply cannot reach -------------------------------------------
        limit_before = S.get(R["ilimit"])
        t_u = time.monotonic()
        S.put(R["ilimit"], STEP_A - 1.0)            # the REK cannot deliver 22 A any more
        time.sleep(SECONDS["unreachable"])
        at_max = S.get(act)
        flag = S.get(r["limit"], as_string=True)
        sets_u = [v for _, v in rec.since(act, t_u)]
        S.put(R["ilimit"], limit_before)
        t_b = time.monotonic()
        time.sleep(SECONDS["back"])
        back_u = rec.since(meas, t_b)
        # the error changes sign when the measurement passes the set point: from then on the
        # output must leave the maximum at once (no wound-up integral)
        t_cross = next((t for t, v in back_u if v > STEP_A), None)
        left = next((t for t, v in rec.since(act, t_b) if v < out_max - 1e-9), None)
        outside = [t for t, v in back_u if abs(v - STEP_A) > LIMITS["band_a"]]
        settle_back = (outside[-1] - t_b) if outside else 0.0
        table["unreachable"] = (at_max, flag, max(sets_u),
                                None if left is None or t_cross is None else left - t_cross,
                                settle_back)

        # --- 5b. PID requested with a large error ---------------------------------------------
        S.put(r["mode_cmd"], 0)
        S.wait_for(lambda: S.get(r["mode"]) == 0, 1.0, "MANUAL")
        for _ in range(3):                          # the model's gain is about 3.3 A/A
            S.put(T["iset"], round(S.get(T["iset"]) + (LARGE_FROM_A - S.get(meas)) / 3.3, 2))
            time.sleep(8.0)
        y_large = S.get(meas)
        before = S.get(act)
        S.put(r["sp_cmd"], STEP_A)
        time.sleep(1.0)                             # the service has seen the set point
        t_lg = time.monotonic()
        S.put(r["mode_cmd"], 1)
        S.wait_for(lambda: S.get(r["mode"]) == 1, 1.0, "PID")
        time.sleep(SECONDS["step"])
        sets = [v for _, v in rec.since(act, t_lg)]
        first_s = next((t - t_lg for t, v in rec.since(act, t_lg) if v > before + 1e-9), None)
        samples_lg = rec.since(meas, t_lg)
        reached = next((t - t_lg for t, v in samples_lg if v >= STEP_A - LIMITS["band_a"]), None)
        peak = max(v for _, v in samples_lg)
        table["large"] = (y_large, before, first_s, reached,
                          max(0.0, (peak - STEP_A) / (STEP_A - y_large) * 100.0),
                          max(b - a for a, b in zip([before] + sets, sets)) if sets else 0.0)

        # --- 6. hand-back in closed loop ------------------------------------------------------
        # The REK silent: its monitors (10 Hz) or its status (the permit, 1 Hz) turn INVALID
        # first, depending on where the polls stand; both are R4 b. Until then the loop
        # regulates; from the hand-back on the TDK stays where it is.
        sim, unit = reg.sim_of(R["vset"])
        n_rek = next(i for i, c in enumerate(("C1", "C2", "C3"), 1) if m[c] == R["status"])
        with S.fault(sim, "silent", unit):
            S.wait_for(lambda: S.get(r["mode"]) == 0, 2.0, "hand-back")
            why = S.get(r["reason"], as_string=True)
            time.sleep(float(m["DT"]) + 0.1)        # a set sent just before may still complete
            fil_before = S.get(act)
            iread_before = S.get(T["iread"])
            time.sleep(5.0)
            fil_after = S.get(act)
            iread_after = S.get(T["iread"])
        table["handback"] = (why, fil_before, fil_after, iread_before, iread_after)
    finally:
        S.put(r["mode_cmd"], 0)
        mdel_all([T["iread"], R["iread"]], 0)
        for name in ("emission_drift_per_min", "emission_factor"):
            plant().release(name)

    # --- the table ------------------------------------------------------------------------------
    st = table["step"]
    lines = [
        "| Closed loop on the plant model (LOOP-DIS) | Result | Pass limit |",
        "|---|---|---|",
        "| MANUAL to PID: discharge moved / first set step | %.3f A / %.3f A | %.2f A / %.2f A |"
        % (table["bump"][0], table["bump"][1], LIMITS["bump_a"], slew_dt),
        "| Step %.1f to %.1f A: rise time 10-90 %% | %.2f s | %.1f s |" % (y0, STEP_A, st["rise_s"], LIMITS["rise_s"]),
        "| overshoot | %.1f %% | %.0f %% |" % (st["overshoot_pct"], LIMITS["overshoot_pct"]),
        "| settling time into +-%.2f A | %.2f s | %.1f s |" % (LIMITS["band_a"], st["settling_s"], LIMITS["settling_s"]),
        "| steady-state error (mean of the last 5 s) | %+.4f A | +-%.2f A |" % (st["sse_a"], LIMITS["sse_a"]),
        "| Emission drift -5 %%/min, 30 s: largest deviation | %.3f A | %.2f A |" % (table["drift"][0], LIMITS["drift_max_a"]),
        "| deviation at the end of the drift | %.3f A | %.2f A |" % (table["drift"][1], LIMITS["drift_end_a"]),
        "| emission back at once: back into the band after | %.2f s | %.1f s |" % (table["drift"][2], LIMITS["settling_s"]),
        "| Output maximum lowered to %.2f A in PID: TDK set / output:get / flag / mode | %.2f A / %.2f A / %s / %s | %.2f A / the same / at maximum / PID |"
        % (table["limit"][0], table["limit"][1][0], table["limit"][1][1], table["limit"][1][2],
           "PID" if table["limit"][1][3] else "MANUAL", table["limit"][0]),
        "| maximum restored at %.3f A: lowest discharge current after / settled after | %.3f A / %.2f s | not below %.3f A (no bump down) / %.1f s |"
        % (table["limit"][2], table["limit"][3], table["limit"][4], table["limit"][2] - LIMITS["band_a"],
           LIMITS["settling_s"] * 2),
        "| Unreachable (REK limit %.0f A): TDK set / flag / highest set | %.2f A / %s / %.2f A | %.2f A / at maximum / %.2f A |"
        % (STEP_A - 1.0, table["unreachable"][0], table["unreachable"][1], table["unreachable"][2], out_max, out_max),
        "| limit restored: leaves the maximum after the error changed sign / settles after | %s / %.2f s | 2 periods + 0.5 s / %.1f s |"
        % ("-" if table["unreachable"][3] is None else "%.2f s" % table["unreachable"][3],
           table["unreachable"][4], LIMITS["settling_s"] * 2),
        "| PID requested at %.2f A, set point %.0f A (TDK %.2f A): TDK first raised after / band reached after | %s / %s | 2 periods / %.0f s |"
        % (table["large"][0], STEP_A, table["large"][1],
           "-" if table["large"][2] is None else "%.2f s" % table["large"][2],
           "-" if table["large"][3] is None else "%.2f s" % table["large"][3], LIMITS["large_s"]),
        "| overshoot / largest TDK step | %.1f %% / %.3f A | %.0f %% / %.2f A (slew x DT) |"
        % (table["large"][4], table["large"][5], LIMITS["overshoot_pct"], slew_dt),
        "| Hand-back in closed loop (REK silent): reason / TDK set at the hand-back, 5 s later | %s / %.3f, %.3f A | measurement or permit %d no data / the same |"
        % (table["handback"][0], table["handback"][1], table["handback"][2], n_rek),
        "| TDK current read-back at the hand-back, 5 s later | %.2f, %.2f A | within 0.5 A (noise) |"
        % (table["handback"][3], table["handback"][4]),
        "| Writes per second to the TDK in PID (during the step) | %.2f | at most %.0f |" % (writes, LIMITS["writes_per_s"]),
        "| TDK current read-back rate, MANUAL / PID | %.2f / %.2f per s | PID >= %.0f %% of MANUAL |"
        % (manual[T["iread"]], pid_rates[T["iread"]], LIMITS["rate_ratio"] * 100),
        "| REK current read-back rate, MANUAL / PID | %.2f / %.2f per s | (reported) |"
        % (manual[R["iread"]], pid_rates[R["iread"]]),
    ]
    text = "\n".join(lines)
    S.report(text, capsys)
    (S.BUILD / "loop-plant.md").write_text(text + "\n")

    assert st["rise_s"] <= LIMITS["rise_s"]
    assert st["overshoot_pct"] <= LIMITS["overshoot_pct"]
    assert st["settling_s"] <= LIMITS["settling_s"]
    assert abs(st["sse_a"]) <= LIMITS["sse_a"]
    assert table["drift"][0] <= LIMITS["drift_max_a"]
    assert table["drift"][1] <= LIMITS["drift_end_a"]
    assert table["drift"][2] <= LIMITS["settling_s"]
    lowered, (tdk_set, shown, flag, mode), at_restore, lowest, settled = table["limit"]
    assert abs(tdk_set - lowered) <= res and abs(shown - tdk_set) <= res and flag == "at maximum" and mode == 1
    assert lowest >= at_restore - LIMITS["band_a"], "a bump down when the maximum is restored"
    assert settled <= 2 * LIMITS["settling_s"]
    res = float(m["RES"])               # the last step to the maximum is not sent if smaller
    assert out_max - res <= table["unreachable"][0] <= out_max and table["unreachable"][1] == "at maximum"
    assert table["unreachable"][2] <= out_max + 1e-9, "no runaway beyond the maximum"
    assert table["unreachable"][3] is not None and table["unreachable"][3] <= 2 * float(m["DT"]) + 0.5
    assert table["unreachable"][4] <= 2 * LIMITS["settling_s"]
    y_large, _, first_s, reached, over_lg, step_lg = table["large"]
    assert y_large < STEP_A - 3.0, "a large error at the switch: %.2f A" % y_large
    assert first_s is not None and first_s <= 2 * float(m["DT"]) + 0.5, "the TDK moves at once"
    assert reached is not None and reached <= LIMITS["large_s"]
    assert over_lg <= LIMITS["overshoot_pct"]
    assert step_lg <= slew_dt + 1e-9
    assert table["handback"][0] in ("measurement no data", "permit %d no data" % n_rek)
    assert table["handback"][1] == table["handback"][2], "the filament set point stayed"
    assert abs(table["handback"][3] - table["handback"][4]) <= 0.5
    assert writes <= LIMITS["writes_per_s"]
    assert pid_rates[T["iread"]] >= LIMITS["rate_ratio"] * manual[T["iread"]]
