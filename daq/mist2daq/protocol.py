"""libcom1 protocol version 2, the device side, without I/O and without a clock.

What a device answers is defined by AVR/libcom1/README.md and its library (libcom1_com.hpp).
This module does what SerialDevice::service(now_ms) does for one received line, with the number
format of the Arduino Opta ("%g", LIBCOM1_USE_DTOSTRE=0), so that the IOC can use the unmodified
EPICS/Db/libcom1.proto and libcom1_device.db.

Its replies are compared with the real library (daq/tools/compare_libcom1.sh) and with the
libcom1 simulator of the emulation (daq/tests/test_against_simulator.py).

One addition the library does not have: a setter may raise Refused(code). The set is then
answered with that error and counts as not executed (used for a value outside a channel's
limits, ERR5, and for a write the hardware did not take, ERR7: docs/emulation/DAQ.md).
"""

import math
import re
import struct

# Result codes as in libcom1_com.hpp. Everything below ERR_UNKNOWN is a valid command.
PRC_QUERY, PRC_SET, PRC_QALL, PRC_GET, PRC_SET_ACK, PRC_IDENT, PRC_PERIOD = 1, 2, 3, 4, 5, 6, 7
ERR_UNKNOWN, ERR_CHANNEL_LOOKUP, ERR_PRECISION_TOO_LARGE, ERR_BUFFER = 10, 11, 12, 13
ERR_NUM_CHANNELS, ERR_NO_DATA, ERR_SYNTAX, ERR_VALUE, ERR_NOT_SUPPORTED = 14, 15, 16, 17, 18

# What the device sends for each error (README, "Error replies")
ERROR_TEXT = {
    ERR_UNKNOWN: "ERR0", ERR_PRECISION_TOO_LARGE: "ERR1", ERR_BUFFER: "ERR2",
    ERR_NUM_CHANNELS: "ERR3", ERR_CHANNEL_LOOKUP: "ERR4", ERR_SYNTAX: "ERR5",
    ERR_VALUE: "ERR6", ERR_NOT_SUPPORTED: "ERR7",
}

PROTOCOL_VERSION = 2
MAX_VALUE_CHARS = 13          # longest "%g" of a float, "-1.17549e-38"
U32 = 0xFFFFFFFF


def min_out_buffer_size(n):
    """README, Buffers: 14 bytes per channel plus 2."""
    return n * (MAX_VALUE_CHARS + 1) + 2


def min_stream_buffer_size(n):
    return min_out_buffer_size(n) + 17


def f32(x):
    """The library keeps every value as a 32-bit float."""
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


def format_value(v):
    """"%g", nan, inf, -inf (README, Commands)."""
    if math.isnan(v):
        return "nan"
    if math.isinf(v):
        return "-inf" if v < 0 else "inf"
    return "%g" % v


# C strtod() as glibc and the Opta's newlib read a number: decimal, hexadecimal, inf, nan
_NUMBER = re.compile(
    r"[ \t\n\v\f\r]*([+-]?(?:0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)(?:[pP][+-]?[0-9]+)?"
    r"|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
    r"|[iI][nN][fF](?:[iI][nN][iI][tT][yY])?|[nN][aA][nN](?:\([0-9A-Za-z_]*\))?))")


def strtod(text, start):
    """(value, end); end == start when nothing could be read."""
    m = _NUMBER.match(text, start)
    if not m:
        return 0.0, start
    s = m.group(1)
    body = s.lstrip("+-").lower()
    if body.startswith("0x"):
        value = float.fromhex(s)
    elif body.startswith("nan"):
        value = math.nan
    else:
        value = float(s)
    return value, m.end()


class Refused(Exception):
    """Raised by a setter: the set is answered with `code` and the setter's effect is void."""

    def __init__(self, code, reason=""):
        super().__init__(reason or ERROR_TEXT.get(code, str(code)))
        self.code = code
        self.reason = reason


class Channel:
    """One channel: identification character, digit, getter() -> float, setter(float) or None."""

    def __init__(self, iden, num, getter=None, setter=None):
        self.iden, self.num, self.getter, self.setter = iden, num, getter, setter

    @property
    def name(self):
        return "%s%d" % (self.iden, self.num)

    def get(self):
        return f32(self.getter()) if self.getter else 0.0


class LineReader:
    """LineBuffer<size> for a byte stream: complete lines only, CR dropped, empty lines ignored,
    a line longer than size - 1 characters replaced by "!" (answered ERR0, never executed)."""

    TOO_LONG = "!"

    def __init__(self, size=128):
        self.size = size
        self.buf = bytearray()
        self.overflow = False

    def feed(self, data):
        parts = data.split(b"\n")
        lines = [self._end_line(chunk) for chunk in parts[:-1]]
        self._add(parts[-1])
        return [l for l in lines if l is not None]

    def _add(self, chunk):
        if self.overflow:
            return
        self.buf += chunk.replace(b"\r", b"")
        if len(self.buf) > self.size - 1:
            self.overflow = True
            self.buf = bytearray()

    def _end_line(self, chunk):
        self._add(chunk)
        line, overflow = bytes(self.buf).decode("latin-1"), self.overflow
        self.buf, self.overflow = bytearray(), False
        if overflow:
            return self.TOO_LONG
        return line or None


class Device:
    """SerialDevice of libcom1. service(now_ms, line) does what SerialDevice::service(now_ms)
    does when the read function returns `line` (None or "" = nothing received). It returns
    (reply or None, [stream frames], result code)."""

    def __init__(self, channels, identity, firmware, out_buffer=None, refresh=None):
        names = [c.name for c in channels]
        if len(set(names)) != len(names):
            raise ValueError("channel identifiers are not unique: %s" % names)
        need = max(16, min_stream_buffer_size(len(channels)))
        self.size = need if out_buffer is None else out_buffer
        if self.size < max(16, min_out_buffer_size(len(channels))):
            raise ValueError("out_buffer %d is too small for %d channels" % (self.size, len(channels)))
        self.channels = list(channels)
        self.identity, self.firmware = identity, firmware
        self.refresh = refresh          # called before values are read (A, g, q, a frame)
        self.now = 0
        self.last_rx = 0
        self.clock_started = False
        self.timeout_ms = 0
        self.on_timeout = None
        self.comm_lost = False
        self.stream_period = 0
        self.stream_primed = False
        self.stream_next = 0
        self.seq = 0

    # --- settings ---------------------------------------------------------------------------

    def set_comm_timeout(self, timeout_ms, on_timeout=None):
        self.timeout_ms = int(timeout_ms) & U32
        self.on_timeout = on_timeout
        self.comm_lost = False

    def set_stream_period(self, period_ms):
        if period_ms != 0 and self.size < min_stream_buffer_size(len(self.channels)):
            return False
        self.stream_period = period_ms & U32
        self.stream_primed = False
        return True

    # --- the main entry -----------------------------------------------------------------------

    def service(self, now_ms, line=None):
        now_ms &= U32
        self.now = now_ms
        if not self.clock_started:
            self.clock_started = True
            self.last_rx = now_ms
        code, reply = self._process(line)
        if code in (PRC_SET_ACK, PRC_PERIOD):
            reply = "ok"
        elif code in ERROR_TEXT:
            reply = ERROR_TEXT[code]
        elif code in (PRC_SET, ERR_NO_DATA):
            reply = None
        if code < ERR_UNKNOWN:                  # a valid command is a sign of life
            self.last_rx = now_ms
            self.comm_lost = False
        if self.timeout_ms and not self.comm_lost and ((now_ms - self.last_rx) & U32) >= self.timeout_ms:
            self.comm_lost = True
            if self.on_timeout:
                self.on_timeout()
        frames = []
        if self.stream_period:
            if not self.stream_primed:
                self.stream_primed = True
                self.stream_next = (now_ms + self.stream_period) & U32
            elif _s32(now_ms - self.stream_next) >= 0:
                frame = self._frame(now_ms)
                if frame is not None:
                    frames.append(frame)
                self.stream_next = (self.stream_next + self.stream_period) & U32
                if _s32(now_ms - self.stream_next) >= 0:
                    self.stream_next = (now_ms + self.stream_period) & U32
        return reply, frames, code

    def ms_until_due(self):
        """Milliseconds until service() has time-dependent work, or None."""
        due = []
        if self.stream_period:
            due.append(0 if not self.stream_primed else _s32(self.stream_next - self.now))
        if self.timeout_ms and not self.comm_lost:
            due.append(_s32(self.last_rx + self.timeout_ms - self.now))
        return max(0, min(due)) if due else None

    # --- commands ---------------------------------------------------------------------------

    def _process(self, line):
        if not line:
            return ERR_NO_DATA, None
        s = line.split("\0", 1)[0]              # a C string ends at its first NUL
        if not s:
            return ERR_NO_DATA, None
        op = s[0]
        if op == "A":
            self._refresh()
            values = self._values(1)
            return (PRC_QALL, "o" + values) if values is not None else (ERR_BUFFER, None)
        if op == "g":
            return self._get(s)
        if op in "sS":
            code, text = self._set(s)
            return (PRC_SET_ACK if op == "S" and code == PRC_SET else code), text
        if op == "I":
            text = "oID=%s;FW=%s;PROTO=%d;CH=%s" % (
                self.identity, self.firmware, PROTOCOL_VERSION, ",".join(c.name for c in self.channels))
            return (PRC_IDENT, text) if len(text) <= self.size - 1 else (ERR_BUFFER, None)
        if op == "P":
            return self._period(s)
        if op == "q":
            return self._legacy_query(s)
        return ERR_UNKNOWN, None

    def _refresh(self):
        if self.refresh:
            self.refresh()

    def _lookup(self, iden, digit):
        num = (ord(digit) - ord("0")) & 0xFF
        for ch in self.channels:
            if ch.iden == iden and ch.num == num:
                return ch
        return None

    def _values(self, pos):
        parts = []
        for ch in self.channels:
            if pos + MAX_VALUE_CHARS >= self.size:
                return None
            text = format_value(ch.get())
            parts.append(text)
            pos += len(text) + 1
        return ":".join(parts)

    def _get(self, s):
        if len(s) < 3:
            return ERR_SYNTAX, None
        ch = self._lookup(s[1], s[2])
        if ch is None:
            return ERR_CHANNEL_LOOKUP, None
        if ch.getter is None:
            return ERR_NOT_SUPPORTED, None
        self._refresh()
        return PRC_GET, "o" + format_value(ch.get())

    def _set(self, s):
        if len(s) < 4:
            return ERR_SYNTAX, None
        value, end = strtod(s, 3)
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
            return ERR_NOT_SUPPORTED, None
        try:
            ch.setter(value)
        except Refused as exc:
            return exc.code, None
        return PRC_SET, None

    def _period(self, s):
        if len(s) < 2 or not "0" <= s[1] <= "9":
            return ERR_SYNTAX, None
        end = 1
        while end < len(s) and "0" <= s[end] <= "9":
            end += 1
        period = min(int(s[1:end]), U32)        # strtoul saturates (32-bit unsigned long)
        while end < len(s) and s[end] in " \t\r":
            end += 1
        if end != len(s):
            return ERR_SYNTAX, None
        return (PRC_PERIOD, None) if self.set_stream_period(period) else (ERR_BUFFER, None)

    def _legacy_query(self, s):
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
        self._refresh()
        value = ch.get()
        if not math.isfinite(value):
            return ERR_VALUE, None
        coeff, _, exp = ("%+.*e" % (precision, value)).partition("e")
        if int(exp[1:]) > 9:
            return ERR_VALUE, None
        return PRC_QUERY, "o" + s[3] + s[4] + coeff.replace(".", "") + str(int(exp[1:])) + exp[0]

    def _frame(self, now_ms):
        prefix = "t%d:%d:" % (self.seq, now_ms)
        self.seq = (self.seq + 1) & 0xFFFF
        if len(prefix) > self.size - 1:
            return None
        self._refresh()
        values = self._values(len(prefix))
        return None if values is None else prefix + values


def _s32(x):
    x &= U32
    return x - (1 << 32) if x & 0x80000000 else x
