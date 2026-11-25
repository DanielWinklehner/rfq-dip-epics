"""Edwards TIC controller (Turbo Instrument Controller), RS-232 (tasks T29, T31, T32).

Source: Edwards "Turbo Instrument Controller (TIC) Serial Communications", D397-30-880 Issue H
(2012), for all seven TIC variants:
  1.2    a query "?V<obj>" or "?S<obj>", a command "!C<obj> <data>" or "!S<obj> <data>", every
         message ends with CR; characters outside start ("?", "!") and end (CR) are ignored
  1.6    replies "=V<obj> <data>", "=S<obj> <data>", or the response code "*V<obj> <r>",
         "*S<obj> <r>", "*C<obj> <r>"; fields separated by ";" (1.5)
  Table 1  902 ?V system status (fields per variant: TC T;B;R1;R2;R3;alert;priority,
         TIC T;B;G1;G2;G3;R1;R2;R3;alert;priority, IC G1;G2;G3;R1;R2;R3;alert;priority,
         IC6 G1..G6;R1..R6;alert;priority), ?S identity (1.6.2.2: "TIC;Dxxxxxxxx;serial;PIC")
         904 turbo pump ?V "state;alert;priority" (1.6.2.3), ?S 3 pump type "3;type"
         905 turbo speed ?V "value;alert;priority", 0.0 - 110.0 %
         910 backing pump ?V "state;alert;priority" (state 0 - 4), ?S 3 pump type
         913, 914, 915 gauges 1-3 (934-936 gauges 4-6 of an IC6) ?V
         "value;units type;state;alert;priority"
  1.7.1  Table 3 response codes, 1.7.4 units types (59 pressure, pascal only; 66 voltage;
         81 percent), 1.7.6 states 0-4, 1.7.7 gauge states, 1.7.8 pump states, 1.7.11 pump types
  1.4    basic messages answered in less than 100 ms

Commands (task T32), "!C<obj> <d>" answered "*C<obj> <r>" (Table 3, 0 = no error):
  904 turbo pump and 910 backing pump, "Turn pump on/off", On = 1, Off = 0 (Table 1);
  913-915 gauges 1-3, the command list 1.7.5: Gauge Off = 0, Gauge On = 1.
Seen on the lab's controller (STATUS.md, "Seen on hardware, lab session", 2026-11-25), and so
done here: "!C910 1", "!C910 0", "!C904 1", "!C904 0" each answered "*C9xx 0" after 19 ms (the
turnaround); the backing pump in its new state at the next query (4 after 32 ms, 0 after 25 ms);
the turbopump still in its old state 32 and 51 ms after its command; the backing pump 0 -> 4 and
4 -> 0 with no state between; the turbopump 0 -> 5 "Accelerating" -> 4 "Running" from above 50 %,
100 % after 120 s; down: 7 "Braking" from the first sample to 0.3 %, then 0, 105 s with the
backing pump switched off right after the stop; with the backing pump left on: 49 % after 40 s,
16 % after 107 s, 0.7 % after 5 minutes, still Braking (the lead's message of 2026-11-25). The
speed follows these curves (options turbo_runup, turbo_rundown_backing_off,
turbo_rundown_backing_on: points [seconds, %] as seen); a change of the backing pump while the
turbopump brakes moves it onto the other curve at its present speed.
The gauge on socket 2 (an AIM) switched on at the TIC's panel (seen): 5 "Off" to 11 "On" in one
step at a 1 s scan, then one unchanging value for 146 s before the value followed the pressure
(standing_s); switched off at the panel: 11 to 5 in one step.

Not in the manual, so options or choices of this simulator (named so in TIC.md):
  - which objects each variant has: TC no gauges, IC and IC6 no pumps (from the variant
    structures of object 902 and the product names); `absent_code`: the response code of a
    query to an object the variant does not have (default 2, "Invalid query/command")
  - the value of a gauge that is not on: 9.9e9 (the example of object 940 in Table 1, "gauge 5
    not ON (e.g. OFF, error, striking etc)"); the number format "%.4e" (that example)
  - the value of a gauge in voltage mode (units 66): 0.000 - 11.000 V, here a fixed 6.546 (the
    example of object 940)
  - a command other than "!C" to 904, 910 or a gauge object, or a setup ("!S"), is not executed:
    it is counted (signal `commands`, which counts every "!" message) and answered
    "*<type><obj> 1"; a "!C" with a value other than 0 or 1 is answered "*C<obj> 4" (Table 3,
    parameter out of range) and not executed
  - ASSUMED (not tried on the controller): `turbo_delay_s` (default 1.0 s), how long the
    turbopump's state stays the old one after its command (seen: more than 51 ms, less than
    the 5 s of the log); `turbo_running_pct` (50.5 %), where "Accelerating" turns "Running" (seen
    between 50.1 % and 54.3 %, and 49.5 % to about 51 %); `turbo_stopped_pct` (0.2 %), where
    "Braking" ends (seen: 0.3 % Braking, 0.1 % Stopped); the end of the run-down with the backing
    pump on after 5 minutes (the last point of turbo_rundown_backing_on)
  - ASSUMED: `start_without_backing` ("accept": the turbopump starts; "refuse": answered
    "*C904 5", Table 3 "Invalid command in current state") and `start_while_braking`
    ("accelerate": the speed rises again from where it is; "refuse": "*C904 5"). Neither was
    tried on the controller; the IOC refuses the first itself and does not rely on either.
  - ASSUMED for a gauge command: a socket without a gauge (state 0) or a gauge in another state
    than 5, 6 or 11 answers "*C<obj> 5" and is not switched; per socket `strike_s` (default 0.5 s),
    the time in the state 6 "Striking" after a switch-on (seen: none at a 1 s scan), and
    `standing_s` (default 146 s, seen), the time it reports one standing value after it.
  - the signal `command_code`: while it is not 0, every "!C" is answered "*C<obj> <code>" and
    not executed (a device case's error reply)
  - setup queries other than "?S902", "?S904 3" / "?S910 3", "?S904 4" and "?S913 4" ..
    "?S915 4": "*S<obj> 2"; "?S904" without a config type: "*S904 3" (missing parameter);
    another config type: "*S904 9". "?S904 4" answers as seen on the lab's controller,
    "=S904 4;0;59;0.0000e+00;0.0000e+00;0" (no master, not enabled)
  - the turnaround (`turnaround_ms`, default 20 ms; the manual says less than 100 ms, the
    commands were answered after 19 ms)
  - multi-drop addressing ("#dd:ss", RS-485) is not simulated
  - per socket, optional (task T31): `floor_pa`, `top_pa`, the gauge's ends: the value it
    reports is never below or above them. The lab's APG100-XM on socket 1 was seen to report
    exactly 1.0000e-02 Pa at high vacuum and exactly 1.0000e+05 Pa at atmosphere, in the state
    On (lab session, 2026-11-25); the simulator does the same with these two options.
  - per socket, optional: `slave`, the TIC's own slave setup of the gauge (D397-30-880 Table 1,
    objects 913-915 config type 4: master, units type, on set point, off set point, enable):
    {master: socket, on_torr, off_torr, enable}. "?S91x 4" answers it in the form seen for the
    turbopump's object ("=S904 4;0;59;0.0000e+00;0.0000e+00;0": config type, master object,
    units type 59, the set points in pascal, enable). While enabled (signal g<n>.slave_enable)
    the gauge is switched by the master's value: off (state 5) while the master reads above
    on_torr or is not On; at or below on_torr it strikes and is On; On or striking, it goes Off
    when the master reads above off_torr. Not enabled, or without the option, nothing switches
    it but a command or the panel. The lab's TIC did not switch its AIM by itself (seen), so the
    emulation's configuration has no link; how its slave setup is set is not read. With the
    signal g<n>.slave_form 1 the reply has the manual's example form instead
    ("=S904 913;59;5.1e-2;4.9e-1;1", 1.6.2.3: without the config type), a reply of another form.
  - per socket, the panel: the signal g<n>.panel, written over the control port, switches the
    gauge as the TIC's front panel does (1 on, 0 off), as a command would. A state set over
    the control port (g<n>.state) wins while it is held.

Signals (all settable over the control port, D5 cases):
  g<n>.pressure  true pressure at gauge n in torr (reported in pascal); for a plant model
  g<n>.state     gauge state, 1.7.7 (0 not connected, 5 off, 6 striking, 4 in alert, 11 on ...)
  g<n>.units     units type of the reply, 1.7.4 (59; 66 = voltage mode)
  g<n>.alert, g<n>.priority     alert ID (1.7.3) and priority (1.7.2)
  g<n>.panel     the switch at the front panel (see above)
  g<n>.slave_enable, g<n>.slave_form   the slave setup's enable, the form of its reply
  turbo.state (1.7.8), turbo.speed (%), turbo.type (1.7.11, 0 = No Pump), turbo.alert,
  turbo.priority, turbo.absent (1 = the controller has no such object: error replies)
  backing.state (1.7.6), backing.type, backing.alert, backing.priority, backing.absent
  commands       number of "!" messages received
  command_code   0, or the response code every "!C" gets (not executed)
"""

import bisect
import math
import re

from ..core import ConfigError, Simulator, register

PA_PER_TORR = 101325.0 / 760.0
GAUGE_OBJECTS = [913, 914, 915, 934, 935, 936]
VARIANTS = {"TIC": (3, True), "TC": (0, True), "IC": (3, False), "IC6": (6, False)}
NOT_ON_VALUE = 9.9e9
VOLTAGE_VALUE = 6.546
RUNNING = (1, 5, 4)             # turbopump states that follow a start (1.7.8)
STOPPING = (2, 3, 6, 7)         # states of a run-down

GAUGE_KEYS = {"pressure", "state", "units", "floor_pa", "top_pa", "slave", "strike_s", "standing_s"}
SLAVE_KEYS = {"master", "on_torr", "off_torr", "enable"}

MESSAGE = re.compile(r"([?!])([VCS])(\d{1,5})(?: (.*))?")

# Seen on the lab's controller, 2026-11-25 (STATUS.md, "Seen on hardware, lab session"): the
# turbopump's speed in % against the seconds since its command, sampled every 5 s.
RUNUP_SEEN = [[0, 0.0], [4, 5.5], [9, 13.3], [14, 20.3], [24, 31.5], [34, 41.8], [44, 50.1],
              [49, 54.3], [59, 62.3], [87, 82.5], [98, 89.0], [120, 100.0]]
RUNDOWN_BACKING_OFF_SEEN = [[0, 100.0], [5, 92.5], [10, 73.2], [15, 57.1], [19, 35.9], [24, 17.6],
                            [29, 9.4], [59, 1.6], [100, 0.3], [105, 0.1], [109, 0.0]]
# With the backing pump left on (the lead's message): 49 % after 40 s, 16 % after 107 s, 0.7 %
# after 5 minutes and still Braking. The last point (0 % after 600 s) is ASSUMED.
RUNDOWN_BACKING_ON_SEEN = [[0, 100.0], [40, 49.0], [107, 16.0], [300, 0.7], [600, 0.0]]


class Curve:
    """Speed against time, monotonic: points [[t, %], ...]. step(speed, dt) moves a speed that
    lies on the curve dt seconds along it (a speed off the curve's range is taken at its end)."""

    def __init__(self, name, points):
        try:
            pts = [(float(t), float(v)) for t, v in points]
        except (TypeError, ValueError):
            raise ConfigError("%s: a list of [seconds, percent] points" % name) from None
        ts = [t for t, _ in pts]
        vs = [v for _, v in pts]
        rising = vs[-1] > vs[0] if len(pts) > 1 else None
        if len(pts) < 2 or ts != sorted(ts) or len(set(ts)) != len(ts) or \
                vs != sorted(vs, reverse=not rising) or len(set(vs)) != len(vs):
            raise ConfigError("%s: at least two points, time rising, speed strictly monotonic" % name)
        self.ts, self.vs, self.rising = ts, vs, rising

    def at(self, t):
        if t <= self.ts[0]:
            return self.vs[0]
        if t >= self.ts[-1]:
            return self.vs[-1]
        i = bisect.bisect_right(self.ts, t)
        t0, t1, v0, v1 = self.ts[i - 1], self.ts[i], self.vs[i - 1], self.vs[i]
        return v0 + (v1 - v0) * (t - t0) / (t1 - t0)

    def time_of(self, v):
        vs = self.vs if self.rising else [-x for x in self.vs]
        x = v if self.rising else -v
        if x <= vs[0]:
            return self.ts[0]
        if x >= vs[-1]:
            return self.ts[-1]
        i = bisect.bisect_right(vs, x)
        x0, x1, t0, t1 = vs[i - 1], vs[i], self.ts[i - 1], self.ts[i]
        return t0 + (t1 - t0) * (x - x0) / (x1 - x0)

    def step(self, v, dt):
        return self.at(self.time_of(v) + dt)


@register("edwards_tic")
class EdwardsTic(Simulator):
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r",
                "turnaround_ms": 20.0}
    OPTIONS = {
        "variant": "TIC",          # TIC, TC, IC, IC6: which objects exist, ?V902 layout
        # one entry per gauge socket: null (no gauge: state 0) or a map with any of
        # pressure (torr), state (1.7.7, default 11 on), units (default 59), floor_pa and
        # top_pa (the ends of the reported value), slave, strike_s, standing_s (module's text)
        "gauges": [{"pressure": 1.0e-6}, None, None],
        "turbo_type": 11,          # 1.7.11 (11 nEXT - 232); 0 = No Pump
        "turbo_state": 4,          # 1.7.8 (4 Running)
        "turbo_speed": 100.0,      # %
        "backing_type": 8,         # 1.7.11 (8 Mains Backing Pump); 0 = No Pump
        "backing_state": 4,        # 1.7.6 (4 On State)
        "absent_code": 2,          # reply code for an object the variant does not have
        # ?S902 (1.6.2.2: "TIC;Dxxxxxxxx;serial;PIC s/w ver"). The form of the lab's controller,
        # seen on 2026-11-25: 'TIC100;D39700640T;160070509\x00;5.0', the first field "TIC100" and a
        # NUL byte after the serial number. The serial number here is made up.
        "identity": "TIC100;D39700640T;000000000\x00;5.0",
        "noise": 0.01,             # relative noise of a pressure reading
        # the pumps after a command (task T32): seen values, and ASSUMED ones (module's text)
        "turbo_runup": RUNUP_SEEN,
        "turbo_rundown_backing_off": RUNDOWN_BACKING_OFF_SEEN,
        "turbo_rundown_backing_on": RUNDOWN_BACKING_ON_SEEN,
        "turbo_delay_s": 1.0,              # ASSUMED
        "turbo_running_pct": 50.5,         # ASSUMED, between seen values
        "turbo_stopped_pct": 0.2,          # ASSUMED, between seen values
        "start_without_backing": "accept",  # ASSUMED: accept or refuse
        "start_while_braking": "accelerate",  # ASSUMED: accelerate or refuse
    }

    def setup(self):
        o = self.options
        if o["variant"] not in VARIANTS:
            raise ConfigError("%s: variant must be one of %s" % (self.name, ", ".join(VARIANTS)))
        self.n_gauges, has_pumps = VARIANTS[o["variant"]]
        gauges = list(o["gauges"] or [])
        if len(gauges) > self.n_gauges:
            raise ConfigError("%s: a %s has %d gauge sockets, %d configured"
                              % (self.name, o["variant"], self.n_gauges, len(gauges)))
        gauges += [None] * (self.n_gauges - len(gauges))
        self.ends, self.slaves, self.timing, self.since, self.standing = {}, {}, {}, {}, {}
        self.panel_seen = {}
        for n, g in enumerate(gauges, 1):
            g = g or {}
            if not isinstance(g, dict) or set(g) - GAUGE_KEYS:
                raise ConfigError("%s: gauge %d: null or a map of %s"
                                  % (self.name, n, ", ".join(sorted(GAUGE_KEYS))))
            present = bool(g)
            self.ends[n] = (float(g.get("floor_pa", 0.0)), float(g.get("top_pa", math.inf)))
            if self.ends[n][0] > self.ends[n][1]:
                raise ConfigError("%s: gauge %d: floor_pa above top_pa" % (self.name, n))
            strike, standing = g.get("strike_s", 0.5), g.get("standing_s", 146.0)
            if not all(isinstance(x, (int, float)) and x >= 0 for x in (strike, standing)):
                raise ConfigError("%s: gauge %d: strike_s and standing_s are seconds, not negative" % (self.name, n))
            self.timing[n] = (float(strike), float(standing))
            if "slave" in g:
                self.slaves[n] = self._slave_spec(n, g["slave"], len(gauges))
            linked = n in self.slaves and self.slaves[n]["enable"]
            state = g.get("state", 5 if linked else 11 if present else 0)
            self.add_signal("g%d.pressure" % n, g.get("pressure", 1.0e-6), lo=0.0)
            self.add_signal("g%d.state" % n, state)
            self.add_signal("g%d.units" % n, g.get("units", 59))
            self.add_signal("g%d.alert" % n, 0.0)
            self.add_signal("g%d.priority" % n, 0.0)
            self.add_signal("g%d.panel" % n, 1.0 if state in (6, 11) else 0.0)
            self.add_signal("g%d.slave_enable" % n, 1.0 if linked else 0.0)
            self.add_signal("g%d.slave_form" % n, 0.0)
            self.panel_seen[n] = self.signals["g%d.panel" % n].value
            self.since[n] = None
        for pump in ("turbo", "backing"):
            self.add_signal(pump + ".type", o[pump + "_type"])
            self.add_signal(pump + ".state", o[pump + "_state"])
            self.add_signal(pump + ".alert", 0.0)
            self.add_signal(pump + ".priority", 0.0)
            self.add_signal(pump + ".absent", 0.0 if has_pumps else 1.0)
        self.add_signal("turbo.speed", o["turbo_speed"], noise=0.0)
        self.commands = self.add_signal("commands", 0.0)
        self.add_signal("command_code", 0.0)
        self.runup = Curve("%s: turbo_runup" % self.name, o["turbo_runup"])
        self.down_off = Curve("%s: turbo_rundown_backing_off" % self.name, o["turbo_rundown_backing_off"])
        self.down_on = Curve("%s: turbo_rundown_backing_on" % self.name, o["turbo_rundown_backing_on"])
        if not self.runup.rising or self.down_off.rising or self.down_on.rising:
            raise ConfigError("%s: the run-up rises, the run-downs fall" % self.name)
        for key in ("turbo_delay_s", "turbo_running_pct", "turbo_stopped_pct"):
            if not isinstance(o[key], (int, float)) or o[key] < 0:
                raise ConfigError("%s: %s must be a number, not negative" % (self.name, key))
        for key, words in (("start_without_backing", ("accept", "refuse")),
                           ("start_while_braking", ("accelerate", "refuse"))):
            if o[key] not in words:
                raise ConfigError("%s: %s must be %s" % (self.name, key, " or ".join(words)))
        state = int(o["turbo_state"])
        self.turbo_mode = "up" if state in RUNNING else "down" if state in STOPPING else "stopped"
        self.turbo_old = None              # (state shown until, that state) after a command
        self.add_coupling(self._step)

    def _slave_spec(self, n, spec, sockets):
        if not isinstance(spec, dict) or set(spec) != SLAVE_KEYS:
            raise ConfigError("%s: gauge %d: slave needs exactly %s" % (self.name, n, ", ".join(sorted(SLAVE_KEYS))))
        if spec["master"] not in range(1, sockets + 1) or spec["master"] == n:
            raise ConfigError("%s: gauge %d: slave master must be another socket" % (self.name, n))
        if not 0 < spec["on_torr"] <= spec["off_torr"]:
            raise ConfigError("%s: gauge %d: slave needs 0 < on_torr <= off_torr" % (self.name, n))
        if not isinstance(spec["enable"], bool):
            raise ConfigError("%s: gauge %d: slave enable is true or false" % (self.name, n))
        return dict(spec)

    def _int(self, name):
        return int(round(self.signals[name].value))

    # --- couplings: the pumps' run-up and run-down, the gauges' switching ---------------------

    def _step(self, dt, signals):
        self._step_turbo(dt, signals)
        for n in range(1, self.n_gauges + 1):
            self._step_gauge(n, signals)

    def _step_turbo(self, dt, signals):
        speed_sig, state_sig = signals["turbo.speed"], signals["turbo.state"]
        speed = speed_sig.value
        if self.turbo_mode == "up":
            speed = self.runup.step(speed, dt)
            state = 4 if speed > self.options["turbo_running_pct"] else 5
        elif self.turbo_mode == "down":
            backing_on = self._int("backing.state") in (1, 4)
            speed = (self.down_on if backing_on else self.down_off).step(speed, dt)
            state = 7
            if speed <= self.options["turbo_stopped_pct"]:
                self.turbo_mode, speed, state = "stopped", 0.0, 0
        else:
            state = 0
        if self.turbo_old is not None:
            until, old = self.turbo_old
            if self.now() < until:
                state = old
            else:
                self.turbo_old = None
        speed_sig.target = speed
        if int(round(state_sig.target)) != state:
            self.log.info("%s: turbopump state %d at %.1f %%", self.name, state, speed)
            state_sig.target = state

    def reading_pa(self, n):
        """What gauge n reports in pascal, without noise, or None when it is not On."""
        if self._int("g%d.state" % n) != 11 or self._int("g%d.units" % n) != 59:
            return None
        floor, top = self.ends[n]
        return min(top, max(floor, self.signals["g%d.pressure" % n].value * PA_PER_TORR))

    def _set_gauge(self, n, state):
        sig = self.signals["g%d.state" % n]
        if int(round(sig.target)) == state:
            return
        self.log.info("%s: gauge %d %s", self.name, n, {5: "off", 6: "striking", 11: "on"}.get(state, state))
        if state == 6:
            self.since[n] = self.now()
        elif state == 5:
            self.since[n] = None
            self.standing.pop(n, None)
        sig.target = state

    def switch_gauge(self, n, on):
        """A switch-on or -off as by the command or the panel. False: not in a state for it."""
        state = self._int("g%d.state" % n)          # as reported, also a state held from outside
        if state not in (5, 6, 11):
            return False
        if on and state == 5:
            self._set_gauge(n, 6)
            self._step_gauge(n, self.signals)
        elif not on and state in (6, 11):
            self._set_gauge(n, 5)
        return True

    def _step_gauge(self, n, signals):
        panel = signals["g%d.panel" % n].value
        if panel != self.panel_seen[n]:
            self.panel_seen[n] = panel
            self.switch_gauge(n, panel >= 0.5)
        state = int(round(signals["g%d.state" % n].target))
        slave = self.slaves.get(n)
        if slave and signals["g%d.slave_enable" % n].value >= 0.5:
            master = self.reading_pa(slave["master"])
            low = master is not None and master <= slave["on_torr"] * PA_PER_TORR
            high = master is None or master > slave["off_torr"] * PA_PER_TORR
            if state in (6, 11) and high:
                self._set_gauge(n, 5)
            elif state == 5 and low:
                self._set_gauge(n, 6)
            state = int(round(signals["g%d.state" % n].target))
        if state == 6 and self.since[n] is not None and self.now() - self.since[n] >= self.timing[n][0]:
            self._set_gauge(n, 11)
            self.standing[n] = (self.now() + self.timing[n][1], None)

    # --- objects ---------------------------------------------------------------------------

    def gauge(self, n):
        state, units = self._int("g%d.state" % n), self._int("g%d.units" % n)
        if state != 11:
            value = NOT_ON_VALUE
        elif units == 59:
            p = self.signals["g%d.pressure" % n].value
            floor, top = self.ends[n]
            if not floor < p * PA_PER_TORR < top:
                value = min(top, max(floor, p * PA_PER_TORR))      # at an end: that end, exactly
            else:
                value = max(p * (1.0 + self.rng.gauss(0.0, self.options["noise"])), 0.0) * PA_PER_TORR
                value = min(top, max(floor, value))
            stand = self.standing.get(n)
            if stand is not None:
                if self.now() >= stand[0]:
                    del self.standing[n]
                elif stand[1] is None:
                    self.standing[n] = (stand[0], value)          # the first value stands
                else:
                    value = stand[1]
        else:
            value = VOLTAGE_VALUE
        return "%.4e;%d;%d;%d;%d" % (value, units, state, self._int("g%d.alert" % n),
                                     self._int("g%d.priority" % n))

    def slave_setup(self, obj, n):
        spec = self.slaves.get(n)
        if spec is None:
            master, on, off, enable = 0, 0.0, 0.0, 0
        else:
            master = GAUGE_OBJECTS[spec["master"] - 1]
            on, off = spec["on_torr"] * PA_PER_TORR, spec["off_torr"] * PA_PER_TORR
            enable = 1 if self.signals["g%d.slave_enable" % n].value >= 0.5 else 0
        if self._int("g%d.slave_form" % n):
            return "=S%d %d;59;%.1e;%.1e;%d" % (obj, master, on, off, enable)
        return "=S%d 4;%d;59;%.4e;%.4e;%d" % (obj, master, on, off, enable)

    def pump(self, pump, what):
        if what == "state":
            return "%d;%d;%d" % (self._int(pump + ".state"), self._int(pump + ".alert"),
                                 self._int(pump + ".priority"))
        return "%.1f;%d;%d" % (self.signals["turbo.speed"].value, self._int("turbo.alert"),
                               self._int("turbo.priority"))

    def system(self):
        """?V902: the state value of each item, then the alert ID of 902 and the priority."""
        variant = self.options["variant"]
        gauges = [self._int("g%d.state" % n) for n in range(1, self.n_gauges + 1)]
        pumps = [self._int("turbo.state"), self._int("backing.state")]
        relays = [0] * (6 if variant == "IC6" else 3)
        prio = [self._int(s) for s in self.signals if s.endswith(".priority")]
        if variant == "TIC":
            fields = pumps + gauges + relays
        elif variant == "TC":
            fields = pumps + relays
        else:
            fields = gauges + relays
        return ";".join(str(f) for f in fields + [0, max(prio + [0])])

    # --- messages --------------------------------------------------------------------------

    def handle(self, request, unit):
        text = request.decode("latin-1")
        start = max(text.rfind("?"), text.rfind("!"))
        if start < 0:
            return None                         # 1.2: no start character, ignored
        m = MESSAGE.fullmatch(text[start:].rstrip("\n"))
        if not m:
            return None
        kind, typ, obj, arg = m.groups()
        if kind == "!":
            self.commands.target = self.commands.value + 1
            if typ == "C":
                return self.command(int(obj), arg)
            self.log.warning("%s: setup %r received and not executed", self.name, text)
            return "*%s%s 1" % (typ, obj)
        return self.query(typ, int(obj), arg)

    def command(self, obj, arg):
        """!C<obj> <d>: the pumps (904, 910) and the gauges' on/off (1.7.5)."""
        gauges = GAUGE_OBJECTS[:self.n_gauges]
        if obj not in (904, 910) and obj not in gauges:
            self.log.warning("%s: command !C%d %s not executed", self.name, obj, arg)
            return "*C%d 1" % obj
        code = self._int("command_code")
        if code:
            self.log.warning("%s: !C%d %s answered with code %d (command_code), not executed", self.name, obj, arg, code)
            return "*C%d %d" % (obj, code)
        if arg not in ("0", "1"):
            return "*C%d 4" % obj
        on = arg == "1"
        if obj in gauges:
            if not self.switch_gauge(gauges.index(obj) + 1, on):
                return "*C%d 5" % obj
            return "*C%d 0" % obj
        pump = "backing" if obj == 910 else "turbo"
        if self._int(pump + ".absent") or self._int(pump + ".type") == 0:
            return "*C%d %d" % (obj, self.options["absent_code"])
        self.step_couplings()
        if pump == "backing":
            self.signals["backing.state"].target = 4 if on else 0
            self.log.info("%s: backing pump %s", self.name, "on" if on else "off")
            return "*C910 0"
        old = self._int("turbo.state")
        if on and self.turbo_mode != "up":
            if self._int("backing.state") not in (1, 4) and self.options["start_without_backing"] == "refuse":
                return "*C904 5"
            if self.turbo_mode == "down" and self.options["start_while_braking"] == "refuse":
                return "*C904 5"
            self.turbo_mode = "up"
        elif not on and self.turbo_mode == "up":
            self.turbo_mode = "down"
        else:
            return "*C904 0"                     # already so: nothing changes
        self.turbo_old = (self.now() + self.options["turbo_delay_s"], old)
        self.log.info("%s: turbopump %s", self.name, "start" if on else "stop")
        return "*C904 0"

    def query(self, typ, obj, arg):
        absent = "*%s%d %d" % (typ, obj, self.options["absent_code"])
        gauges = GAUGE_OBJECTS[:self.n_gauges]
        if typ == "V" and arg is None:
            if obj == 902:
                return "=V902 " + self.system()
            if obj in gauges:
                return "=V%d %s" % (obj, self.gauge(gauges.index(obj) + 1))
            if obj in (904, 905, 910):
                pump = "backing" if obj == 910 else "turbo"
                if self._int(pump + ".absent"):
                    return absent
                return "=V%d %s" % (obj, self.pump(pump, "speed" if obj == 905 else "state"))
            if obj in GAUGE_OBJECTS or 904 <= obj <= 912:
                return absent
            return "*V%d 2" % obj
        if typ == "S":
            if obj == 902 and arg is None:
                return "=S902 " + self.options["identity"]
            if obj in gauges and arg == "4":
                return self.slave_setup(obj, gauges.index(obj) + 1)
            if obj in (904, 910):
                pump = "backing" if obj == 910 else "turbo"
                if self._int(pump + ".absent"):
                    return absent
                if arg is None or arg == "":
                    return "*S%d 3" % obj
                if obj == 904 and arg == "4":
                    return "=S904 4;0;59;0.0000e+00;0.0000e+00;0"    # seen on the lab's TIC
                if arg != "3":
                    return "*S%d 9" % obj
                return "=S%d 3;%d" % (obj, self._int(pump + ".type"))
            return "*S%d 2" % obj
        return "*%s%d 2" % (typ, obj)
