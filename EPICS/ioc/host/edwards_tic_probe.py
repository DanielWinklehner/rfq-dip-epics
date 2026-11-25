#!/usr/bin/env python3
"""Read-only first contact with an Edwards TIC controller on its RS-232 port.

    edwards_tic_probe.py /dev/ttyUSB0
    edwards_tic_probe.py /dev/ttyUSB0 --timeout 1.0

Sends queries only, each once, and nothing else: no command ("!C") and no setup ("!S"), so it
changes nothing on the controller, its pumps or its gauges. The queries are those that
EPICS/Db/tic.proto sends (task T29). Source of every object number and reply format: Edwards
"Turbo Instrument Controller (TIC) Serial Communications", D397-30-880 Issue H (2012), Table 1
"Objects accessed via the PC serial comms" and sections 1.6, 1.6.2.2, 1.6.2.3, 1.7.

    ?S902     identity: "TIC;<software version>;<serial number>;<PIC software version>" (1.6.2.2)
    ?V902     system status; the number of fields tells the variant (Table 1, object 902):
              TC 7, IC 8, TIC 10, IC6 14
    ?V913..915  gauge 1..3: "<value>;<units type>;<state>;<alert ID>;<priority>" (Table 1);
              units type 59 = pressure in pascal, 66 = voltage, 81 = percent (1.7.4)
    ?V904     turbo pump: "<state>;<alert ID>;<priority>" (1.6.2.3, states 1.7.8)
    ?S904 3   turbo pump type: "3;<pump type>" (1.6.2.3, types 1.7.11)
    ?V905     turbo speed: "<percent>;<alert ID>;<priority>" (Table 1)
    ?V910     backing pump: "<state>;<alert ID>;<priority>" (Table 1, states 0-4)
    ?S910 3   backing pump type: "3;<pump type>" (Table 1)

An object that a controller does not have (a TIC Instrument Controller has no turbo pump, a
TIC Turbo Controller no gauges) is answered with an error reply "*V<object> <code>" (Table 3),
which this program prints with its meaning; the manual does not say which code.

Line settings: 9600 baud, 8 data bits, no parity, 1 stop bit, Xon/Xoff, CR at the end of every
message (TIC Turbo Controller manual D397-12-880 Issue E, 2.4.5; D397-30-880, 1.2). Reply
timeout 500 ms, the manual's suggestion for a master (D397-30-880, 1.4).

Stop the IOC first: only one program may talk on the line.

Every reply is printed as it came, with the time from the request to the end of the reply, and
what it means. Exit code 0: every query was answered (a reply ending with CR, also an error
reply), 1: at least one was not, 2: the device cannot be opened. Python 3 standard library only.
"""

import argparse
import os
import re
import select
import sys
import termios
import time

PA_PER_TORR = 101325.0 / 760.0

# (query, what it asks for) in the order sent
QUERIES = [
    ("?S902", "identity"),
    ("?V902", "system status"),
    ("?V913", "gauge 1"),
    ("?V914", "gauge 2"),
    ("?V915", "gauge 3"),
    ("?V904", "turbo pump state"),
    ("?S904 3", "turbo pump type"),
    ("?V905", "turbo speed"),
    ("?V910", "backing pump state"),
    ("?S910 3", "backing pump type"),
]

# D397-30-880 Issue H, 1.7.1 Table 3
RESPONSE = {0: "no error", 1: "Invalid command for object ID", 2: "Invalid query/command",
            3: "Missing parameter", 4: "Parameter out of range",
            5: "Invalid command in current state", 6: "Data checksum error",
            7: "EEPROM read or write error", 8: "Operation took too long", 9: "Invalid config ID"}
# 1.7.4 SNVT values
UNITS = {59: "pressure, Pa", 66: "voltage", 81: "percent"}
# 1.7.6 State (backing pump: "State 0 - 4", Table 1, object 910)
STATE = {0: "Off State", 1: "Off Going On State", 2: "On Going Off Shutdown State",
         3: "On Going Off Normal State", 4: "On State"}
# 1.7.7 Active gauge states
GAUGE_STATE = {0: "Gauge Not connected", 1: "Gauge Connected", 2: "New Gauge Id",
               3: "Gauge Change", 4: "Gauge In Alert", 5: "Off", 6: "Striking",
               7: "Initialising", 8: "Calibrating", 9: "Zeroing", 10: "Degassing", 11: "On",
               12: "Inhibited"}
# 1.7.8 Full pump states
PUMP_STATE = {0: "Stopped", 1: "Starting Delay", 5: "Accelerating", 4: "Running",
              2: "Stopping Short Delay", 3: "Stopping Normal Delay", 6: "Fault Braking",
              7: "Braking"}
# 1.7.11 Pump types
PUMP_TYPE = {0: "No Pump", 1: "EXDC Pump", 3: "EXT75DX Pump", 4: "EXT255DX", 8: "Mains Backing Pump",
             9: "Serial Pump", 10: "nEXT - 485", 11: "nEXT - 232", 12: "nXDS",
             99: "Not yet identified"}
# Table 1, object 902: number of fields of the ?V902 reply
VARIANT = {7: "TC (TIC Turbo Controller)", 8: "IC (TIC Instrument Controller, 3 gauges)",
           10: "TIC (TIC Turbo & Instrument Controller)", 14: "IC6 (TIC Instrument Controller, 6 gauges)"}

NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def word(table, text):
    try:
        number = int(text)
    except ValueError:
        return "%r?" % text
    return "%d %s" % (number, table.get(number, "(not in the manual's table)"))


def meaning(query, reply):
    """(what the reply says, whether it has the form tic.proto expects)."""
    kind, obj = query[1], query[2:5]
    m = re.fullmatch(r"\*%s%s (\d{1,2})" % (kind, obj), reply)
    if m:
        code = int(m.group(1))
        return "error reply: %s" % RESPONSE.get(code, "code %d, not in Table 3" % code), True
    head = "=%s%s " % (kind, obj)
    if not reply.startswith(head):
        return "NOT THE FORM THE PROTOCOL FILE EXPECTS", False
    data = reply[len(head):]
    fields = data.split(";")
    if query == "?S902":
        names = ["type", "software", "serial", "PIC software"]
        return ", ".join("%s %s" % (n, f) for n, f in zip(names, fields)), len(fields) >= 2
    if query == "?V902":
        ok = all(re.fullmatch(r"\d+", f) for f in fields)
        return "%d fields: %s" % (len(fields), VARIANT.get(len(fields), "variant not known")), ok
    if obj in ("913", "914", "915"):
        if len(fields) != 5 or not re.fullmatch(NUMBER, fields[0]):
            return "NOT THE FORM THE PROTOCOL FILE EXPECTS", False
        value = float(fields[0])
        text = "state %s, units %s, alert %s, priority %s" % (
            word(GAUGE_STATE, fields[2]), word(UNITS, fields[1]), fields[3], fields[4])
        if fields[1] == "59" and fields[2] == "11":
            text = "%.3e torr (%s Pa), " % (value / PA_PER_TORR, fields[0]) + text
        else:                           # not a pressure, or the gauge is not on: no reading
            text = "value %s (no pressure reading), " % fields[0] + text
        return text, True
    if query.startswith("?S"):
        if len(fields) != 2 or fields[0] != "3":
            return "NOT THE FORM THE PROTOCOL FILE EXPECTS", False
        return "pump type %s" % word(PUMP_TYPE, fields[1]), True
    if len(fields) != 3:
        return "NOT THE FORM THE PROTOCOL FILE EXPECTS", False
    if obj == "905":
        return "speed %s %%, alert %s, priority %s" % tuple(fields), True
    table = PUMP_STATE if obj == "904" else STATE
    return "state %s, alert %s, priority %s" % (word(table, fields[0]), fields[1], fields[2]), True


def open_line(path):
    """The device, raw, 9600 8N1, Xon/Xoff from the controller honoured, modem lines ignored."""
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attr = termios.tcgetattr(fd)
    attr[0] = termios.IXON              # no input processing except Xon/Xoff (D397-12-880 2.4.5)
    attr[1] = attr[3] = 0               # no output or line processing, no echo
    attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attr[4] = attr[5] = termios.B9600
    attr[6][termios.VMIN] = attr[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attr)
    return fd


def ask(fd, request, timeout):
    """(reply without its CR, or what came before the timeout; complete; seconds)."""
    termios.tcflush(fd, termios.TCIFLUSH)
    start = time.monotonic()
    os.write(fd, request.encode("ascii") + b"\r")
    reply = b""
    while not reply.endswith(b"\r"):
        left = start + timeout - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            return reply.decode("ascii", "replace"), False, time.monotonic() - start
        reply += os.read(fd, 128)
    return reply[:-1].decode("ascii", "replace"), True, time.monotonic() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("device", help="serial device of the TIC's RS-232 port, e.g. /dev/ttyUSB0")
    parser.add_argument("--timeout", type=float, default=0.5, metavar="S",
                        help="reply timeout in seconds (default 0.5, the manual's suggestion)")
    args = parser.parse_args()

    try:
        fd = open_line(args.device)
    except (OSError, termios.error) as error:
        print("edwards_tic_probe: cannot open %s: %s" % (args.device, error), file=sys.stderr)
        return 2
    answered = expected = 0
    try:
        for query, what in QUERIES:
            reply, complete, seconds = ask(fd, query, args.timeout)
            if complete:
                answered += 1
                text, ok = meaning(query, reply)
                expected += ok
            else:
                text = "NO REPLY" if not reply else "NO CR AT THE END"
            print("%-8s %-19s %-34r %5.0f ms  %s" % (query, what, reply, 1000 * seconds, text))
    finally:
        os.close(fd)

    print("RESULT: %d of %d queries answered, %d in the form the protocol file expects"
          % (answered, len(QUERIES), expected))
    return 0 if answered == len(QUERIES) else 1


if __name__ == "__main__":
    sys.exit(main())
