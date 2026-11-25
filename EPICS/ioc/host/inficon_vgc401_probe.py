#!/usr/bin/env python3
"""Read-only first contact with an INFICON VGC401 single-channel gauge controller over RS-232.

    inficon_vgc401_probe.py /dev/ttyUSB0             9600 baud (the controller's default)
    inficon_vgc401_probe.py /dev/ttyUSB0 19200       the rate set on the controller

Source: INFICON operating manual "Single-Channel Controller VGC401", tinb01e1-f (2011-07),
chapter 5 "Communication (Serial Interface)", pages 55 to 75. Page numbers below are its own.

Line (p. 55, 12): 1 start bit, 8 data bits, no parity, 1 stop bit, no hardware handshake;
9600 (default, p. 82), 19200 or 38400 baud, a setting of the controller (p. 44, 69).

What it does, in this order:
  1. listens for LISTEN_S seconds and sends nothing. After power-on the VGC401 sends the
     measured value every second by itself; the first character it receives stops that (p. 55).
     Every line that arrives is printed with its time.
  2. sends each read request once: PR1 (pressure and status, p. 60), UNI (pressure unit, p. 67),
     TID (gauge identification, p. 62), ERR (error word, p. 63), PNR (firmware number, p. 71).
     Each request is the mnemonic and CR (p. 57); the controller answers <ACK><CR><LF>
     (or <NAK><CR><LF>), then <ENQ> asks for the data, which ends with <CR><LF> (p. 57, 58).
     The raw replies are printed with the time each took; a missing reply is printed as such.
  3. a last line says how many requests were answered.

It sends no mnemonic with a parameter, so it changes no setting. Two things it does change,
both described in the manual and both undone by switching the controller off and on: the
first character it sends ends the automatic transmission of measured values (p. 55), and
reading ERR clears the error word (p. 63: "The ERROR word is cancelled when read out").

Stop the IOC first: only one program may use the line.

Exit code 0: all five requests answered in the form of the manual; 1: not; 2: the device
cannot be opened. Python 3 standard library only.
"""

import argparse
import os
import re
import select
import sys
import termios
import time

LISTEN_S = 3.0        # s, step 1. The controller sends once per second after power-on (p. 55).
REPLY_TIMEOUT = 1.0   # s, per reply. The manual gives no response time; a first contact waits long.

ACK, NAK, ENQ = b"\x06", b"\x15", b"\x05"          # p. 56
BAUD = {9600: termios.B9600, 19200: termios.B19200, 38400: termios.B38400}   # p. 12, 69

# p. 60: status digit of a measurement
STATUS = {"0": "measurement data okay", "1": "underrange", "2": "overrange",
          "3": "sensor error", "4": "sensor off (BAG, PEG)", "5": "no sensor",
          "6": "identification error", "7": "error BAG, BPG, HPG, BCG"}
UNITS = {"0": "mbar/bar", "1": "Torr", "2": "Pascal", "3": "Micron"}          # p. 67
GAUGES = {"PSG": "Pirani", "PCG": "Pirani/Capacitive", "PEG": "Cold cathode",  # p. 62
          "MPG": "Cold cathode/Pirani", "CDG": "Capacitive", "BAG": "Hot cathode",
          "BPG": "Hot cathode/Pirani", "BPG402": "Hot cathode/Pirani",
          "HPG": "Hot cathode/Pirani", "BCG": "Hot cathode/Pirani/Capacitive",
          "noSEn": "no sensor", "noid": "no identification"}
ERRORS = {"1000": "controller error (see the display)", "0100": "NO HWR, no hardware",   # p. 63
          "0010": "PAR, inadmissible parameter", "0001": "SYN, syntax error"}

# request -> (meaning, the data reply of the manual)
REQUESTS = {
    "PR1": ("pressure and status", r"([0-7]),([-+]?\d\.\d{4}E[-+]\d\d)"),   # p. 60
    "UNI": ("pressure unit", r"([0-3])"),                                   # p. 67
    "TID": ("gauge identification", r"(%s)" % "|".join(sorted(GAUGES, key=len, reverse=True))),
    "ERR": ("error word", r"([01]{4})"),                                    # p. 63
    "PNR": ("firmware number", r"(\d{3}-\d{3}-.{1,2})"),                     # p. 71
}


def open_line(path, baud):
    """The device, raw, 8N1, no flow control, modem lines ignored (p. 55)."""
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attr = termios.tcgetattr(fd)
    attr[0] = attr[1] = attr[3] = 0  # no input, output or line processing
    attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attr[4] = attr[5] = BAUD[baud]
    attr[6][termios.VMIN] = attr[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attr)
    return fd


class Line:
    """Reads lines that end with LF (the controller ends every reply with CR LF, p. 57)."""

    def __init__(self, fd):
        self.fd = fd
        self.buf = b""

    def read_line(self, deadline):
        """(bytes up to and with LF, or what came before the deadline; complete)."""
        while b"\n" not in self.buf:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([self.fd], [], [], left)[0]:
                rest, self.buf = self.buf, b""
                return rest, False
            data = os.read(self.fd, 256)
            if not data:
                time.sleep(0.01)
            self.buf += data
        line, self.buf = self.buf.split(b"\n", 1)
        return line + b"\n", True


def show(raw):
    return repr(raw)[1:]  # b'...' -> '...' with the control characters escaped


def listen(line, seconds):
    """Step 1: print what the controller sends by itself. Returns the number of lines."""
    print("1. listening %.0f s, sending nothing" % seconds)
    start = time.monotonic()
    n = 0
    while True:
        raw, complete = line.read_line(start + seconds)
        if raw:
            n += complete
            print("   %6.3f s  %-32s %s" % (time.monotonic() - start, show(raw),
                                            "" if complete else "(no LF before the end)"))
        if not complete:
            break
    if n:
        print("   -> the controller sends by itself: %d line(s). The first character of step 2"
              " ends that until it is switched off and on (manual p. 55)" % n)
    else:
        print("   -> nothing arrived: the controller does not send by itself (it was asked"
              " before, or the line, the cable or the baud rate is wrong)")
    return n


def ask(fd, line, mnemonic):
    """Step 2 for one request. Returns (ok, list of printed lines)."""
    meaning, form = REQUESTS[mnemonic]
    out = []
    termios.tcflush(fd, termios.TCIFLUSH)
    line.buf = b""
    start = time.monotonic()
    os.write(fd, mnemonic.encode("ascii") + b"\r")
    # the acknowledgement; a line of the automatic transmission may still arrive before it
    while True:
        raw, complete = line.read_line(start + REPLY_TIMEOUT)
        ms = 1000 * (time.monotonic() - start)
        if not complete:
            out.append("   %s  %-22s ack  %-24s %5.0f ms  %s" % (
                mnemonic, meaning, show(raw), ms, "NO REPLY" if not raw else "NO LF AT THE END"))
            return False, out
        if raw.rstrip(b"\r\n") in (ACK, NAK):
            break
        out.append("   %s  %-22s      %-24s %5.0f ms  (not an acknowledgement, ignored)" % (
            mnemonic, meaning, show(raw), ms))
    if raw.rstrip(b"\r\n") == NAK:
        out.append("   %s  %-22s ack  %-24s %5.0f ms  NAK: the controller refused the request" % (
            mnemonic, meaning, show(raw), ms))
        return False, out
    out.append("   %s  %-22s ack  %-24s %5.0f ms" % (mnemonic, meaning, show(raw), ms))
    start = time.monotonic()
    os.write(fd, ENQ)
    raw, complete = line.read_line(start + REPLY_TIMEOUT)
    ms = 1000 * (time.monotonic() - start)
    if not complete:
        out.append("   %s  %-22s data %-24s %5.0f ms  %s" % (
            mnemonic, meaning, show(raw), ms, "NO REPLY" if not raw else "NO LF AT THE END"))
        return False, out
    text = raw.decode("ascii", "replace")
    match = re.fullmatch(form, text.rstrip("\r\n")) if text.endswith("\r\n") else None
    out.append("   %s  %-22s data %-24s %5.0f ms  %s" % (
        mnemonic, meaning, show(raw), ms, explain(mnemonic, match) if match
        else "NOT THE FORM OF THE MANUAL"))
    return bool(match), out


def explain(mnemonic, match):
    value = match.group(1)
    if mnemonic == "PR1":
        return "status %s = %s, value %s in the controller's unit" % (
            value, STATUS[value], match.group(2))
    if mnemonic == "UNI":
        return UNITS[value]
    if mnemonic == "TID":
        return GAUGES[value]
    if mnemonic == "ERR":
        return "no error" if value == "0000" else ", ".join(
            text for bits, text in ERRORS.items() if int(bits, 2) & int(value, 2))
    return "firmware number and modification index"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("device", help="serial device of the USB to RS-232 adapter, e.g. /dev/ttyUSB0")
    parser.add_argument("baud", nargs="?", type=int, default=9600, choices=sorted(BAUD),
                        help="the controller's baud rate (default 9600, the factory setting)")
    args = parser.parse_args()

    try:
        fd = open_line(args.device, args.baud)
    except (OSError, termios.error) as error:
        print("inficon_vgc401_probe: cannot open %s: %s" % (args.device, error), file=sys.stderr)
        return 2
    print("INFICON VGC401 on %s, %d baud, 8N1, no handshake" % (args.device, args.baud))
    answered = 0
    try:
        line = Line(fd)
        listen(line, LISTEN_S)
        print("2. one request each; columns: request, meaning, part, raw reply, time, remark")
        for mnemonic in REQUESTS:
            ok, out = ask(fd, line, mnemonic)
            answered += ok
            print("\n".join(out))
    finally:
        os.close(fd)
    print("RESULT: %d of %d requests answered in the form of the manual" % (answered, len(REQUESTS)))
    return 0 if answered == len(REQUESTS) else 1


if __name__ == "__main__":
    sys.exit(main())
