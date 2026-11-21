"""Edwards nAIM digital active inverted magnetron (cold cathode) gauge, RS-232.

The instruction manual of the nAIM itself was not found. Sources:
  [TIC]  Edwards "TIC Instrument Controller Serial Communications", D397-30-880 Issue H: the
         message structure of the Edwards protocol family: queries "?V<obj>" / "?S<obj>",
         commands "!C<obj> <args>" / "!S<obj> <args>", replies "=V<obj> <data>" or
         "*<type><obj> <code>", fields separated by ";", every message ends with CR, characters
         before the start character "?" or "!" are ignored, response codes (Table 3).
  [INF]  INFICON "Communication Protocol RS232C, RS485C, MAG500/MAG504/MPG500/MPG504",
         tira83e1-e (2019-07), section 3.2 "Edwards nAIM Protocol" (INFICON's emulation of the
         nAIM): "?V752" -> "=V752 <pressure>;<status bits, 4 hex digits>", "!C752 0|1" switches
         the cold cathode, a good write is answered "*C752 0", a bad one "*C752 <code>", the
         data unit "!S755 1|2|3", the gauge status bits, the multi-drop prefix "#aa:bb".

Status bits ([INF]): 0 gauge error, 1 cold cathode on, 3 command lock, 4 and 5 pressure unit
(bit5 bit4: 0 1 mbar, 1 0 Pa, 1 1 Torr), 6 EEPROM error, 8 striking, 15 exposure threshold.

Signals: pressure (torr; drifts slowly around the option `pressure` unless a plant model sets it),
on (1 = cold cathode high voltage on), error (1 = gauge error bit), temperature (deg C, ?V759),
reject (0, or a response code that every command "!..." gets instead of 0: a test hook).

Settings, because no document gives them: what the gauge reports while off or striking
(`off_pressure`), how long striking takes (`strike_s`), whether the cathode is on at power-up
(`start_on`), the data unit at power-up (`units`; INFICON's factory setting is Pa, the lab's
database expects torr), the identity string (?S0), the drift and noise, the response time.
"""

import math
import re

from ..core import ConfigError, Simulator, register

UNIT_BITS = {"mbar": 0x10, "pa": 0x20, "torr": 0x30}
UNIT_CODES = {"1": "mbar", "2": "pa", "3": "torr"}           # !S755 n
TORR_TO = {"torr": 1.0, "mbar": 1.33322, "pa": 133.322}
ST_ERROR, ST_ON, ST_UNIT, ST_EEPROM, ST_STRIKING = 0x0001, 0x0002, 0x0030, 0x0040, 0x0100

MESSAGE = re.compile(r"(?:#(\d\d):(\d\d))?([?!])([VCS])(\d{1,5})(?: (.*))?")


@register("edwards_naim")
class EdwardsNaim(Simulator):
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r",
                "turnaround_ms": 10.0}      # [TIC] 1.4: basic messages < 100 ms; value assumed
    OPTIONS = {
        "address": 0,              # [INF] 00 = non-addressed mode, 01..98 = multi-drop
        "units": "torr",           # data unit at power-up: mbar, pa, torr
        "pressure": 1.0e-6,        # torr, the centre of the standalone drift
        "drift": 0.02,             # relative random walk per sqrt(s), log scale
        "drift_return_s": 600.0,   # the walk returns to `pressure` with this time constant
        "noise": 0.01,             # relative noise of one reading
        "start_on": True,
        "strike_s": 2.0,
        "off_pressure": 9.9e9,     # [TIC] reports 9.9e9 for a gauge that is not on: assumed
        "identity": "nAIM;SIM;0000",   # ?S0: "identity;software version;name" ([INF])
        "temperature": 25.0,
    }

    def setup(self):
        o = self.options
        if o["units"] not in UNIT_BITS:
            raise ConfigError("%s: units must be one of %s" % (self.name, ", ".join(UNIT_BITS)))
        self.pressure = self.add_signal("pressure", o["pressure"], lo=0.0)
        self.on = self.add_signal("on", 1.0 if o["start_on"] else 0.0)
        self.error = self.add_signal("error", 0.0)
        self.temperature = self.add_signal("temperature", o["temperature"], noise=0.05)
        self.reject = self.add_signal("reject", 0.0)
        self.units = o["units"]
        self.struck_at = -o["strike_s"]       # time the cathode was switched on (struck at start)
        self._was_on = o["start_on"]
        self._x = 0.0                           # log(pressure / centre)
        self.add_coupling(self._step)

    def _step(self, dt, signals):
        on = self.on.value >= 0.5
        if on and not self._was_on:
            self.struck_at = self.now()
        self._was_on = on
        if dt <= 0 or self.pressure.external:
            return
        o = self.options
        self._x += -self._x * dt / o["drift_return_s"] + \
            o["drift"] * math.sqrt(dt) * self.rng.gauss(0.0, 1.0)
        self.pressure.target = o["pressure"] * math.exp(self._x)

    def striking(self):
        return self.on.value >= 0.5 and self.now() - self.struck_at < self.options["strike_s"]

    def status_word(self):
        s = UNIT_BITS[self.units]
        s |= ST_ERROR if self.error.value >= 0.5 else 0
        s |= ST_ON if self.on.value >= 0.5 else 0
        s |= ST_STRIKING if self.striking() else 0
        return s

    def reading(self):
        if self.on.value < 0.5 or self.striking():
            return self.options["off_pressure"]
        p = self.pressure.value * (1.0 + self.rng.gauss(0.0, self.options["noise"]))
        return max(p, 0.0) * TORR_TO[self.units]

    def handle(self, request, unit):
        text = request.decode("latin-1")
        start = max(text.rfind("?"), text.rfind("!"))
        if start < 0:
            return None                         # [TIC] 1.2: no start character, ignored
        if start >= 6 and re.fullmatch(r"#\d\d:\d\d", text[start - 6:start]):
            start -= 6                          # keep the multi-drop prefix
        m = MESSAGE.fullmatch(text[start:].rstrip("\n"))
        if not m:
            return None
        dest, src, kind, typ, obj, arg = m.groups()
        address = self.options["address"]
        if (dest is None) != (address == 0):
            return None
        if dest is not None and int(dest) not in (address, 0, 99):
            return None
        reply = self._message(kind, typ, obj, arg)
        if dest is not None:
            if int(dest) == 0:
                return None                     # [INF] 00: everyone executes, nobody answers
            reply = "#%s:%02d%s" % (src, address, reply)
        return reply

    def _message(self, kind, typ, obj, arg):
        if kind == "?":
            if arg is not None:
                return "*%s%s 2" % (typ, obj)
            if typ == "V" and obj == "752":
                return "=V752 %.2E;%04X" % (self.reading(), self.status_word())
            if typ == "V" and obj == "759":
                return "=V759 %.1f" % self.temperature.read()
            if typ == "S" and obj in ("0", "751"):
                return "=S%s %s" % (obj, self.options["identity"])
            if typ == "S" and obj == "755":
                return "*S755 1"                # [INF] write only: "no access rights"
            return "*%s%s 2" % (typ, obj)
        reject = int(self.reject.value)
        if typ == "C" and obj == "752":
            if arg is None or arg == "":
                return "*C752 3"
            if arg not in ("0", "1"):
                return "*C752 4"
            if reject:
                return "*C752 %d" % reject
            if self.on.external:
                self.on.release()
            self.on.target = 1.0 if arg == "1" else 0.0
            self.step_couplings()
            return "*C752 0"
        if typ == "S" and obj == "755":
            if arg is None or arg == "":
                return "*S755 3"
            if arg not in UNIT_CODES:
                return "*S755 4"
            if reject:
                return "*S755 %d" % reject
            self.units = UNIT_CODES[arg]
            return "*S755 0"
        return "*%s%s 2" % (typ, obj)
