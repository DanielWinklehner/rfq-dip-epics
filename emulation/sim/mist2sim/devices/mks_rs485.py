"""MKS G-series mass flow controllers (GV50A, GE50A, GM50A) on one RS-485 multi-drop bus.

Source: "G-Series MFC RS-485 Digital Interface Supplement", MKS P/N 1046411-001 Rev. A, April 2013
(called "Sup" below, printed page numbers). What is not from there is marked ASSUMED.

Framing (Sup pp.5-9):
    request   @@@<addr><FNC>?<data>;<checksum>      query     e.g. @@@254S?;FF
              @@@<addr><FNC>!<data>;<checksum>      command   e.g. @@@254S!50;FF
    reply     @@@000ACK<data>;<checksum>   or   @@@000NAK<code>;<checksum>
At least one '@' (typically 1 to 3), a 3-digit address, an UPPER-CASE function of up to three
characters. Nothing follows the 2 checksum characters: no CR, no LF. The checksum "FF" means
"do not check", and the device then answers with "FF" too (Sup p.6, p.9).
Address 254 (the initial address of every unit): every unit receives the message and every unit
answers. Address 255: every unit executes, none answers (Sup p.12).

Simulator limits:
  * The line terminator is ";FF" in both directions, so only requests with the checksum FF are
    framed (the IOC always sends FF). A request with a real checksum is not recognised (it waits
    for ";FF"): computed checksums are not simulated.
  * Several units answering address 254 send their replies one after the other. On a real bus
    they would collide. So give every unit its own address before putting two on one bus.

Signals per unit (prefix "<address>."): setpoint (% FS), flow (% FS, measured), wink (0/1),
valve (0 NORMAL, 1 FLOW_OFF, 2 PURGE). A plant model reads setpoint and drives flow.
Fault "trip" on a unit: it answers NAK98 ("internal device error") to everything (ASSUMED
behaviour, used to test the NAK path).
"""

from ..core import ALL, ConfigError, Simulator, register

# NAK codes (Sup Table 4, p.8)
NAK_SYNTAX, NAK_INVALID_DATA, NAK_MODE, NAK_COMMAND, NAK_INTERNAL = 10, 12, 13, 17, 98

VALVE = ("NORMAL", "FLOW_OFF", "PURGE")       # VO (Sup Table 6)
UNIT_KEYS = {
    "address": None,       # 1..253, or 254 (the initial address of a unit)
    "full_scale": 100.0,   # FS? in flow units (Sup p.16: 0.1 to 500000)
    "flow_units": "SCCM",  # U? (SCCM or SLM)
    "gas": "N2",           # PG? (gas symbol, Sup Table C1)
    "tau_s": 1.0,          # ASSUMED: time constant of the flow following the set point
    "noise": 0.02,         # ASSUMED: noise of the measured flow, % FS
    "setpoint": -20.0,     # initial set point, % FS (Sup p.18: initial value -20.00 %)
}


def parse(request):
    """b'@@@254S!50' -> (254, 'S', '!', '50'), or None if there is no address to answer to."""
    text = request.decode("latin-1")
    body = text.lstrip("@")
    if body == text or len(body) < 3 or not body[:3].isdigit():
        return None
    addr, rest = int(body[:3]), body[3:]
    for i, c in enumerate(rest):
        if c in "!?":
            return addr, rest[:i], c, rest[i + 1:]
    return addr, rest, "", ""


@register("mks_rs485")
class MksRs485(Simulator):
    """One RS-485 bus with MKS G-series MFCs. Configuration: options.units, see UNIT_KEYS."""

    DEFAULTS = {"baud": 9600, "in_terminator": ";FF", "out_terminator": ";FF",
                "turnaround_ms": 5}       # ASSUMED: the supplement gives no reply delay
    OPTIONS = {
        "units": [{"address": 254}],
        "set_reply_echo": True,   # ASSUMED: the reply to a set ("!") carries the value set,
                                  # "@@@000ACK50;FF". Sup p.7: "data variable field (if relevant)"
        "vd_per_flow": 0.5,       # ASSUMED: VD? valve drive % = 10 + vd_per_flow * flow %
    }

    def setup(self):
        self.cfg = {}
        if not self.options["units"]:
            raise ConfigError("%s: units must be a non-empty list" % self.name)
        for spec in self.options["units"]:
            if not isinstance(spec, dict) or set(spec) - set(UNIT_KEYS):
                raise ConfigError("%s: a unit is a mapping with keys %s" % (self.name, ", ".join(UNIT_KEYS)))
            u = dict(UNIT_KEYS, **spec)
            a = u["address"]
            if isinstance(a, bool) or not isinstance(a, int) or not 1 <= a <= 254:
                raise ConfigError("%s: unit address must be 1..254, not %r" % (self.name, a))
            self.add_unit(a)
            self.cfg[a] = u
            sp = self.add_signal("%d.setpoint" % a, u["setpoint"], lo=-20.0, hi=140.0)
            flow = self.add_signal("%d.flow" % a, 0.0, tau=u["tau_s"], noise=u["noise"], lo=-20.0, hi=140.0)
            self.add_signal("%d.wink" % a, 0.0)
            valve = self.add_signal("%d.valve" % a, 0.0)
            u["cal_mode"] = False
            self.add_coupling(self._follow(sp, flow, valve))

    @staticmethod
    def _follow(sp, flow, valve):
        def fn(dt, signals):
            mode = int(valve.value)
            # ASSUMED: a negative set point closes the valve; PURGE (valve fully open) gives 140 %
            flow.target = 0.0 if mode == 1 else 140.0 if mode == 2 else max(0.0, sp.value)
        return fn

    def route(self, request):
        msg = parse(request)
        if msg is None:
            return None
        return ALL if msg[0] in (254, 255) else msg[0]

    def trip(self, unit):
        pass                      # handle() answers NAK98 while the fault is active

    def handle(self, request, unit):
        addr, fnc, kind, data = parse(request)
        if self.faulted("trip", unit):
            reply = "NAK%02d" % NAK_INTERNAL
        else:
            reply = self.command(unit, fnc, kind, data)
            if kind == "!":
                self.step_couplings()      # the flow starts to follow at once
        return None if addr == 255 else "@@@000" + reply

    def command(self, unit, fnc, kind, data):
        """One function of one unit -> 'ACK<data>' or 'NAK<code>'."""
        u = self.cfg[unit]
        sig = lambda name: self.signals["%d.%s" % (unit, name)]  # noqa: E731
        fs = float(u["full_scale"])
        if not fnc or fnc != fnc.upper() or len(fnc) > 3:
            return "NAK%02d" % NAK_COMMAND           # Sup p.5: functions must be upper case
        if kind not in "!?" or not kind:
            return "NAK%02d" % NAK_SYNTAX
        ack = lambda v: "ACK" + (v if kind == "?" or self.options["set_reply_echo"] else "")  # noqa: E731
        queries = {
            "F": lambda: "%.2f" % sig("flow").read(),                  # % FS
            "FX": lambda: "%.2f" % (sig("flow").read() * fs / 100.0),  # flow units
            "FS": lambda: "%g" % fs,
            "U": lambda: u["flow_units"],
            "VD": lambda: "%.1f" % min(100.0, 10.0 + self.options["vd_per_flow"] * sig("flow").value)
            if sig("flow").value > 0 else "0.0",
            "T": lambda: "O",                                         # status: O = OK
            "DT": lambda: "MFC",
            "MF": lambda: "MKS",
            "CA": lambda: "%03d" % unit,
        }
        if kind == "?":
            if fnc == "S":
                return ack("%.2f" % sig("setpoint").value)
            if fnc == "SX":
                return ack("%.2f" % (sig("setpoint").value * fs / 100.0))
            if fnc == "WK":
                return ack("ON" if sig("wink").value else "OFF")
            if fnc == "VO":
                return ack(VALVE[int(sig("valve").value)])
            if fnc == "OM":
                return ack("CAL_MODE" if u["cal_mode"] else "RUN_MODE")
            if fnc == "PG":                          # Sup p.15: only in Calibrate mode
                return ack(u["gas"]) if u["cal_mode"] else "NAK%02d" % NAK_MODE
            if fnc in queries:
                return ack(queries[fnc]())
            return "NAK%02d" % NAK_COMMAND
        # commands ("!")
        if fnc in ("S", "SX"):
            try:
                value = float(data)
            except ValueError:
                return "NAK%02d" % NAK_INVALID_DATA
            percent = value if fnc == "S" else value * 100.0 / fs
            lo, hi = (-20.0, 140.0) if fnc == "S" else (0.0, 100.0)   # Sup p.18, in % FS
            if not lo <= percent <= hi:
                return "NAK%02d" % NAK_INVALID_DATA  # ASSUMED code for out of range
            sig("setpoint").target = percent
            return ack(data)
        if fnc == "WK" and data in ("ON", "OFF"):
            sig("wink").target = 1.0 if data == "ON" else 0.0
            return ack(data)
        if fnc == "VO" and data in VALVE:
            sig("valve").target = VALVE.index(data)
            return ack(data)
        if fnc == "OM" and data in ("RUN_MODE", "CAL_MODE"):
            u["cal_mode"] = data == "CAL_MODE"
            return ack(data)
        if fnc in ("WK", "VO", "OM"):
            return "NAK%02d" % NAK_INVALID_DATA
        return "NAK%02d" % NAK_COMMAND
