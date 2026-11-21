"""Matsusada CO series: one simulator = one chain of power supplies behind one CO-U32 (USB).

Protocol: CO series instruction manual rev 0.4, chapters 5 (syntax) and 7 (command reference).

    #<unit> <command> [<parameter>]   unit 0..31, or AL for the multiple commands
                                      CH0, CH1, VCN, ICN, SW, RST, REN, GTL, PL (no reply)
    CH0 FFFF / CH1 FFFF    set voltage / current, hex 0..FFFF, more than 4 digits: ignored
    VCN 12.34 / ICN 100    set in percent 0..100, more than 2 decimals truncated, >100 ignored
    SW1 / SW0, PL1 / PL0   output on / off, polarity setting
    RST                    cancel the cut-off state (the output comes back if SW1)
    REN / GTL              remote control on / off. Without remote only REN is executed
    MN1 / MN2   -> MONI1=FFFH / MONI2=FFFH    monitors, 12 bit
    VM / IM     -> VM=100.0 / IM=25.0         monitors in percent
    CH0? / CH1? -> CH0=FFFFH / CH1=FFFFH      settings, 16 bit
    VCN? / ICN? -> VCN=12.34                  settings in percent
    SW? -> SW1, PL? -> PL0, PLM -> PLM=0, STS -> #<unit> CO|CF RM|LO

Set commands get no reply. Wrong commands, wrong parameters and requests without a unit number
are ignored without a reply. Not case sensitive, spaces allowed between unit, command and
parameter. Input delimiter CR or LF, every reply ends with CR.

Each unit is a load resistance on a supply with a current limit: the output voltage follows the
set point with time constant tau_s while the output is on and falls to zero when it is off, the
current is voltage / load, and when that exceeds the current set point the supply is in constant
current mode (the voltage is pulled down). The monitors carry noise and are quantised to 12 bit.
Fault "trip": the unit cuts off as after an overload and stays off until RST.

Signals per unit <a> (all magnitudes, SI units, also for negative supplies):
    <a>.vset V, <a>.iset A        programmed set points (CH0/VCN, CH1/ICN); a value set here
                                  stays after release (front panel, power cycle)
    <a>.vout V, <a>.iout A        output (what MN1/MN2 measure)
    <a>.output 0/1                output really on (SW1, not cut off)
    <a>.sw 0/1, <a>.cutoff 0/1, <a>.remote 0/1 (set 0 = front panel takes local control; it
                                  stays local after release until REN), <a>.load_ohm
and line.turnaround_ms (a test knob: `set` changes the turnaround of the line at run time).
"""

import asyncio
import re
import time

from ..core import ALL, REQUIRED, ConfigError, Simulator, register

UNIT_KEYS = {
    "address": REQUIRED,   # 0..31, the UNIT DIL switch of the CO-HV / CO-RG
    "vfs": REQUIRED,       # full-scale voltage, V
    "ifs": REQUIRED,       # full-scale current, A
    "polarity": "+",       # "+" or "-": what PLM reports (the AU..N models are negative)
    "load_ohm": 0.0,       # load resistance; 0 = no load (open output, no current)
    "output_on": False,    # start state: output on (as left by a previous IOC)
    "remote": None,        # start state: in remote control (default: same as output_on)
    "vset": 0.0,           # start set points, V and A (manual default CH0 0000, CH1 0000)
    "iset": 0.0,
    "silent_for_s": 0.0,   # the unit is switched off for this long after the simulator starts:
                           # it neither answers nor executes (a supply that comes on later)
}

MULTIPLE = {"CH0", "CH1", "VCN", "ICN", "SW", "RST", "REN", "GTL", "PL"}   # manual 5-2

_HEX4 = re.compile(r"[0-9A-F]{1,4}")
_PERCENT = re.compile(r"([0-9]{1,3})(?:\.([0-9]*))?|\.([0-9]+)")
_UNIT = re.compile(r"#(AL|[0-9]+)(.*)")
_COMMAND = re.compile(r"(CH0\?|CH1\?|VCN\?|ICN\?|SW\?|PL\?|PLM|CH0|CH1|VCN|ICN|SW|PL|MN1|MN2|VM"
                      r"|IM|STS|RST|REN|GTL)(.*)")


def parse(request):
    """Request bytes (no delimiter) -> (unit, command, parameter) or None (ignored).
    unit is an int or "AL". Spaces are removed, letters made upper case."""
    try:
        text = request.decode("ascii")
    except UnicodeDecodeError:
        return None
    if any(not " " <= c <= "~" for c in text):
        return None                      # ASSUMED: control characters make a command wrong
    text = text.replace(" ", "").upper()
    m = _UNIT.fullmatch(text)
    if not m:
        return None
    unit = m.group(1) if m.group(1) == "AL" else int(m.group(1))
    m = _COMMAND.fullmatch(m.group(2))
    if not m:
        return None
    cmd, param = m.groups()
    return unit, cmd, param


def code16(value, fs):
    return max(0, min(0xFFFF, int(round(value / fs * 0xFFFF)))) if fs else 0


def code12(value, fs):
    return max(0, min(0xFFF, int(round(value / fs * 0xFFF)))) if fs else 0


def parse_percent(param):
    """'12.34' -> 12.34, '12.345' -> 12.34 (truncated), '123.4', '1000', '' -> None."""
    m = _PERCENT.fullmatch(param)
    if not m:
        return None
    if m.group(3) is not None:
        value = float("0." + m.group(3)[:2])
    else:
        value = float(m.group(1) + "." + (m.group(2) or "")[:2] + "0")
    return value if value <= 100.0 else None


def format_percent(code):
    """Setting in percent: 'VCN=100.0', 'VCN=12.34' in the manual. ASSUMED: two decimals with
    one trailing zero removed (100.0, 50.0, 12.34, 12.3)."""
    s = "%.2f" % (code / 0xFFFF * 100.0)
    return s[:-1] if s.endswith("0") else s


@register("matsusada_co")
class MatsusadaCO(Simulator):
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r", "turnaround_ms": 5.0}
    OPTIONS = {
        "units": REQUIRED,            # list of mappings, keys in UNIT_KEYS
        "tau_s": 0.3,                 # time constant of the output voltage
        "noise": 0.0002,              # monitor noise, standard deviation as a fraction of full scale
        # Open points of the manual, each a setting:
        "queries_without_remote": False,  # answer queries before REN (manual: CO-G32 waits for REN only)
        "icn_sets_ch1": True,         # ICN and CH1 are one setting (both on pin 2 of the control cable)
        "bang_when_off": False,       # send "!" when a unit's output goes off (manual 7-2, SRQ, USB)
        "srq_query_reply": False,     # answer "SRQ?" (no unit number) with "SRQ OFF"
    }

    def setup(self):
        self.unit = {}
        if not isinstance(self.options["units"], list) or not self.options["units"]:
            raise ConfigError("%s: units must be a non-empty list" % self.name)
        for i, cfg in enumerate(self.options["units"], 1):
            u = self._unit_config(i, cfg)
            a = u["address"]
            self.add_unit(a)
            on = bool(u["output_on"])
            remote = on if u["remote"] is None else bool(u["remote"])
            vfs, ifs = float(u["vfs"]), float(u["ifs"])
            sig = {
                "vset": self.add_signal("%d.vset" % a, u["vset"], lo=0, hi=vfs),
                "iset": self.add_signal("%d.iset" % a, u["iset"], lo=0, hi=ifs),
                "vout": self.add_signal("%d.vout" % a, u["vset"] if on else 0.0,
                                        tau=self.options["tau_s"],
                                        noise=self.options["noise"] * vfs, lo=0),
                "iout": self.add_signal("%d.iout" % a, 0.0, noise=self.options["noise"] * ifs,
                                        lo=0),
                "output": self.add_signal("%d.output" % a, float(on)),
                "sw": self.add_signal("%d.sw" % a, float(on)),
                "cutoff": self.add_signal("%d.cutoff" % a, 0.0),
                "remote": self.add_signal("%d.remote" % a, float(remote)),
                "load_ohm": self.add_signal("%d.load_ohm" % a, u["load_ohm"], lo=0),
            }
            self.unit[a] = {"vfs": vfs, "ifs": ifs, "negative": u["polarity"] == "-",
                            "pl": 0, "icn": code16(u["iset"], ifs), "ch1": code16(u["iset"], ifs),
                            "silent_until": float(u["silent_for_s"]), "sig": sig}
        self.turnaround = self.add_signal("line.turnaround_ms", self.turnaround_ms, lo=0)
        self.add_coupling(self._model)
        self._parsed = None
        self._model(0.0, self.signals)

    def _unit_config(self, i, cfg):
        where = "%s: unit %d" % (self.name, i)
        if not isinstance(cfg, dict):
            raise ConfigError("%s: expected a mapping" % where)
        unknown = sorted(set(cfg) - set(UNIT_KEYS))
        if unknown:
            raise ConfigError("%s: unknown key(s) %s; allowed: %s" % (
                where, ", ".join(unknown), ", ".join(UNIT_KEYS)))
        u = {k: cfg.get(k, d) for k, d in UNIT_KEYS.items()}
        for k, d in UNIT_KEYS.items():
            if u[k] is REQUIRED:
                raise ConfigError("%s: key %r is required" % (where, k))
        a = u["address"]
        if isinstance(a, bool) or not isinstance(a, int) or not 0 <= a <= 31:
            raise ConfigError("%s: address must be 0..31, not %r" % (where, a))
        for k in ("vfs", "ifs"):
            if isinstance(u[k], bool) or not isinstance(u[k], (int, float)) or u[k] <= 0:
                raise ConfigError("%s: %s must be a positive number" % (where, k))
        for k in ("load_ohm", "vset", "iset", "silent_for_s"):
            if isinstance(u[k], bool) or not isinstance(u[k], (int, float)) or u[k] < 0:
                raise ConfigError("%s: %s must be a number >= 0" % (where, k))
        if u["polarity"] not in ("+", "-"):
            raise ConfigError("%s: polarity must be '+' or '-'" % where)
        return u

    # --- plant model -------------------------------------------------------------------------

    def _model(self, dt, signals):
        self.turnaround_ms = self.turnaround.value
        for addr, u in self.unit.items():
            s = u["sig"]
            if s["remote"].external:
                # Front panel (plant model or test): the unit stays in that mode after release,
                # local until the next REN.
                if s["remote"].target != s["remote"].value:
                    self.log.info("unit %s: front panel: %s", addr,
                                  "remote" if s["remote"].value >= 0.5 else "local")
                s["remote"].target = s["remote"].value
            for k in ("vset", "iset"):
                # A setting changed outside the line (front panel, power cycle) stays after
                # release, until the next set command.
                if s[k].external and s[k].target != s[k].value:
                    self.log.info("unit %s: %s := %g outside the line", addr, k, s[k].value)
                    s[k].target = s[k].value
            on = s["sw"].value >= 0.5 and s["cutoff"].value < 0.5
            s["output"].target = 1.0 if on else 0.0
            v = s["vset"].value if on else 0.0
            r = s["load_ohm"].value
            if r > 0 and v / r > s["iset"].value:
                v = s["iset"].value * r          # constant current mode
            s["vout"].target = v
            s["iout"].target = s["vout"].value / r if r > 0 else 0.0

    def _changed_output(self, a, before):
        self._model(0.0, self.signals)
        after = self.unit[a]["sig"]["output"].value >= 0.5
        if before and not after and self.options["bang_when_off"]:
            self.send("!", unit=a)

    def _is_on(self, a):
        return self.unit[a]["sig"]["output"].value >= 0.5

    # --- line timing -------------------------------------------------------------------------

    async def _sleep_until(self, t):
        """The core waits with asyncio.sleep, which wakes up to about 1 ms late (epoll counts in
        whole milliseconds). On a full chain that is idle line after every reply, about 5 % of a
        19 ms transaction. Sleep to 1 ms before the time with asyncio, then the rest with
        time.sleep: that blocks the loop for at most 1 ms but, unlike yielding in a loop, costs no
        CPU and leaves the GIL to other threads (plant model in the same process)."""
        delay = t - self._loop.time() - 0.001
        if delay > 0:
            await asyncio.sleep(delay)
        rest = t - self._loop.time()
        if rest > 0:
            time.sleep(rest)

    # --- protocol ----------------------------------------------------------------------------

    async def _on_client(self, reader, writer):
        # The core splits input at one terminator; the CO series accepts CR and LF (manual 5-3).
        await super()._on_client(_LFasCR(reader) if self.in_term == b"\r" else reader, writer)

    def route(self, request):
        p = self._parsed = parse(request)
        if p is None:
            text = request.replace(b" ", b"").upper()
            if text == b"SRQ?" and self.options["srq_query_reply"]:
                self._parsed = ("SRQ", "SRQ?", "")
                return self.units[0]
            return None
        unit, cmd, param = p
        if unit == "AL":
            if cmd not in MULTIPLE:
                return None              # queries and MN/STS are not multiple commands
            return ALL
        return unit                      # unknown addresses: the core lets nobody answer

    def handle(self, request, unit):
        if self._parsed is None:
            return None
        u, cmd, param = self._parsed
        if u == "SRQ":
            return "SRQ OFF"
        d = self.unit[unit]
        s = d["sig"]
        if self.now() < d["silent_until"]:
            return None                  # switched off
        if cmd == "REN" and not param:
            if s["remote"].value < 0.5:
                self.log.info("unit %s: REN (remote control on)", unit)
            s["remote"].target = 1.0
            return None
        if s["remote"].value < 0.5:
            # Manual 7-2 REN/GTL: without remote control only REN is accepted.
            if not (self.options["queries_without_remote"] and _is_query(cmd)):
                if not _is_query(cmd):
                    self.log.info("unit %s: %s %s ignored (local)", unit, cmd, param)
                return None
        if cmd in ("CH0", "CH1"):
            if not _HEX4.fullmatch(param):
                return None
            self._set(unit, cmd, int(param, 16))
            return None
        if cmd in ("VCN", "ICN"):
            pct = parse_percent(param)
            if pct is None:
                return None
            code = int(round(pct / 100.0 * 0xFFFF))
            if cmd == "VCN":
                self._set(unit, "CH0", code, "VCN %s" % param)
            else:
                d["icn"] = code
                if self.options["icn_sets_ch1"]:
                    self._set(unit, "CH1", code, "ICN %s" % param)
                else:
                    s["iset"].target = code / 0xFFFF * d["ifs"]
                    self.log.info("unit %s: ICN %s", unit, param)
            return None
        if cmd == "SW" and param in ("0", "1"):
            before = self._is_on(unit)
            s["sw"].target = float(param)
            self.log.info("unit %s: SW%s", unit, param)
            self._changed_output(unit, before)
            return None
        if cmd == "PL" and param in ("0", "1"):
            d["pl"] = int(param)
            return None
        if param:
            return None                  # every remaining command takes no parameter
        if cmd == "RST":
            before = self._is_on(unit)
            s["cutoff"].target = 0.0
            self.log.info("unit %s: RST", unit)
            self._changed_output(unit, before)
            return None
        if cmd == "GTL":
            s["remote"].target = 0.0
            self.log.info("unit %s: GTL (local)", unit)
            return None
        if cmd == "MN1":
            return "MONI1=%03XH" % code12(s["vout"].read(), d["vfs"])
        if cmd == "MN2":
            return "MONI2=%03XH" % code12(s["iout"].read(), d["ifs"])
        if cmd == "VM":
            return "VM=%.1f" % (code12(s["vout"].read(), d["vfs"]) / 0xFFF * 100.0)
        if cmd == "IM":
            return "IM=%.1f" % (code12(s["iout"].read(), d["ifs"]) / 0xFFF * 100.0)
        if cmd == "CH0?":
            return "CH0=%04XH" % code16(s["vset"].value, d["vfs"])
        if cmd == "CH1?":
            return "CH1=%04XH" % self._ch1(d)
        if cmd == "VCN?":
            return "VCN=%s" % format_percent(code16(s["vset"].value, d["vfs"]))
        if cmd == "ICN?":
            return "ICN=%s" % format_percent(self._ch1(d) if self.options["icn_sets_ch1"]
                                             else d["icn"])
        if cmd == "SW?":
            return "SW%d" % (s["sw"].value >= 0.5)
        if cmd == "PL?":
            return "PL%d" % d["pl"]
        if cmd == "PLM":
            return "PLM=%d" % d["negative"]
        if cmd == "STS":
            return "#%d %s %s" % (unit, "CO" if self._is_on(unit) else "CF",
                                  "RM" if s["remote"].value >= 0.5 else "LO")
        return None

    def _ch1(self, d):
        if self.options["icn_sets_ch1"]:
            return code16(d["sig"]["iset"].value, d["ifs"])
        return d["ch1"]

    def _set(self, unit, reg, code, text=None):
        d = self.unit[unit]
        if reg == "CH0":
            d["sig"]["vset"].target = code / 0xFFFF * d["vfs"]
        else:
            d["sig"]["iset"].target = code / 0xFFFF * d["ifs"]
            d["ch1"] = code
        self.log.info("unit %s: %s", unit, text or "%s %04X" % (reg, code))

    # --- faults ------------------------------------------------------------------------------

    def trip(self, unit):
        """Cut-off as after an overload: the output goes off and stays off until RST."""
        for a in (self.units if unit is None else [unit]):
            before = self._is_on(a)
            self.unit[a]["sig"]["cutoff"].target = 1.0
            self._changed_output(a, before)

    def trip_cleared(self, unit):
        pass                              # the cut-off is latched: only RST ends it


def _is_query(cmd):
    return cmd.endswith("?") or cmd in ("MN1", "MN2", "VM", "IM", "PLM", "STS")


class _LFasCR:
    """Stream reader wrapper: LF is a delimiter like CR."""

    def __init__(self, reader):
        self._reader = reader

    async def read(self, n=-1):
        return (await self._reader.read(n)).replace(b"\n", b"\r")

