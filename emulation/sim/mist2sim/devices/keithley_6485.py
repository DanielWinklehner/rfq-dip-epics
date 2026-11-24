"""Keithley Model 6485 picoammeter, SCPI over RS-232.

Source: Keithley "Model 6485 Picoammeter Instruction Manual", document 6485-901-01 Rev. A
(November 2001), from download.tek.com. Page numbers below are the manual's (section-page).

What is simulated, with its place in the manual:
  * power-on state: the factory setup (SYSTem:PRESet), which the instrument powers up to as
    shipped (1-15; SYSTem:POSetup default PRES, Table 14-6): zero check ON, zero correct OFF,
    range AUTO, NPLC 6 (60 Hz) or 5 (50 Hz), arm count INF (Table 1-3, 1-16/1-17); autozero ON
    (Table 2-2, 2-3); data elements READing, UNITs, TIME, STATus ("All 4", Table 13-2, 13-3).
    Option power_on_setup "RST" gives the bus defaults instead (arm count 1, Table 1-3).
  * trigger model: in the factory setup the instrument leaves idle at power-on and keeps
    measuring (7-4, Figure 7-1). "While operating within the trigger model (not in idle), most
    commands will not be executed until the instrument completes all of its programmed operations
    and returns to the idle state"; ABORt, SYSTem:PRESet, *TRG, *RST, *RCL are the exceptions
    (7-4). ABORt goes to idle, INITiate leaves it (Table 7-3, 7-9). With an infinite arm count the
    instrument never returns to idle: a command that has to wait never runs (the simulator then
    answers nothing to that message), with a finite count it runs when the count is done.
  * one reading takes NPLC / line frequency (4-5: 1 PLC = 16.67 ms at 60 Hz, 20 ms at 50 Hz),
    times `autozero_factor` while autozero is on (2-2: autozero off "increases measurement speed
    up to 3 times"; the factor itself is not given, default 3 = the worst case).
  * SENSe:DATA? returns the last reading, "If there is no reading available ... an error (-230)"
    (3-5); the reading string has the selected elements in ASCII (13-4, Figure 13-1:
    "+1.040564E-06A, +2.236299E+02, +1.380000E+02"); overflow and overvoltage readings are
    "+9.9E37" (13-6); status word bits 0 overflow, 7 overvoltage, 9 zero check, 10 zero correct
    (13-6, 13-7), sent in decimal in scientific notation as in Figure 13-1.
  * ranges 2 nA ... 20 mA, full scale 5 % over range, above it overflow (4-2, Table 4-3);
    autorange goes up at 105 % of range and down at the range value (4-2).
  * multiple commands in one message separated by ";", a leading ":" returns to the root
    (9-14); an invalid command is not executed and the commands after it are ignored (9-15);
    multiple responses are sent in order separated by ";" (9-15, example "0; 1; 1; 0").
  * *IDN? "KEITHLEY INSTRUMENTS INC., MODEL 6485, xxxxxxx, yyyyy/zzzzz/w" (11-3).
  * commands are processed after CR (9-17); the transmit terminator is a menu choice (LF, CR,
    LFCR, CRLF, 9-17): CR assumed here, as in keithley6485.proto.

Commands: ABORt, INITiate, *IDN?, SYSTem:ZCHeck <b> / ?, [SENSe:]CURRent:RANGe[:UPPer] <n> / ?,
[SENSe:]CURRent:RANGe:AUTO <b> / ?, [SENSe:]CURRent:NPLCycles <n> / ?, SYSTem:AZERo <b> / ?,
[SENSe:]DATA[:LATest]?. Anything else is an undefined header: not executed, the rest of the
message ignored, no answer.

Not in the manual, therefore options or assumptions: the reply format of CURR:RANG? and
CURR:NPLC? ("%.6E"), whether the range query reports the range in use while autoranging (it
does here), what a reading shows with zero check on (`zero_check_reading`), the response time,
the spaces after "," and ";" (as printed in the manual, option `spaces`), the serial number and
firmware in *IDN?. The factory autorange state is contradictory in the manual (Table 1-3: AUTO;
Table 14-4 note: SYSTem:PRESet OFF): option `power_on_auto`, default AUTO (Table 1-3).
Not simulated: zero correct, filters, REL, math, buffer, limits, triggers other than immediate,
the autorange limits, DDC.

Signals (control port): current (A, the input; a plant model drives it), zero_check, auto (0/1),
range (A, nominal), nplc, autozero (0/1), power (set 0 then 1 = a power cycle back to the
power-on setup), and counters n_set (executed commands that change a setting), n_abort, n_init,
n_query. Faults: the core's (silent, close, garbage, slow); no trip.
"""

import math

from ..core import ConfigError, Simulator, register

RANGES = [2e-9, 2e-8, 2e-7, 2e-6, 2e-5, 2e-4, 2e-3, 2e-2]   # Table 4-3
OVER = 1.05                                                  # 4-2: 5 % over range
OVERFLOW = "+9.9E37"                                         # 13-6
ST_OFLO, ST_OVERVOLT, ST_ZCH, ST_ZCOR = 0x001, 0x080, 0x200, 0x400   # 13-6, 13-7
ALLOWED_WHILE_RUNNING = {"ABOR"}                            # 7-4 (of the commands simulated)

# Command patterns as in Section 14: nodes "LONGform" (the short form is the upper-case
# letters, 9-12), optional nodes in brackets. SENSe also as SENSe1 (Table 14-4: [:SENSe[1]]).
PATTERNS = {
    "ABOR": "ABORt",
    "INIT": "INITiate [IMMediate]",
    "ZCH": "SYSTem ZCHeck [STATe]",
    "AZER": "SYSTem AZERo [STATe]",
    "RANG": "[SENSe] CURRent [DC] RANGe [UPPer]",
    "AUTO": "[SENSe] CURRent [DC] RANGe AUTO",
    "NPLC": "[SENSe] CURRent [DC] NPLCycles",
    "DATA": "[SENSe] DATA [LATest]",
}


def _nodes(pattern):
    return [(w.strip("[]"), w.startswith("[")) for w in pattern.split()]


def _word_matches(token, word):
    """9-12, 9-13: a command word in its short form (the upper-case letters) or long form."""
    short = "".join(c for c in word if c.isupper())
    token = token.upper()
    if token.endswith("1") and token[:-1] in (short, word.upper()):
        token = token[:-1]
    return token in (short, word.upper())


def _match(tokens, nodes):
    if not nodes:
        return not tokens
    (word, optional), rest = nodes[0], nodes[1:]
    if tokens and _word_matches(tokens[0], word) and _match(tokens[1:], rest):
        return True
    return optional and _match(tokens, rest)


COMPILED = {k: _nodes(v) for k, v in PATTERNS.items()}


def _bool(arg):
    a = arg.strip().upper()
    if a in ("1", "ON"):
        return True
    if a in ("0", "OFF"):
        return False
    raise ValueError(arg)


@register("keithley_6485")
class Keithley6485(Simulator):
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r",
                "turnaround_ms": 5.0}           # response time: not in the manual, assumed
    OPTIONS = {
        "identity": "KEITHLEY INSTRUMENTS INC., MODEL 6485, 0000000, SIM00/SIM00/A",
        "power_on_setup": "PRES",       # PRES (factory, as shipped) or RST (bus defaults)
        "power_on_auto": True,          # Table 1-3 says AUTO, Table 14-4 note says OFF
        "power_on_range": 2e-4,         # Table 14-4 default 2.1e-4: the 200 uA range
        "line_frequency": 60.0,         # 50 or 60 Hz (1-13)
        "autozero_factor": 3.0,         # 2-2: "up to 3 times"
        "current": 0.0,                 # A, the input at start
        "noise": 0.0,                   # A, rms noise of a reading
        "zero_check_reading": 0.0,      # A, what a reading shows with zero check on: assumed
        "spaces": True,                 # ", " and "; " as printed in the manual
    }

    def setup(self):
        o = self.options
        if o["power_on_setup"] not in ("PRES", "RST"):
            raise ConfigError("%s: power_on_setup must be PRES or RST" % self.name)
        if o["line_frequency"] not in (50, 60):
            raise ConfigError("%s: line_frequency must be 50 or 60" % self.name)
        if not any(abs(o["power_on_range"] / r - 1) < 0.1 for r in RANGES):
            raise ConfigError("%s: power_on_range must be one of %s" % (self.name, RANGES))
        self.current = self.add_signal("current", o["current"], noise=o["noise"])
        self.zero_check = self.add_signal("zero_check", 1.0)
        self.auto = self.add_signal("auto", 1.0)
        self.range = self.add_signal("range", 2e-4)
        self.nplc = self.add_signal("nplc", 6.0)
        self.autozero = self.add_signal("autozero", 1.0)
        self.power = self.add_signal("power", 1.0)
        self.counters = {n: self.add_signal(n, 0.0)
                         for n in ("n_set", "n_abort", "n_init", "n_query")}
        self._pending = []              # (due, text): replies held back until the run is done
        self._power_on()
        self._was_on = True
        self.add_coupling(self._step)

    # --- power -------------------------------------------------------------------------------

    def _power_on(self):
        """1-14, 1-15: the power-on setup; the timestamp starts at zero (13-6)."""
        o = self.options
        for sig, value in ((self.zero_check, 1.0), (self.auto, 1.0 if o["power_on_auto"] else 0.0),
                           (self.range, self._nominal(o["power_on_range"])),
                           (self.nplc, 6.0 if o["line_frequency"] == 60 else 5.0),
                           (self.autozero, 1.0)):
            sig.release()
            sig.target = value
        self.t_on = self.now()
        self.last = None                # (reading text, timestamp, status) of the last reading
        self._pending = []
        if o["power_on_setup"] == "PRES":
            self.arm_count = None       # INF (Table 1-3, factory)
            self.run_start = self.now() # 7-4: leaves idle when it is turned on
        else:
            self.arm_count = 1          # Table 1-3, *RST
            self.run_start = None       # remote: idle until INITiate (7-4, Figure 7-2)

    def _step(self, dt, signals):
        on = self.power.value >= 0.5
        if on and not self._was_on:
            self.log.info("power on: %s setup", self.options["power_on_setup"])
            self._power_on()
        elif not on and self._was_on:
            self.log.info("power off")
        self._was_on = on

    # --- measurement -------------------------------------------------------------------------

    @staticmethod
    def _nominal(value):
        """The range that a value selects: the lowest that holds it (4-2, Table 4-3)."""
        v = abs(value)
        for r in RANGES:
            if v <= r * OVER:
                return r
        return RANGES[-1]

    def reading_time(self):
        t = self.nplc.value / self.options["line_frequency"]
        return t * (self.options["autozero_factor"] if self.autozero.value >= 0.5 else 1.0)

    def _run_end(self):
        if self.run_start is None or self.arm_count is None:
            return None
        return self.run_start + self.arm_count * self.reading_time()

    def busy(self, t):
        if self.run_start is None:
            return False
        end = self._run_end()
        return end is None or t < end

    def _settle(self, t):
        """Take the readings completed up to t: the last one becomes the latest reading."""
        if self.run_start is None:
            return
        end = self._run_end()
        upto = t if end is None else min(t, end)
        n = int(math.floor((upto - self.run_start) / self.reading_time() + 1e-9))
        if self.arm_count is not None:
            n = min(n, self.arm_count)
        if n >= 1:
            self.last = self._measure(self.run_start + n * self.reading_time())
        if end is not None and t >= end:
            self.run_start = None

    def _autorange(self, value):
        """4-2: up at 105 % of range, down below the range value of the next lower range."""
        r = self.range.value
        i = RANGES.index(self._nominal(r))
        v = abs(value)
        while v > RANGES[i] * OVER and i < len(RANGES) - 1:
            i += 1
        while i > 0 and v < RANGES[i - 1]:
            i -= 1
        self.range.target = RANGES[i]

    def _measure(self, t_done):
        status = 0
        value = self.current.read()
        if self.zero_check.value >= 0.5:
            status |= ST_ZCH
            value = self.options["zero_check_reading"]
        elif self.auto.value >= 0.5 and not self.range.external:
            self._autorange(value)
        if abs(value) > self.range.value * OVER:
            status |= ST_OFLO
            text = OVERFLOW
        else:
            text = "%+.6E" % value
        return text, t_done - self.t_on, status

    def data_string(self):
        """13-4, Figure 13-1: READing with UNITs, TIME, STATus."""
        text, stamp, status = self.last
        sep = ", " if self.options["spaces"] else ","
        return "%sA%s%+.6E%s%+.6E" % (text, sep, stamp, sep, float(status))

    # --- protocol ----------------------------------------------------------------------------

    def _count(self, name):
        self.counters[name].target = self.counters[name].value + 1

    def _set(self, sig, value, what):
        sig.release()
        sig.target = value
        self._count("n_set")
        self.log.info("setting: %s", what)

    def handle(self, request, unit):
        if self.power.value < 0.5:
            return None
        text = request.decode("latin-1").replace("\n", "").strip()
        t = self.now()
        replies = []
        path = []
        for part in text.split(";"):
            part = part.strip()
            if not part:
                continue
            if self.busy(t) and not self._allowed(part, path):
                if self.arm_count is None:
                    return None             # 7-4: never back in idle, the command never runs
                t = self._run_end()         # finite count: runs when the count is done
            self._settle(t)
            result = self._execute(part, path, t)
            if result is False:
                break                       # 9-15: the rest of the message is ignored
            if result is not None:
                replies.append(result)
        if not replies:
            return None
        line = ("; " if self.options["spaces"] else ";").join(replies)
        if t > self.now():
            self._pending.append((t, line))
            return None
        return line

    def tick(self, now):
        due = [p for p in self._pending if p[0] <= now + 1e-9]
        for p in due:
            self._pending.remove(p)
            self.send(p[1])
        return min((p[0] for p in self._pending), default=None)

    def _split(self, part, path):
        """Header tokens (absolute, 9-14) and the argument."""
        header, _, arg = part.partition(" ")
        query = header.endswith("?")
        header = header.rstrip("?")
        if header.startswith("*"):
            return [header.upper()], query, arg
        if header.startswith(":"):
            tokens = header[1:].split(":")
        else:
            tokens = path[:-1] + header.split(":") if path else header.split(":")
        return tokens, query, arg

    def _allowed(self, part, path):
        tokens, query, arg = self._split(part, path)
        return not query and _match(tokens, COMPILED["ABOR"])

    def _execute(self, part, path, t):
        """One command. Returns a reply string, None (no reply) or False (error: stop)."""
        tokens, query, arg = self._split(part, path)
        if tokens == ["*IDN"] and query:
            self._count("n_query")
            return self.options["identity"]
        name = next((k for k, nodes in COMPILED.items() if _match(tokens, nodes)), None)
        if name is None or tokens[0].startswith("*"):
            self.log.info("undefined header: %r", part)     # -113 (B-3)
            return False
        path[:] = tokens
        try:
            return self._command(name, query, arg, t)
        except ValueError:
            self.log.info("bad parameter: %r", part)
            return False

    def _command(self, name, query, arg, t):
        if name == "ABOR":
            self._count("n_abort")
            self.run_start = None           # 7-9: goes to idle
            return None
        if name == "INIT":
            self._count("n_init")
            if self.run_start is None:      # 7-10: not executed while in the trigger model
                self.run_start = t
            return None
        if name == "DATA":
            if not query:
                raise ValueError(name)
            self._count("n_query")
            if self.last is None:
                self.log.info("no reading available: -230")   # 3-5
                return False
            return self.data_string()
        sig = {"ZCH": self.zero_check, "AZER": self.autozero, "AUTO": self.auto,
               "RANG": self.range, "NPLC": self.nplc}[name]
        if query:
            self._count("n_query")
            if name in ("ZCH", "AZER", "AUTO"):
                return "1" if sig.value >= 0.5 else "0"
            return "%.6E" % sig.value
        if name in ("ZCH", "AZER", "AUTO"):
            self._set(sig, 1.0 if _bool(arg) else 0.0, "%s %s" % (name, arg))
            return None
        value = float(arg)
        if name == "RANG":
            if abs(value) > 0.021:          # Table 14-4: -0.021 to 0.021
                raise ValueError(arg)
            self._set(sig, self._nominal(value), "RANG %s" % arg)
            return None
        limit = 6.0 if self.options["line_frequency"] == 60 else 5.0   # Table 4-4
        if not 0.01 <= value <= limit:
            raise ValueError(arg)
        self._set(sig, value, "NPLC %s" % arg)
        return None
