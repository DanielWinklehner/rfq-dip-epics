#!/usr/bin/env python3
"""Runs edwards_tic_probe.py against a fake TIC on a pseudo-terminal, twice.

    python3 EPICS/ioc/host/edwards_tic_probe_test.py

1. A fake that answers every query as a TIC Turbo & Instrument Controller would (replies in
   the forms of D397-30-880 Issue H; the numbers are made up): the probe must exit with 0 and
   say that all queries were answered.
2. A fake that reads and never answers: the probe must print NO REPLY for every query and exit
   with 1.
The fake also checks that the probe sent queries only ("?"), never a command or setup ("!").
Exit code 0 when both runs behave so, 1 otherwise. Python 3 standard library only, Linux.
"""

import os
import subprocess
import sys
import threading

PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edwards_tic_probe.py")

REPLIES = {
    "?S902": "=S902 TIC;D39722000Z;FAKE0001;2.1",
    "?V902": "=V902 4;4;11;11;0;0;0;0;0;0",
    "?V913": "=V913 1.3332e-04;59;11;0;0",          # 1.0e-6 torr in pascal
    "?V914": "=V914 6.6661e-01;59;11;0;0",          # 5.0e-3 torr
    "?V915": "=V915 9.9000e+09;59;0;0;0",           # no gauge on socket 3
    "?V904": "=V904 4;0;0",
    "?S904 3": "=S904 3;11",
    "?V905": "=V905 100.0;0;0",
    "?V910": "=V910 4;0;0",
    "?S910 3": "=S910 3;8",
}


class Fake(threading.Thread):
    def __init__(self, master, answer):
        super().__init__(daemon=True)
        self.master, self.answer = master, answer
        self.received = []

    def run(self):
        buf = b""
        while True:
            try:
                data = os.read(self.master, 256)
            except OSError:
                return                                  # the probe closed the line
            if not data:
                return
            buf += data
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                text = line.decode("ascii", "replace")
                self.received.append(text)
                if self.answer and text in REPLIES:
                    os.write(self.master, REPLIES[text].encode("ascii") + b"\r")


def run(answer):
    master, slave = os.openpty()
    fake = Fake(master, answer)
    fake.start()
    try:
        result = subprocess.run([sys.executable, PROBE, os.ttyname(slave), "--timeout", "0.3"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                timeout=60)
    finally:
        os.close(slave)
        os.close(master)
    fake.join(2)
    print(result.stdout, end="")
    print("probe exit code %d, fake received %d messages" % (result.returncode, len(fake.received)))
    return result, fake.received


def main():
    good = True
    print("== 1. fake that answers")
    result, received = run(answer=True)
    if result.returncode != 0 or "RESULT: 10 of 10 queries answered, 10 in the form" not in result.stdout:
        print("FAIL: expected exit code 0 and 10 of 10 answered in the expected form")
        good = False
    if len(received) != 10 or any(not m.startswith("?") for m in received):
        print("FAIL: the probe sent something other than 10 queries: %r" % received)
        good = False
    print("== 2. fake that does not answer")
    result, received = run(answer=False)
    if result.returncode == 0 or "RESULT: 0 of 10 queries answered" not in result.stdout \
            or result.stdout.count("NO REPLY") != 10:
        print("FAIL: expected NO REPLY ten times, 0 of 10 answered and an exit code other than 0")
        good = False
    if any(not m.startswith("?") for m in received):
        print("FAIL: the probe sent something other than queries: %r" % received)
        good = False
    print("PASS" if good else "FAILED")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
