#!/usr/bin/env python3
"""Run inficon_vgc401_probe.py against a fake VGC401 on a pseudo-terminal. One command:

    EPICS/ioc/host/inficon_vgc401_fake.py            a fake that answers: exit code 0
    EPICS/ioc/host/inficon_vgc401_fake.py --silent   a fake that never answers: exit code 1

The exit code is that of the probe. The fake follows the operating manual tinb01e1-f
(2011-07), chapter 5 (pages there): after its start it sends "0,<value> <unit>" CR LF once per
second (p. 55, the format of COM p. 61; the unit text is assumed) until the first character
arrives; a request ends with CR, LF or CR LF (p. 57) and is answered <ACK><CR><LF>, or
<NAK><CR><LF> for an unknown mnemonic (p. 58); <ENQ> returns the data of the last request, or
the error word if there was none (p. 57). Its values (a Pirani gauge "PSG", Torr, 7.5e-3, the
firmware number 302-519-E of p. 2) are examples. Python 3 standard library only.
"""

import argparse
import os
import pty
import select
import subprocess
import sys
import threading
import time
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "inficon_vgc401_probe.py")

DATA = {"PR1": "0, 7.5000E-03", "UNI": "1", "TID": "PSG", "PNR": "302-519-E", "ERR": None}


def fake(master, silent, stop):
    """Serve the fake controller on the master side of the pty until `stop` is set."""
    heard = False                # the first character received ends the automatic output
    next_auto = time.monotonic() + 0.5     # the probe is listening by then
    buf, last, error = b"", None, "0000"
    while not stop.is_set():
        if not heard and not silent and time.monotonic() >= next_auto:
            os.write(master, b"0, 7.5000E-03 Torr\r\n")
            next_auto += 1.0
        if not select.select([master], [], [], 0.05)[0]:
            continue
        try:
            data = os.read(master, 256)
        except OSError:          # the probe closed the slave side
            time.sleep(0.05)
            continue
        heard = heard or bool(data)
        for byte in data:
            ch = bytes([byte])
            if ch == b"\x03":                    # <ETX> clears the input buffer (p. 57)
                buf = b""
            elif ch == b"\x05":                  # <ENQ>
                if last in (None, "ERR"):
                    reply, error = error, "0000"     # cancelled when read out (p. 63)
                else:
                    reply = DATA[last]
                if not silent:
                    os.write(master, reply.encode("ascii") + b"\r\n")
            elif ch in (b"\r", b"\n"):
                message, buf = buf.replace(b" ", b"").decode("ascii", "replace"), b""
                if not message:
                    continue                     # the LF of CR LF
                if message in DATA:
                    last, reply = message, b"\x06"
                else:
                    last, error, reply = None, "0001", b"\x15"   # SYN (p. 63)
                if not silent:
                    os.write(master, reply + b"\r\n")
            else:
                buf += ch


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--silent", action="store_true", help="the fake never answers")
    args = parser.parse_args()
    master, slave = pty.openpty()
    tty.setraw(slave)            # no echo, no CR/LF translation: a serial line, not a terminal
    path = os.ttyname(slave)
    stop = threading.Event()
    thread = threading.Thread(target=fake, args=(master, args.silent, stop), daemon=True)
    thread.start()
    print("fake VGC401 (%s) on %s" % ("silent" if args.silent else "answers", path), flush=True)
    try:
        status = subprocess.call([sys.executable, PROBE, path])
    finally:
        stop.set()
        thread.join(1.0)
        os.close(slave)
        os.close(master)
    print("probe exit code %d" % status)
    return status


if __name__ == "__main__":
    sys.exit(main())
