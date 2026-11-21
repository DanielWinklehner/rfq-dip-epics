"""Test devices and a small line client shared by the tests."""

import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mist2sim.core import ALL, Simulator, register  # noqa: E402


@register("test_echo")
class Echo(Simulator):
    """Replies "re:<request>", "quiet" gets no reply, "two" gets two lines, "trip" is supported."""

    OPTIONS = {"greeting": "hi"}

    def setup(self):
        self.out = self.add_signal("out", 5.0)
        self.tripped = 0
        self.cleared = 0

    def handle(self, request, unit):
        if request == b"quiet":
            return None
        if request == b"two":
            return [b"one", "two"]
        if request == b"boom":
            raise RuntimeError("device bug")
        if request == b"say":
            self.send("unsolicited")
            return "said"
        return b"re:" + request

    def trip(self, unit):
        self.tripped += 1
        self.out.target = 0.0

    def trip_cleared(self, unit):
        self.cleared += 1


@register("test_bus")
class Bus(Simulator):
    """'#<n> Q' -> '#<n> A', '#AL X' -> every unit executes, no reply."""

    OPTIONS = {"units": [1, 2, 3]}

    def setup(self):
        self.hits = {}
        for u in self.options["units"]:
            self.add_unit(u)
            self.add_signal("%d.v" % u, float(u))

    def route(self, request):
        head = request.split(b" ", 1)[0]
        if head == b"#AL":
            return ALL
        if head[:1] == b"#" and head[1:].isdigit():
            return int(head[1:])
        return None

    def handle(self, request, unit):
        self.hits[unit] = self.hits.get(unit, 0) + 1
        if request.startswith(b"#AL"):
            return None
        return "#%d A" % unit


class LineClient:
    """A TCP client that reads lines ending with `term`."""

    def __init__(self, port, term=b"\n", timeout=2.0):
        self.term = term
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = b""

    def send(self, data):
        self.sock.sendall(data)

    def readline(self, timeout=None):
        """One line without terminator, or None on timeout."""
        if timeout is not None:
            self.sock.settimeout(timeout)
        while self.term not in self.buf:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not data:
                raise ConnectionError("closed")
            self.buf += data
        line, self.buf = self.buf.split(self.term, 1)
        return line

    def ask(self, line, timeout=1.0):
        self.send(line + b"\n")
        return self.readline(timeout)

    def close(self):
        self.sock.close()


def wait_until(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()
