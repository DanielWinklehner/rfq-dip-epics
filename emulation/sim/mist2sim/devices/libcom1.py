"""libcom1, the MIST Arduino communication library (AVR/libcom1, protocol 2).

Engine: a pure, deterministic model of SerialDevice::service(now_ms) without I/O or clock.
It is proven line by line against the real library by tools/replay_libcom1.py.
Libcom1Sim: the simulator type `libcom1`, a device fully described by its configuration.

protocol=1 models a board flashed with libcom1 before protocol 2 (the library of commit
9cb8f18^, which the rack computer held, reference/lab-2026/README.md): it knows `A`, `s` and
`q` only and answers every other command with ERR0 (AVR/libcom1/README.md: "g, S, I and P are
new in protocol version 2. Version 1 firmware answers them with ERR0"). Not modelled: protocol
1's handling of malformed `s` and `q` commands (atof, no syntax check, the one-digit exponent
bug). An IOC that polls with `A` never sends them.
"""

import math
import re
import struct
from collections import namedtuple

from ..core import REQUIRED, ConfigError, Simulator, register

# Result codes of libcom1_com.hpp. Everything below ERR_UNKNOWN is a valid command.
PRC_QUERY, PRC_SET, PRC_QALL, PRC_GET, PRC_SET_ACK, PRC_IDENT, PRC_PERIOD = 1, 2, 3, 4, 5, 6, 7
ERR_UNKNOWN, ERR_CHANNEL_LOOKUP, ERR_PRECISION_TOO_LARGE, ERR_BUFFER = 10, 11, 12, 13
ERR_NUM_CHANNELS, ERR_NO_DATA, ERR_SYNTAX, ERR_VALUE, ERR_NOT_SUPPORTED = 14, 15, 16, 17, 18

ERROR_TEXT = {
    ERR_UNKNOWN: "ERR0", ERR_PRECISION_TOO_LARGE: "ERR1", ERR_BUFFER: "ERR2",
    ERR_NUM_CHANNELS: "ERR3", ERR_CHANNEL_LOOKUP: "ERR4", ERR_SYNTAX: "ERR5",
    ERR_VALUE: "ERR6", ERR_NOT_SUPPORTED: "ERR7",
}

PROTOCOL_VERSION = 2
MAX_VALUE_CHARS = 13
U32 = 0xFFFFFFFF


def min_out_buffer_size(n):
    return n * (MAX_VALUE_CHARS + 1) + 2


def min_stream_buffer_size(n):
    return min_out_buffer_size(n) + 17


def f32(x):
    """Round to a 32-bit float, as the library stores every value."""
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


def _s32(x):
    x &= U32
    return x - (1 << 32) if x & 0x80000000 else x


def format_value(v, number_format):
    """detail::format_value(): "%g", or dtostre(v, 6, always sign) with trailing zeros removed."""
    if math.isnan(v):
        return "nan"
    if math.isinf(v):
        return "-inf" if v < 0 else "inf"
    if number_format == "g":
        return "%g" % v
    s = "%+.6e" % v                     # "+d.dddddde+dd", 13 characters
    zero_start = 9
    while zero_start != 3 and s[zero_start - 1] == "0":
        zero_start -= 1
    return s[:zero_start] + s[9:]


_SPACE = " \t\n\v\f\r"
_DEC = r"(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
_HEX = r"0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)(?:[pP][+-]?[0-9]+)?"
_SPECIAL = r"[iI][nN][fF](?:[iI][nN][iI][tT][yY])?|[nN][aA][nN](?:\([0-9A-Za-z_]*\))?"
_STRTOD = {
    "g": re.compile(r"[+-]?(?:%s|%s|%s)" % (_HEX, _DEC, _SPECIAL)),
    "avr": re.compile(r"[+-]?(?:%s|%s)" % (_DEC, _SPECIAL)),   # avr-libc: no hex floats
}


def strtod(text, start, number_format):
    """C strtod() on text[start:]: returns (value, end index); end == start if nothing parsed."""
    i = start
    while i < len(text) and text[i] in _SPACE:
        i += 1
    m = _STRTOD[number_format].match(text, i)
    if not m:
        return 0.0, start
    s = m.group(0)
    body = s.lstrip("+-").lower()
    if body.startswith("0x"):
        value = float.fromhex(s)
    elif body.startswith("nan"):
        value = math.nan
    else:
        value = float(s)            # decimal, "inf" and "infinity"
    return value, m.end()


def from_line_buffer(raw, size=128):
    """What LineBuffer<size> hands over for one received line (without its '\\n'):
    CR dropped, empty lines ignored (None), too long lines replaced by "!" (answered ERR0)."""
    line = raw.replace("\r", "")
    if not line:
        return None
    if len(line) > size - 1:
        return "!"
    return line


class Channel:
    """One channel: identifier character, digit, getter() -> float or None, setter(float) or None."""

    def __init__(self, iden, num, getter=None, setter=None):
        self.iden, self.num, self.getter, self.setter = iden, num, getter, setter

    @property
    def name(self):
        return "%s%d" % (self.iden, self.num)

    def get(self):
        return f32(self.getter()) if self.getter else 0.0


Output = namedtuple("Output", "reply frames code")


class Engine:
    """SerialDevice<out_buffer, len(channels)>. service(now_ms, line) does what
    SerialDevice::service(now_ms) does when the read function returns `line` (None = no line)."""

    def __init__(self, channels, identity="libcom1", firmware="0", number_format="g",
                 out_buffer=160, protocol=PROTOCOL_VERSION):
        if number_format not in ("g", "avr"):
            raise ValueError("number_format must be 'g' or 'avr'")
        if protocol not in (1, 2):
            raise ValueError("protocol must be 1 or 2")
        self.protocol = protocol
        if out_buffer < max(16, min_out_buffer_size(len(channels))):
            raise ValueError("out_buffer %d is too small for %d channels (needs %d)" % (
                out_buffer, len(channels), max(16, min_out_buffer_size(len(channels)))))
        names = [c.name for c in channels]
        if len(set(names)) != len(names):
            raise ValueError("channel identifiers are not unique: %s" % names)
        self.channels = list(channels)
        self.name, self.version = identity, firmware
        self.number_format = number_format
        self.size = out_buffer
        self.now = 0
        self.last_rx = 0
        self.timeout_ms = 0
        self.on_timeout = None
        self.stream_period = 0
        self.stream_next = 0
        self.seq = 0
        self.clock_started = False
        self.comm_lost = False
        self.stream_primed = False

    def set_comm_timeout(self, timeout_ms, on_timeout=None):
        self.timeout_ms = timeout_ms & U32
        self.on_timeout = on_timeout
        self.comm_lost = False

    def set_stream_period(self, period_ms):
        if period_ms != 0 and self.size < min_stream_buffer_size(len(self.channels)):
            return False
        self.stream_period = period_ms & U32
        self.stream_primed = False
        return True

    # --- main entry points -------------------------------------------------------------------

    def service(self, now_ms, line=None):
        now_ms &= U32
        self.now = now_ms
        if not self.clock_started:
            self.clock_started = True
            self.last_rx = now_ms
        code, reply = self.communicate(line)
        if self.timeout_ms and not self.comm_lost and \
                ((now_ms - self.last_rx) & U32) >= self.timeout_ms:
            self.comm_lost = True
            if self.on_timeout:
                self.on_timeout()
        frames = []
        if self.stream_period:
            if not self.stream_primed:
                self.stream_primed = True
                self.stream_next = (now_ms + self.stream_period) & U32
            elif _s32(now_ms - self.stream_next) >= 0:
                frame = self._stream_frame(now_ms)
                if frame is not None:
                    frames.append(frame)
                self.stream_next = (self.stream_next + self.stream_period) & U32
                if _s32(now_ms - self.stream_next) >= 0:
                    self.stream_next = (now_ms + self.stream_period) & U32
        return Output(reply, frames, code)

    def communicate(self, line):
        code, text = self._process(line)
        if code in (PRC_SET_ACK, PRC_PERIOD):
            text = "ok"
        elif code in ERROR_TEXT:
            text = ERROR_TEXT[code]
        elif code in (PRC_SET, ERR_NO_DATA):
            text = None
        if code < ERR_UNKNOWN:
            self.last_rx = self.now
            self.comm_lost = False
        return code, text

    def ms_until_due(self):
        """Milliseconds until service() has time-dependent work to do, or None."""
        due = []
        if self.stream_period:
            due.append(0 if not self.stream_primed else _s32(self.stream_next - self.now))
        if self.timeout_ms and not self.comm_lost:
            due.append(_s32(self.last_rx + self.timeout_ms - self.now))
        return max(0, min(due)) if due else None

    # --- commands ----------------------------------------------------------------------------

    def _process(self, line):
        if line is None:
            return ERR_NO_DATA, None
        s = line.split("\0", 1)[0]        # a C string ends at the first NUL
        if not s:
            return ERR_NO_DATA, None
        op = s[0]
        if self.protocol == 1 and op not in "qsA":
            return ERR_UNKNOWN, None      # protocol 1: process_input() knows q, s and A only
        if op == "q":
            return self._single_query(s)
        if op == "g":
            return self._plain_query(s)
        if op == "s":
            return self._setter(s)
        if op == "S":
            code, text = self._setter(s)
            return (PRC_SET_ACK if code == PRC_SET else code), text
        if op == "A":
            values = self._values(1)
            return (PRC_QALL, "o" + values) if values is not None else (ERR_BUFFER, None)
        if op == "I":
            return self._identify()
        if op == "P":
            return self._period(s)
        return ERR_UNKNOWN, None

    def _lookup(self, iden, digit):
        num = (ord(digit) - ord("0")) & 0xFF
        for ch in self.channels:
            if ch.iden == iden and ch.num == num:
                return ch
        return None

    def _values(self, pos):
        """"<v1>:...:<vN>" starting at buffer position pos, or None if it does not fit."""
        parts = []
        for ch in self.channels:
            if pos + MAX_VALUE_CHARS >= self.size:
                return None
            text = format_value(ch.get(), self.number_format)
            parts.append(text)
            pos += len(text) + 1
        return ":".join(parts)

    def _single_query(self, s):
        if len(s) < 6:
            return ERR_SYNTAX, None
        if s[1] != "0" or s[2] != "1":
            return ERR_NUM_CHANNELS, None
        precision = (ord(s[5]) - ord("0")) & 0xFF
        if precision > 6:
            return ERR_PRECISION_TOO_LARGE, None
        ch = self._lookup(s[3], s[4])
        if ch is None:
            return ERR_CHANNEL_LOOKUP, None
        if ch.getter is None:
            return ERR_NOT_SUPPORTED, None
        value = ch.get()
        if not math.isfinite(value):
            return ERR_VALUE, None
        text = "%+.*e" % (precision, value)
        coeff, _, exp = text.partition("e")
        if exp[:1] not in ("+", "-") or not exp[1:].isdigit() or int(exp[1:]) > 9:
            return ERR_VALUE, None
        return PRC_QUERY, "o" + s[3] + s[4] + coeff.replace(".", "") + str(int(exp[1:])) + exp[0]

    def _plain_query(self, s):
        if len(s) < 3:
            return ERR_SYNTAX, None
        ch = self._lookup(s[1], s[2])
        if ch is None:
            return ERR_CHANNEL_LOOKUP, None
        if ch.getter is None:
            return ERR_NOT_SUPPORTED, None
        return PRC_GET, "o" + format_value(ch.get(), self.number_format)

    def _setter(self, s):
        if len(s) < 4:
            return ERR_SYNTAX, None
        value, end = strtod(s, 3, self.number_format)
        if end == 3:
            return ERR_SYNTAX, None
        value = f32(value)
        while end < len(s) and s[end] in " \t\r":
            end += 1
        if end != len(s) or not math.isfinite(value):
            return ERR_SYNTAX, None
        ch = self._lookup(s[1], s[2])
        if ch is None:
            return ERR_CHANNEL_LOOKUP, None
        if ch.setter is None:
            # protocol 1 has no ERR7: every channel of its sketches has a setter, a dummy one for
            # the readings (FlowMeters.ino: dummySetFunc), so the set is taken and ignored
            return (PRC_SET, None) if self.protocol == 1 else (ERR_NOT_SUPPORTED, None)
        ch.setter(value)
        return PRC_SET, None

    def _identify(self):
        text = "oID=%s;FW=%s;PROTO=%d;CH=%s" % (
            self.name, self.version, PROTOCOL_VERSION, ",".join(c.name for c in self.channels))
        return (PRC_IDENT, text) if len(text) <= self.size - 1 else (ERR_BUFFER, None)

    def _period(self, s):
        if len(s) < 2 or not "0" <= s[1] <= "9":
            return ERR_SYNTAX, None
        end = 1
        while end < len(s) and "0" <= s[end] <= "9":
            end += 1
        period = min(int(s[1:end]), U32)   # strtoul saturates (unsigned long is 32 bit on AVR and Opta)
        while end < len(s) and s[end] in " \t\r":
            end += 1
        if end != len(s):
            return ERR_SYNTAX, None
        return (PRC_PERIOD, None) if self.set_stream_period(period) else (ERR_BUFFER, None)

    def _stream_frame(self, now_ms):
        prefix = "t%d:%d:" % (self.seq, now_ms)
        self.seq = (self.seq + 1) & 0xFFFF
        if len(prefix) > self.size - 1:
            return None
        values = self._values(len(prefix))
        return None if values is None else prefix + values


# --- the simulator type -----------------------------------------------------------------------

BEHAVIOURS = {
    # behaviour: (default access, allowed keys besides id/access/behaviour)
    "constant": ("r", {"value"}),
    "analog": ("r", {"value", "noise", "tau", "lo", "hi", "step"}),
    "readback": ("rw", {"value", "tau", "lo", "hi", "step"}),
    "relay": ("rw", {"value"}),
}


@register("libcom1")
class Libcom1Sim(Simulator):
    """A libcom1 device (valve box, thermocouple board, Opta ...) described by configuration."""

    DEFAULTS = {"baud": 115200, "in_terminator": "\n", "out_terminator": "\r\n"}
    OPTIONS = {
        "identity": "libcom1",        # name reported by "I"
        "firmware": "0",              # FW= reported by "I" (the sketches use __DATE__)
        "number_format": "avr",       # "avr" (dtostre) or "g" (%g, Arduino Opta)
        "out_buffer": 160,            # IOHandler / SerialDevice output buffer size
        "in_buffer": 128,             # LineBuffer size: lines up to in_buffer - 1 characters
        "comm_timeout_ms": 0,         # set_comm_timeout(), 0 = off
        "on_timeout": {},             # {channel: value} written when the timeout fires
        "channels": REQUIRED,         # list in query-all order, see README.md
        "protocol": 2,                # 1: a board flashed before protocol 2 (A, s, q only)
    }

    def setup(self):
        o = self.options
        if o["number_format"] not in ("avr", "g"):
            raise ConfigError("%s: number_format must be 'avr' or 'g'" % self.name)
        if not o["channels"]:
            raise ConfigError("%s: channels must be a non-empty list" % self.name)
        if o["protocol"] not in (1, 2) or isinstance(o["protocol"], bool):
            raise ConfigError("%s: protocol must be 1 or 2" % self.name)
        if o["protocol"] == 1 and o["comm_timeout_ms"]:
            raise ConfigError("%s: protocol 1 has no communication timeout" % self.name)
        channels = [self._channel(i, spec) for i, spec in enumerate(o["channels"], 1)]
        try:
            self.engine = Engine(channels, str(o["identity"]), str(o["firmware"]),
                                 o["number_format"], int(o["out_buffer"]), int(o["protocol"]))
        except ValueError as exc:
            raise ConfigError("%s: %s" % (self.name, exc)) from None
        if int(o["in_buffer"]) < 8:
            raise ConfigError("%s: in_buffer must be at least 8" % self.name)
        by_name = {c.name: c for c in channels}
        for name, value in o["on_timeout"].items():
            if name not in by_name or not isinstance(value, (int, float)):
                raise ConfigError("%s: on_timeout: %r is not a channel with a number" % (self.name, name))

        def outputs_off():
            for name, value in o["on_timeout"].items():
                ch = by_name[name]
                if ch.setter:
                    ch.setter(f32(value))
                self.log.info("communication timeout: %s = %g", name, value)

        if o["comm_timeout_ms"]:
            self.engine.set_comm_timeout(int(o["comm_timeout_ms"]), outputs_off)

    def _channel(self, i, spec):
        where = "%s: channel %d" % (self.name, i)
        if not isinstance(spec, dict):
            raise ConfigError("%s: expected a mapping" % where)
        cid = spec.get("id")
        if not isinstance(cid, str) or len(cid) != 2 or not cid[1].isdigit() or cid[0] == "\0":
            raise ConfigError("%s: id must be one character and one digit, like s1" % where)
        behaviour = spec.get("behaviour", "constant")
        if behaviour not in BEHAVIOURS:
            raise ConfigError("%s (%s): behaviour must be one of %s" % (where, cid, ", ".join(BEHAVIOURS)))
        access, allowed = BEHAVIOURS[behaviour]
        unknown = sorted(set(spec) - allowed - {"id", "access", "behaviour"})
        if unknown:
            raise ConfigError("%s (%s): unknown key(s) %s for behaviour %s; allowed: %s" % (
                where, cid, ", ".join(unknown), behaviour, ", ".join(sorted(allowed | {"id", "access", "behaviour"}))))
        access = spec.get("access", access)
        if access not in ("r", "w", "rw"):
            raise ConfigError("%s (%s): access must be r, w or rw" % (where, cid))
        params = {k: v for k, v in spec.items() if k in allowed}
        for k, v in params.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ConfigError("%s (%s): %s must be a number" % (where, cid, k))
        try:
            sig = self.add_signal(cid, **params)
        except TypeError as exc:
            raise ConfigError("%s (%s): %s" % (where, cid, exc)) from None

        def write(v):
            if behaviour == "readback":
                sig.target = v
            elif behaviour == "relay":
                sig.target = 1.0 if v == 1.0 else 0.0   # as set_solenoid() in the valve box
            # constant, analog: accepted and ignored (like dummy_set in the thermocouple sketch)

        return Channel(cid[0], int(cid[1]), sig.read if "r" in access else None,
                       write if "w" in access else None)

    def _ms(self, now=None):
        return int((self.now() if now is None else now) * 1000) & U32

    def handle(self, request, unit):
        line = from_line_buffer(request.decode("latin-1"), int(self.options["in_buffer"]))
        out = self.engine.service(self._ms(), line)
        if self.engine.protocol == 1 and out.code == ERR_UNKNOWN:
            # what the board as flashed cannot answer, for the device cases to look for
            self.log.info("protocol 1: %r answered ERR0", line)
        for frame in out.frames:
            self.send(frame)
        return out.reply

    def tick(self, now):
        out = self.engine.service(self._ms(now))
        for frame in out.frames:
            self.send(frame)
        due = self.engine.ms_until_due()
        return None if due is None else now + due / 1000.0 + 0.0005
