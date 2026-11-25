"""INFICON VGC401 single-channel gauge controller, RS-232 (task T30).

Source: INFICON operating manual "Single-Channel Controller VGC401", tinb01e1-f (2011-07),
chapter 5 "Communication (Serial Interface)". Pages are the manual's:
  p. 55  after power-on it sends the measured value every 1 s by itself; the first character it
         receives stops that until COM starts it again. 8N1, no hardware handshake.
  p. 56  <ETX> 03, <ENQ> 05, <ACK> 06, <NAK> 15 hex; pressure format sx.xxxxEsxx.
  p. 57  three-character mnemonics, spaces ignored, <ETX> clears the input buffer, a message
         ends with <CR>, <LF> or <CR><LF>; acknowledged <ACK><CR><LF>; <ENQ> requests the data
         of the last mnemonic, repeated <ENQ> gives more; "If <ENQ> is received without a valid
         request, the ERROR word is transmitted."
  p. 58  an error is answered <NAK><CR><LF> and sets a flag in the ERROR word.
  p. 59  the list of mnemonics.
  p. 60  PR1 -> "x,sx.xxxxEsxx": status 0 okay, 1 underrange, 2 overrange, 3 sensor error,
         4 sensor off, 5 no sensor, 6 identification error, 7 error BAG, BPG, HPG, BCG. "The 3rd
         and 4th decimal are always 0, except for the CDG gauge."
  p. 61  COM [,x] -> continuous output "x,sx.xxxxEsxx y" (y: the unit) every 100 ms, 1 s, 1 min.
  p. 62  TID -> PSG, PCG, PEG, MPG, CDG, BAG, BPG, BPG402, HPG, BCG, noSEn, noid.
  p. 63  ERR -> 0000, 1000 controller error, 0100 no hardware, 0010 inadmissible parameter,
         0001 syntax error; cancelled when read out, set again at once if it persists.
  p. 67  UNI [,x] -> 0 mbar/bar, 1 Torr, 2 Pascal, 3 Micron.   p. 71  PNR -> "xxx-xxx-x".
  p. 75  the example dialogue (FOL,2 -> NAK; ENQ -> 0001).   p. 2, 82  firmware 302-519-E,
         default unit mbar.

Framing: a request ends with CR, LF or CR LF, and <ENQ> is a request of its own without a
terminator, so this module splits the input itself (_on_client below; the base class splits at
one terminator only). Every reply line gets CR LF.

Signals: pressure (torr, the true value; a plant model may drive it), status (the status digit
PR1 reports, 0..7; any number for a test), unit (the UNI number; any number for a test),
controller_error (1 = flag 1000 of the ERROR word), continuous (1 while it sends by itself),
power (set 0 then 1 = a power cycle: it sends by itself again if the option says so),
refuse_uni (1 = UNI answered <NAK>: a test hook), counters n_set (messages with a parameter,
and COM: everything that would change the controller), n_nak, n_enq.

Assumed, because the manual does not say: the value PR1 sends with status 3..7 (the pressure,
as with 0), the unit texts of the continuous output ("mbar", "Torr", "Pascal", "Micron"), the
serial value in Micron above 99000 Micron (p. 41 switches the readout to Torr; here it stays in
Micron), the response time, and what an empty message does (ignored). Mnemonics of p. 59 that
are not modelled (SP1, FIL, ...) are answered <NAK> and set the syntax flag; a parameter to a
mnemonic other than UNI and COM is acknowledged, counted in n_set and not applied.
With the option range_torr (task T31) the status follows the pressure at the ends of the head's
range (1 underrange, 2 overrange) and the value is the end of the range: both assumed, the range
a configuration value (config/rack.yaml).
"""

import math
import socket

from ..core import ConfigError, Simulator, register

ETX, ENQ, ACK, NAK = b"\x03", b"\x05", "\x06", "\x15"
GAUGES = ("PSG", "PCG", "PEG", "MPG", "CDG", "BAG", "BPG", "BPG402", "HPG", "BCG")     # p. 62
MNEMONICS = ("BAU", "COM", "COR", "DCD", "DGS", "ERR", "EUM", "FIL", "FSR", "FUM", "HVC", "ITR",
             "LOC", "OFS", "PNR", "PRE", "PR1", "RES", "SAV", "SP1", "SPS", "TAD", "TDI", "TEE",
             "TEP", "TID", "TIO", "TKB", "TLC", "TRA", "TRS", "UNI", "WDT")             # p. 59
READS = ("PR1", "UNI", "TID", "ERR", "PNR")
TORR_TO = {0: 1.0 / 0.750061683, 1: 1.0, 2: 1.0 / 0.00750061683, 3: 1000.0}            # p. 67
UNIT_TEXT = {0: "mbar", 1: "Torr", 2: "Pascal", 3: "Micron"}       # COM's "y": texts assumed
COM_INTERVAL = {0: 0.1, 1: 1.0, 2: 60.0}                                                # p. 61
ERR_CONTROLLER, ERR_HARDWARE, ERR_PARAMETER, ERR_SYNTAX = 8, 4, 2, 1                    # p. 63


@register("inficon_vgc401")
class InficonVgc401(Simulator):
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r\n",
                "turnaround_ms": 5.0}           # response time: not in the manual, assumed
    OPTIONS = {
        "gauge": "PSG",            # what TID reports (p. 62); the lab's head is not known
        "unit": 0,                 # UNI at power-on: 0 mbar (the default, p. 82), 1 Torr, 2 Pa, 3 Micron
        "pressure": 0.03,          # torr, the reading without a plant model
        "noise": 0.01,             # relative noise of one reading
        "continuous": True,        # sends by itself after power-on (p. 55)
        "com_mode": 1,             # interval of that output: 0 100 ms, 1 1 s (default), 2 1 min
        "firmware": "302-519-E",   # PNR (p. 71); the number of p. 2
        # [low, high] in torr: the measuring range of the gauge head (task T31). Below it PR1
        # reports status 1 (underrange), above it status 2 (overrange), each with the end of
        # the range as its value; null: no range, the status is the signal `status` alone. The
        # manual does not give the heads' ranges, nor the value sent with status 1 and 2.
        "range_torr": None,
    }

    def setup(self):
        o = self.options
        if o["gauge"] not in GAUGES:
            raise ConfigError("%s: gauge must be one of %s" % (self.name, ", ".join(GAUGES)))
        if o["unit"] not in TORR_TO:
            raise ConfigError("%s: unit must be 0, 1, 2 or 3 (p. 67)" % self.name)
        if o["com_mode"] not in COM_INTERVAL:
            raise ConfigError("%s: com_mode must be 0, 1 or 2 (p. 61)" % self.name)
        rng = o["range_torr"]
        if rng is not None and not (isinstance(rng, (list, tuple)) and len(rng) == 2 and 0 < rng[0] < rng[1]):
            raise ConfigError("%s: range_torr must be null or [low, high] with 0 < low < high" % self.name)
        self.pressure = self.add_signal("pressure", o["pressure"], lo=0.0)
        self.status = self.add_signal("status", 0.0)
        self.unit = self.add_signal("unit", float(o["unit"]))
        self.controller_error = self.add_signal("controller_error", 0.0)
        self.continuous = self.add_signal("continuous", 1.0 if o["continuous"] else 0.0)
        self.power = self.add_signal("power", 1.0)
        self.refuse_uni = self.add_signal("refuse_uni", 0.0)
        self.counters = {n: self.add_signal(n, 0.0) for n in ("n_set", "n_nak", "n_enq")}
        self.com_mode = o["com_mode"]
        self.pending = None          # the last accepted mnemonic, read out by <ENQ>
        self.error = 0               # the ERROR word, bits as ERR_*
        self._next_auto = 0.0
        self._was_on = True
        self.add_coupling(self._step)

    # --- power ---------------------------------------------------------------------------------

    def _step(self, dt, signals):
        on = self.power.value >= 0.5
        if on and not self._was_on:
            self.log.info("power on")
            self.pending, self.error = None, 0
            self.com_mode = self.options["com_mode"]
            self.continuous.target = 1.0 if self.options["continuous"] else 0.0
            self._next_auto = self.now()
        self._was_on = on

    def _count(self, name):
        self.counters[name].target = self.counters[name].value + 1

    # --- what it reports -----------------------------------------------------------------------

    def _unit(self):
        return int(self.unit.value)

    def reading(self):
        """(status digit, pressure in torr) as PR1 reports them: the signal `status`, and with
        the option range_torr status 1 or 2 and the end of the range outside it (assumed)."""
        status = int(self.status.value)
        p = max(0.0, self.pressure.value * (1.0 + self.rng.gauss(0.0, self.options["noise"])))
        rng = self.options["range_torr"]
        if rng is not None and status == 0:
            if p < rng[0]:
                status, p = 1, float(rng[0])
            elif p > rng[1]:
                status, p = 2, float(rng[1])
        return status, p

    def value_text(self, p=None):
        """sx.xxxxEsxx in the current unit (p. 56, 60); 3rd and 4th decimal 0 except CDG."""
        if p is None:
            p = max(0.0, self.pressure.value * (1.0 + self.rng.gauss(0.0, self.options["noise"])))
        p *= TORR_TO.get(self._unit(), 1.0)
        if self.options["gauge"] != "CDG":
            p = float("%.2E" % p)
        # Seen on the lab's VGC401 on 2026-11-25 (firmware 302-519-D): '0, 7.6400E+02', a blank
        # where the manual's form "sx.xxxxEsxx" has the sign of a positive value.
        return "% .4E" % p if math.isfinite(p) else " 9.9999E+99"

    def measurement(self):
        status, p = self.reading()
        return "%d,%s" % (status, self.value_text(p))        # p. 60

    def gauge(self):
        status = int(self.status.value)
        return {5: "noSEn", 6: "noid"}.get(status, self.options["gauge"])  # p. 62

    def error_word(self):
        """Read out and cancel; a persisting error is set again at once (p. 63)."""
        word = self.error | (ERR_CONTROLLER if self.controller_error.value >= 0.5 else 0)
        self.error = 0
        return "".join("1" if word & bit else "0" for bit in (8, 4, 2, 1))

    # --- requests ------------------------------------------------------------------------------

    def handle(self, request, unit):
        if self.power.value < 0.5:
            return None
        if request == ENQ:
            self._count("n_enq")
            if self.pending is None or self.pending == "ERR":
                return self.error_word()        # p. 57: no valid request -> the ERROR word
            return {"PR1": self.measurement, "UNI": lambda: "%d" % self._unit(),
                    "TID": self.gauge, "PNR": lambda: self.options["firmware"]}[self.pending]()
        message = request.decode("latin-1").replace(" ", "")        # p. 57: spaces ignored
        if not message:
            return None
        mnemonic, param = message[:3], message[3:]
        if mnemonic not in MNEMONICS or (param and not param.startswith(",")):
            return self._nak(ERR_SYNTAX)
        if param or mnemonic == "COM":
            self._count("n_set")
            return self._set(mnemonic, param[1:])
        if mnemonic not in READS or (mnemonic == "UNI" and self.refuse_uni.value >= 0.5):
            return self._nak(ERR_SYNTAX)
        self.pending = mnemonic
        return ACK

    def _nak(self, flag):
        self._count("n_nak")
        self.error |= flag
        self.pending = None
        return NAK

    def _set(self, mnemonic, arg):
        self.log.info("set %s %s", mnemonic, arg)
        if mnemonic == "UNI":
            if arg not in ("0", "1", "2", "3"):
                return self._nak(ERR_PARAMETER)
            if self.unit.external:
                self.unit.release()
            self.unit.target = float(arg)
        elif mnemonic == "COM":
            if arg not in ("", "0", "1", "2"):
                return self._nak(ERR_PARAMETER)
            self.com_mode = int(arg) if arg else self.com_mode
            self.continuous.target = 1.0
            self._next_auto = self.now() + COM_INTERVAL[self.com_mode]
        self.pending = mnemonic
        return ACK

    # --- the automatic transmission (p. 55, 61) ------------------------------------------------

    def tick(self, now):
        if self.power.value < 0.5 or self.continuous.value < 0.5:
            return now + 0.1
        if now >= self._next_auto:
            unit = self._unit()
            self.send("%s %s" % (self.measurement(), UNIT_TEXT.get(unit, "?")))
            self._next_auto = max(self._next_auto + COM_INTERVAL[self.com_mode], now)
        return min(self._next_auto, now + 0.1)

    def heard(self, data):
        """Any character received ends the automatic transmission (p. 55)."""
        if data and self.continuous.value >= 0.5:
            self.log.info("first character received: automatic transmission stops")
            self.continuous.target = 0.0

    @staticmethod
    def split(buf):
        """(complete requests, rest). CR, LF and CR LF end a message, <ENQ> is one by itself,
        <ETX> clears the input buffer (p. 57)."""
        requests, current = [], b""
        for byte in buf:
            ch = bytes([byte])
            if ch in (b"\r", b"\n"):
                if current:
                    requests.append(current)
                current = b""
            elif ch == ENQ:
                requests.append(ENQ)
            elif ch == ETX:
                current = b""
            else:
                current += ch
        return requests, current

    async def _on_client(self, reader, writer):
        """The base class's connection handler with this device's framing (split, heard)."""
        self.track_handler()
        if self.faulted("close"):
            writer.close()
            return
        self._drop_connection()
        self._conn_id += 1
        me = self._conn_id
        self._conn = writer
        sock = writer.get_extra_info("socket")
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.log.info("client %s connected", writer.get_extra_info("peername"))
        buf = b""
        try:
            while True:
                data = await reader.read(4096)
                if not data or me != self._conn_id:
                    break
                t = self._loop.time()
                self.stats.bytes_in += len(data)
                if self.power.value >= 0.5 and not self.faulted("silent"):
                    self.heard(data)
                requests, buf = self.split(buf + data)
                for request in requests:
                    self._queue.put_nowait(("req", t, me, request, None))
                if len(buf) > 65536:
                    buf = b""
        except (ConnectionError, OSError):
            pass
        finally:
            if me == self._conn_id:
                self._conn = None
                self.log.info("client disconnected")
            writer.close()
