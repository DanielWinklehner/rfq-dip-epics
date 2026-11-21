"""ControlClient: the synchronous client of a simulator's control port (standard library only).

    from mist2sim.control import ControlClient
    with ControlClient("localhost", 6012) as c:
        c.fault("silent", duration=5)
        print(c.stats())
"""

import json
import socket


class ControlError(Exception):
    """The simulator answered with {"ok": false, "error": ...}."""


class ControlClient:
    def __init__(self, host="localhost", port=6000, timeout=5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.file = self.sock.makefile("rwb")

    def close(self):
        self.file.close()
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def call(self, request):
        """Send one request (a dict, or a raw line as str) and return the reply dict as is."""
        line = request if isinstance(request, str) else json.dumps(request)
        self.file.write(line.encode() + b"\n")
        self.file.flush()
        reply = self.file.readline()
        if not reply:
            raise ConnectionError("control port closed the connection")
        return json.loads(reply)

    def _cmd(self, cmd, **args):
        reply = self.call(dict(cmd=cmd, **{k: v for k, v in args.items() if v is not None}))
        if not reply.get("ok"):
            raise ControlError(reply.get("error", "no error text"))
        return reply

    def info(self):
        return self._cmd("info")

    def fault(self, mode, unit=None, duration=None, ms=None):
        return self._cmd("fault", mode=mode, unit=unit, duration=duration, ms=ms)

    def clear(self, mode=None, unit=None):
        return self._cmd("clear", mode=mode, unit=unit)

    def get(self, signal=None):
        return self._cmd("get", signal=signal)

    def set(self, signal, value):
        return self._cmd("set", signal=signal, value=value)

    def release(self, signal):
        return self._cmd("release", signal=signal)

    def stats(self, reset=False):
        return self._cmd("stats", reset=reset)
