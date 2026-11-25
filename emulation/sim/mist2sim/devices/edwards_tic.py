"""Edwards TIC controller (Turbo Instrument Controller), RS-232, queries only (task T29).

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

Not in the manual, so options or choices of this simulator (named so in TIC.md):
  - which objects each variant has: TC no gauges, IC and IC6 no pumps (from the variant
    structures of object 902 and the product names); `absent_code`: the response code of a
    query to an object the variant does not have (default 2, "Invalid query/command")
  - the value of a gauge that is not on: 9.9e9 (the example of object 940 in Table 1, "gauge 5
    not ON (e.g. OFF, error, striking etc)"); the number format "%.4e" (that example)
  - the value of a gauge in voltage mode (units 66): 0.000 - 11.000 V, here a fixed 6.546 (the
    example of object 940)
  - a command or setup ("!") is never executed: it is counted (signal `commands`) and answered
    "*<type><obj> 1"; the IOC of T29 must never send one
  - setup queries other than "?S902" and "?S904 3" / "?S910 3": "*S<obj> 2"; "?S904" without a
    config type: "*S904 3" (missing parameter); another config type: "*S904 9"
  - the turnaround (`turnaround_ms`, default 20 ms; the manual says less than 100 ms)
  - multi-drop addressing ("#dd:ss", RS-485) is not simulated

Signals (all settable over the control port, D5 cases):
  g<n>.pressure  true pressure at gauge n in torr (reported in pascal); for a plant model
  g<n>.state     gauge state, 1.7.7 (0 not connected, 5 off, 6 striking, 4 in alert, 11 on ...)
  g<n>.units     units type of the reply, 1.7.4 (59; 66 = voltage mode)
  g<n>.alert, g<n>.priority     alert ID (1.7.3) and priority (1.7.2)
  turbo.state (1.7.8), turbo.speed (%), turbo.type (1.7.11, 0 = No Pump), turbo.alert,
  turbo.priority, turbo.absent (1 = the controller has no such object: error replies)
  backing.state (1.7.6), backing.type, backing.alert, backing.priority, backing.absent
  commands       number of "!" messages received
"""

import re

from ..core import ConfigError, Simulator, register

PA_PER_TORR = 101325.0 / 760.0
GAUGE_OBJECTS = [913, 914, 915, 934, 935, 936]
VARIANTS = {"TIC": (3, True), "TC": (0, True), "IC": (3, False), "IC6": (6, False)}
NOT_ON_VALUE = 9.9e9
VOLTAGE_VALUE = 6.546

MESSAGE = re.compile(r"([?!])([VCS])(\d{1,5})(?: (.*))?")


@register("edwards_tic")
class EdwardsTic(Simulator):
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r",
                "turnaround_ms": 20.0}
    OPTIONS = {
        "variant": "TIC",          # TIC, TC, IC, IC6: which objects exist, ?V902 layout
        # one entry per gauge socket: null (no gauge: state 0) or a map with any of
        # pressure (torr), state (1.7.7, default 11 on), units (default 59)
        "gauges": [{"pressure": 1.0e-6}, None, None],
        "turbo_type": 11,          # 1.7.11 (11 nEXT - 232); 0 = No Pump
        "turbo_state": 4,          # 1.7.8 (4 Running)
        "turbo_speed": 100.0,      # %
        "backing_type": 8,         # 1.7.11 (8 Mains Backing Pump); 0 = No Pump
        "backing_state": 4,        # 1.7.6 (4 On State)
        "absent_code": 2,          # reply code for an object the variant does not have
        "identity": "TIC;DSIM00000;SIM0001;SIM",   # ?S902 (1.6.2.2)
        "noise": 0.01,             # relative noise of a pressure reading
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
        for n, g in enumerate(gauges, 1):
            g = g or {}
            if not isinstance(g, dict) or set(g) - {"pressure", "state", "units"}:
                raise ConfigError("%s: gauge %d: null or a map of pressure, state, units"
                                  % (self.name, n))
            present = bool(g)
            self.add_signal("g%d.pressure" % n, g.get("pressure", 1.0e-6), lo=0.0)
            self.add_signal("g%d.state" % n, g.get("state", 11 if present else 0))
            self.add_signal("g%d.units" % n, g.get("units", 59))
            self.add_signal("g%d.alert" % n, 0.0)
            self.add_signal("g%d.priority" % n, 0.0)
        for pump in ("turbo", "backing"):
            self.add_signal(pump + ".type", o[pump + "_type"])
            self.add_signal(pump + ".state", o[pump + "_state"])
            self.add_signal(pump + ".alert", 0.0)
            self.add_signal(pump + ".priority", 0.0)
            self.add_signal(pump + ".absent", 0.0 if has_pumps else 1.0)
        self.add_signal("turbo.speed", o["turbo_speed"], noise=0.0)
        self.commands = self.add_signal("commands", 0.0)

    def _int(self, name):
        return int(round(self.signals[name].value))

    # --- objects ---------------------------------------------------------------------------

    def gauge(self, n):
        state, units = self._int("g%d.state" % n), self._int("g%d.units" % n)
        if state != 11:
            value = NOT_ON_VALUE
        elif units == 59:
            p = self.signals["g%d.pressure" % n].value
            value = max(p * (1.0 + self.rng.gauss(0.0, self.options["noise"])), 0.0) * PA_PER_TORR
        else:
            value = VOLTAGE_VALUE
        return "%.4e;%d;%d;%d;%d" % (value, units, state, self._int("g%d.alert" % n),
                                     self._int("g%d.priority" % n))

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
            self.log.warning("%s: command or setup %r received and not executed", self.name, text)
            return "*%s%s 1" % (typ, obj)
        return self.query(typ, int(obj), arg)

    def query(self, typ, obj, arg):
        absent = "*%s%d %d" % (typ, obj, self.options["absent_code"])
        if typ == "V" and arg is None:
            if obj == 902:
                return "=V902 " + self.system()
            gauges = GAUGE_OBJECTS[:self.n_gauges]
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
            if obj in (904, 910):
                pump = "backing" if obj == 910 else "turbo"
                if self._int(pump + ".absent"):
                    return absent
                if arg is None or arg == "":
                    return "*S%d 3" % obj
                if arg != "3":
                    return "*S%d 9" % obj
                return "=S%d 3;%d" % (obj, self._int(pump + ".type"))
            return "*S%d 2" % obj
        return "*%s%d 2" % (typ, obj)
