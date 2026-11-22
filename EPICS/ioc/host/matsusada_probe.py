#!/usr/bin/env python3
"""Read-only first contact with Matsusada supplies behind a CO-U32 or USB-OPT adapter.

    matsusada_probe.py /dev/mist2/co-u32 3 4            device, then the unit numbers
    matsusada_probe.py /dev/mist2/co-u32 3 4 --repeat 100

Sends queries only (STS, SW?, CH0?, CH1?, MN1, MN2), with the line settings and the terminator
of EPICS/Db/matsusada_co_ctrl.proto: 9600 baud, 8 data bits, no parity, 1 stop bit, no flow
control, CR. It sends no set command and no REN, so it changes nothing on a supply.

Stop the IOC first: only one program may talk on a chain.

Every reply is printed as it came, with the time from the request to the end of the reply, and
compared with what the protocol file expects. Exit code 0: every unit answered every query in
that form, 1: not, 2: the device cannot be opened. Python 3 standard library only.
"""

import argparse
import os
import re
import select
import statistics
import sys
import termios
import time

REPLY_TIMEOUT = 0.5  # s. matsusada_co_ctrl.proto waits 150 ms; a first contact may take longer.

# query -> the reply matsusada_co_ctrl.proto expects ({unit} is the unit number)
QUERIES = {
    "STS": r"#{unit} (CF|CO) (RM|LO)",
    "SW?": r"SW[01]",
    "CH0?": r"CH0=([0-9A-F]{{4}})H",
    "CH1?": r"CH1=([0-9A-F]{{4}})H",
    "MN1": r"MONI1=([0-9A-F]{{3}})H",
    "MN2": r"MONI2=([0-9A-F]{{3}})H",
}
MEANING = {
    "STS": "output and control",
    "SW?": "output switch setting",
    "CH0?": "voltage setting",
    "CH1?": "current limit setting",
    "MN1": "voltage monitor",
    "MN2": "current monitor",
}


def open_line(path):
    """The device, raw, 9600 8N1, modem lines ignored."""
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attr = termios.tcgetattr(fd)
    attr[0] = attr[1] = attr[3] = 0  # no input, output or line processing
    attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attr[4] = attr[5] = termios.B9600
    attr[6][termios.VMIN] = attr[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attr)
    return fd


def ask(fd, request):
    """(reply without its CR, or what came before the timeout; complete; seconds)."""
    termios.tcflush(fd, termios.TCIFLUSH)
    start = time.monotonic()
    os.write(fd, request.encode("ascii") + b"\r")
    reply = b""
    while not reply.endswith(b"\r"):
        left = start + REPLY_TIMEOUT - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            return reply.decode("ascii", "replace"), False, time.monotonic() - start
        reply += os.read(fd, 64)
    return reply[:-1].decode("ascii", "replace"), True, time.monotonic() - start


def remark(query, unit, reply, complete):
    """What to say about one reply, and whether it is what the protocol file expects."""
    if not complete:
        return ("NO REPLY" if not reply else "NO CR AT THE END"), False
    match = re.fullmatch(QUERIES[query].format(unit=unit), reply)
    if not match:
        return "NOT THE FORM THE PROTOCOL FILE EXPECTS", False
    if match.lastindex and query not in ("STS", "SW?"):
        digits = match.group(1)
        return "%.2f %% of full scale" % (100 * int(digits, 16) / (16 ** len(digits) - 1)), True
    return "", True


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("device", help="serial device of the adapter, for example /dev/mist2/co-u32")
    parser.add_argument("units", nargs="+", type=int, help="unit numbers (UNIT switch of each supply)")
    parser.add_argument("--repeat", type=int, default=1, metavar="N",
                        help="ask every query N times and print the reply times (default 1)")
    args = parser.parse_args()

    try:
        fd = open_line(args.device)
    except (OSError, termios.error) as error:
        print("matsusada_probe: cannot open %s: %s" % (args.device, error), file=sys.stderr)
        return 2
    good = True
    times = []
    try:
        for unit in args.units:
            print("unit %d" % unit)
            for query in QUERIES:
                for turn in range(args.repeat):
                    reply, complete, seconds = ask(fd, "#%d %s" % (unit, query))
                    text, ok = remark(query, unit, reply, complete)
                    good = good and ok
                    if ok:
                        times.append(seconds)
                    if turn == 0 or not ok:
                        print("  %-5s %-22s %-14r %5.0f ms  %s"
                              % (query, MEANING[query], reply, 1000 * seconds, text))
    finally:
        os.close(fd)

    if len(times) > 1:
        print("reply time of %d good replies: min %.0f, median %.0f, max %.0f ms"
              % (len(times), 1000 * min(times), 1000 * statistics.median(times), 1000 * max(times)))
    print("RESULT: every unit answered every query in the expected form" if good
          else "RESULT: at least one reply is missing or has another form")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
