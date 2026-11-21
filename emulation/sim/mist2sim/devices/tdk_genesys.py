"""TDK-Lambda GENESYS 2.4 kW (default: GEN8-300), RS-232/RS-485 remote control.

Source: TDK-Lambda "GENESYS GEN 2.4kW Series Power Supplies User Manual", IA669-04-01 Rev.D,
chapter 7 (protocol, command set, registers), 5.3 (OVP reset), 5.8 (Enable), 5.11 (safe start,
auto-restart), 5.13 (last setting memory). Section numbers below refer to that manual.

Wire format: commands end with CR, LF is ignored (7.5.3), backspace deletes (7.5.8), "\\" repeats
the last command (7.5.4), an optional "$<2 hex>" checksum makes the reply carry one too (7.5.5).
Every command is answered with "OK", a query with its value, an error with Cnn or Enn (7.6).
"ADR n" must be answered with OK before anything else is accepted (7.5 note).

Model: a programmed voltage pv and current pc, an output switch, and a load resistance. With the
output on the supply is in CV when pv / R <= pc, else in CC. The measured mv and mc follow the
operating point with time constant tau_s and carry noise.

Signals (control port): pv, pc (programmed, V and A), mv, mc (measured, V and A), output (0/1,
the actual output state), load_ohm (the load, a plant model can drive it), ac_power (1 = AC on;
set 0 and then 1 or release = a power cycle), enable_open (1 = rear panel J1 Enable open, 5.8).
Fault "trip": an OVP shutdown (5.3): output off, FLT bit OVP, cleared by OUT 1 or a power cycle.

Not established from the manual, therefore settings or assumptions (see OPTIONS):
  * the reply of an unaddressed supply: none (a multi-drop bus needs the others to be silent)
  * an ADR with a bad argument: no reply
  * the error code for PC, OVP above the maximum, UVL above its maximum and over-long values:
    C05 ("setting out of range"), C03 for a value that is not a number or longer than 12 chars
  * REV?, SN?, DATE? strings, the response time (turnaround_ms) and the time constant
Not simulated: SRQ messages (FENA/SENA are stored, no "!nn" is sent), SAV/RCL, FBD, global
commands (G...), foldback tripping, OTP, AC fail and SO: they answer C01 or never happen.
"""

import re

from ..core import Simulator, register

# Fault Condition Register (Table 7-7) and Status Condition Register (Table 7-8)
FLT_AC, FLT_OTP, FLT_FOLD, FLT_OVP = 0x02, 0x04, 0x08, 0x10
FLT_SO, FLT_OFF, FLT_ENA = 0x20, 0x40, 0x80
ST_CV, ST_CC, ST_NFLT, ST_FLT, ST_AST, ST_FDE, ST_LCL = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x80

ON_OFF = {"1": True, "ON": True, "0": False, "OFF": False}
RMT_MODES = {"0": "LOC", "LOC": "LOC", "1": "REM", "REM": "REM", "2": "LLO", "LLO": "LLO"}


def _flag(attr):
    """A command "<CMD> 1|ON|0|OFF" that sets a boolean attribute."""
    def fn(self, arg):
        on = ON_OFF.get(arg)
        if on is None:
            return "C03"
        setattr(self, attr, on)
        return "OK"
    return fn


def _hex_register(attr):
    """A command "<CMD> nn" that sets a register from two hex digits."""
    def fn(self, arg):
        if not re.fullmatch(r"[0-9A-F]{1,2}", arg):
            return "C03"
        setattr(self, attr, int(arg, 16))
        return "OK"
    return fn


def checksum(text):
    """7.5.5: '$' and two hex characters, the sum of the characters modulo 256."""
    return "%02X" % (sum(text.encode("latin-1")) % 256)


@register("tdk_genesys")
class TdkGenesys(Simulator):
    DEFAULTS = {"baud": 19200, "in_terminator": "\r", "out_terminator": "\r",
                "turnaround_ms": 5.0}          # response time: not in the manual, assumed
    OPTIONS = {
        "address": 6,             # 7.2.1: shipped with address 6
        "v_rating": 8.0,          # rated output, Table 7-3 / 7-4 (GEN8-300)
        "i_rating": 300.0,
        "ovp_min": 0.5,           # Table 7-5 for 8 V
        "ovp_max": 10.0,
        "uvl_max": 7.6,           # Table 7-6 for 8 V
        "v_format": "%.3f",       # MV?, Table 7-3: 0.000 ... 8.000 for 8 V
        "i_format": "%06.2f",     # MC?, Table 7-4: 000.00 ... 300.00 for GEN8-300
        "idn": "LAMBDA,GEN8-300",  # 7.7.4: "LAMBDA, GENX-Y"
        "rev": "REV:SIM",         # placeholder: real strings unknown
        "sn": "000000",
        "date": "2017/06/01",
        "load_ohm": 0.025,        # a hot filament: a few tens of milliohms
        "tau_s": 0.1,             # output follows its operating point, assumed
        "noise_v": 0.002,
        "noise_i": 0.05,
        "auto_restart": False,    # 7.2.1: shipped in safe start
        "addressed_at_start": False,   # a supply that was just switched on is unaddressed
    }

    def setup(self):
        o = self.options
        self.pv = self.add_signal("pv", 0.0)
        self.pc = self.add_signal("pc", 0.0)
        self.mv = self.add_signal("mv", 0.0, tau=o["tau_s"], noise=o["noise_v"], lo=0.0)
        self.mc = self.add_signal("mc", 0.0, tau=o["tau_s"], noise=o["noise_i"], lo=0.0)
        self.output = self.add_signal("output", 0.0)
        self.load = self.add_signal("load_ohm", o["load_ohm"], lo=0.0)
        self.ac_power = self.add_signal("ac_power", 1.0)
        self.enable_open = self.add_signal("enable_open", 0.0)
        self.addressed = o["addressed_at_start"]
        self.rmt = "LOC"
        self.out_req = False                    # the OUT setting (kept over a power cycle)
        self.pv_str, self.pc_str = "0", "0"
        self.ovp = o["ovp_max"]
        self.ovp_str = "%.1f" % self.ovp
        self.uvl, self.uvl_str = 0.0, "0"
        self.ast = o["auto_restart"]
        self.fld = False
        self.latched = 0                        # OVP (and FOLD) until OUT 1 or AC recycle
        self.fena = self.sena = self.feve = self.seve = 0
        self.mode = "OFF"
        self.last = ""
        self._ac, self._ena, self._stat = True, False, None
        self.add_coupling(self._step)

    # --- model -------------------------------------------------------------------------------

    def _step(self, dt, signals):
        ac = self.ac_power.value >= 0.5
        if ac != self._ac:
            self._ac = ac
            if ac:
                self._power_up()
            else:
                self.log.info("AC power off")
        ena = self.enable_open.value >= 0.5
        if ena and not self._ena and not self.ast:
            self.out_req = False                # 5.8: safe start needs OUT 1 afterwards
        self._ena = ena
        on = ac and self.out_req and not ena
        self.output.target = 1.0 if on else 0.0
        r = self.load.value
        v, i = self.pv.target, self.pc.target
        if not on:
            self.mode, tv, ti = "OFF", 0.0, 0.0
        elif r > 0 and v / r <= i:
            self.mode, tv, ti = "CV", v, v / r
        else:
            self.mode, tv, ti = "CC", i * r, i
        self.mv.target, self.mc.target = tv, ti
        self.feve |= self.fault_register() & self.fena
        stat = self.status_register()
        if self._stat is not None:
            self.seve |= (stat ^ self._stat) & self.sena
        self._stat = stat

    def _power_up(self):
        """5.11 / 5.13: settings come back, the address must be sent again, safe start keeps
        the output off, OVP is reset (5.3.3, method 3.2), event registers are cleared (7.8.3)."""
        self.log.info("AC power on: unaddressed")
        self.addressed = False
        if not self.ast:
            self.out_req = False
        self.latched = 0
        self.feve = self.seve = 0
        if self.rmt == "LLO":
            self.rmt = "REM"

    def fault_register(self):
        return self.latched | (FLT_ENA if self._ena else 0)

    def status_register(self):
        s = {"CV": ST_CV, "CC": ST_CC}.get(self.mode, 0)
        s |= ST_FLT if self.fault_register() & self.fena else ST_NFLT
        s |= (ST_AST if self.ast else 0) | (ST_FDE if self.fld else 0)
        return s | (ST_LCL if self.rmt == "LOC" else 0)

    def trip(self, unit):
        """OVP shutdown, 5.3.2: the output shuts down. Reset by OUT 1 (5.3.3)."""
        self.step_couplings()
        self.latched |= FLT_OVP
        self.out_req = False
        self.step_couplings()

    # --- protocol ----------------------------------------------------------------------------

    def handle(self, request, unit):
        if not self._ac:
            return None
        text = ""
        for ch in request.decode("latin-1").replace("\n", ""):
            text = text[:-1] if ch == "\b" else text + ch
        text = text.strip()
        m = re.fullmatch(r"(.*)\$([0-9A-Fa-f]{2})", text, re.S)
        if m:
            text = m.group(1)
            reply = "C04" if checksum(text) != m.group(2).upper() else self._command(text)
            return None if reply is None else reply + "$" + checksum(reply)
        return self._command(text)

    def _command(self, text):
        if text == "\\":
            text = self.last
        else:
            self.last = text
        cmd, _, arg = text.upper().partition(" ")
        arg = arg.strip()
        if cmd == "ADR":
            try:
                self.addressed = int(arg) == self.options["address"]
            except ValueError:
                return None
            return "OK" if self.addressed else None
        if not self.addressed:
            return None
        if cmd == "":
            return "OK"                         # 7.7.1: a CR by itself
        query = self._query(cmd)
        if query is not None:
            return "C01" if arg else query
        fn = self.COMMANDS.get(cmd)
        if fn is None:
            return "C01"
        if cmd in self.NEEDS_ARG and not arg:
            return "C02"
        reply = fn(self, arg)
        self.step_couplings()                   # new operating point from now on
        return reply

    def _fmt_v(self, v):
        return self.options["v_format"] % v

    def _fmt_i(self, i):
        return self.options["i_format"] % i

    def _query(self, cmd):
        o = self.options
        local = self.rmt == "LOC"
        if cmd == "PV?":
            return self._fmt_v(self.pv.target) if local else self.pv_str
        if cmd == "PC?":
            return self._fmt_i(self.pc.target) if local else self.pc_str
        if cmd == "MV?":
            return self._fmt_v(self.mv.read())
        if cmd == "MC?":
            return self._fmt_i(self.mc.read())
        if cmd == "DVC?":
            return "%s, %s, %s, %s, %s, %s" % (
                self._fmt_v(self.mv.read()), self._fmt_v(self.pv.target),
                self._fmt_i(self.mc.read()), self._fmt_i(self.pc.target),
                "%.3f" % self.ovp, "%.3f" % self.uvl)
        if cmd == "STT?":
            return "MV(%s),PV(%s),MC(%s),PC(%s),SR(%02X),FR(%02X)" % (
                self._fmt_v(self.mv.read()), self.pv_str, self._fmt_i(self.mc.read()),
                self.pc_str, self.status_register(), self.fault_register())
        if cmd == "OUT?":
            return "ON" if self.output.value >= 0.5 else "OFF"
        if cmd == "MODE?":
            return self.mode
        if cmd == "FLT?":
            return "%02X" % self.fault_register()
        if cmd == "STAT?":
            return "%02X" % self.status_register()
        if cmd == "FEVE?":
            v, self.feve = self.feve, 0
            return "%02X" % v
        if cmd == "SEVE?":
            v, self.seve = self.seve, 0
            return "%02X" % v
        simple = {
            "IDN?": o["idn"], "REV?": o["rev"], "SN?": o["sn"], "DATE?": o["date"],
            "RMT?": self.rmt, "MDAV?": "0", "MS?": "1",
            "OVP?": self.ovp_str, "UVL?": self.uvl_str,
            "AST?": "ON" if self.ast else "OFF", "FLD?": "ON" if self.fld else "OFF",
            "FENA?": "%02X" % self.fena, "SENA?": "%02X" % self.sena,
        }
        return simple.get(cmd)

    @staticmethod
    def _number(arg):
        if len(arg) > 12:
            return None
        try:
            return float(arg)
        except ValueError:
            return None

    def _remote(self):
        if self.rmt == "LOC":
            self.rmt = "REM"                    # 7.2.6: a command that affects the output

    def _pv(self, arg):
        v = self._number(arg)
        if v is None:
            return "C03"
        if v > 1.05 * self.options["v_rating"] or v > 0.95 * self.ovp:
            return "E01"
        if v < self.uvl:
            return "E02"
        self._remote()
        self.pv.target, self.pv_str = v, arg
        return "OK"

    def _pc(self, arg):
        i = self._number(arg)
        if i is None:
            return "C03"
        if i < 0 or i > 1.05 * self.options["i_rating"]:
            return "C05"
        self._remote()
        self.pc.target, self.pc_str = i, arg
        return "OK"

    def _out(self, arg):
        on = ON_OFF.get(arg)
        if on is None:
            return "C03"
        if on and self._ena:
            return "E07"                        # latching fault shutdown (ENA)
        self._remote()
        if on:
            self.latched = 0                    # 7.7.5: OUT 1 recovers from OVP and FLD
        self.out_req = on
        return "OK"

    def _ovp(self, arg):
        v = self._number(arg)
        if v is None:
            return "C03"
        if v < max(self.options["ovp_min"], 1.05 * self.pv.target):
            return "E04"
        if v > self.options["ovp_max"]:
            return "C05"
        self.ovp, self.ovp_str = v, arg
        return "OK"

    def _ovm(self, arg):
        self.ovp = self.options["ovp_max"]
        self.ovp_str = "%.1f" % self.ovp
        return "OK"

    def _uvl(self, arg):
        v = self._number(arg)
        if v is None:
            return "C03"
        if v > self.pv.target:
            return "E06"
        if v < 0 or v > self.options["uvl_max"]:
            return "C05"
        self.uvl, self.uvl_str = v, arg
        return "OK"

    def _rmt(self, arg):
        mode = RMT_MODES.get(arg)
        if mode is None:
            return "C03"
        self.rmt = mode
        return "OK"

    def _cls(self, arg):
        self.feve = self.seve = 0
        return "OK"

    def _rst(self, arg):
        """7.7.3: output 0 V, 0 A, off, remote, auto-start off, OVP max, foldback off, UVL 0."""
        self.pv.target, self.pv_str = 0.0, "0"
        self.pc.target, self.pc_str = 0.0, "0"
        self.out_req = False
        self.rmt = "REM"
        self.ast = self.fld = False
        self._ovm(arg)
        self.uvl, self.uvl_str = 0.0, "0"
        self.latched = 0                        # assumed as for GRST: OVP and FOLD are cleared
        return "OK"

    COMMANDS = {
        "PV": _pv, "PC": _pc, "OUT": _out, "OVP": _ovp, "OVM": _ovm, "UVL": _uvl,
        "AST": _flag("ast"), "FLD": _flag("fld"), "RMT": _rmt,
        "FENA": _hex_register("fena"), "SENA": _hex_register("sena"),
        "CLS": _cls, "RST": _rst,
    }
    NEEDS_ARG = {"PV", "PC", "OUT", "OVP", "UVL", "AST", "FLD", "RMT", "FENA", "SENA"}
