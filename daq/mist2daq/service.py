"""The service: the channels of one NI box as one libcom1 device, served over TCP.

Daq      the logic without sockets: scaling, limits, the held set values, the communication
         timeout and its action. Tested directly (daq/tests).
Server   the TCP side: one client at a time on the libcom1 port, a read-only status port.

What the service does by itself: nothing. It writes no output at its start, at a lost client or
at its stop. The only exception is the setting on_comm_lost: ramp_to_zero (off by default).
"""

import json
import logging
import math
import selectors
import signal
import socket
import time

from . import __version__
from .backends import BackendError
from .protocol import (ERR_NOT_SUPPORTED, ERR_SYNTAX, ERR_UNKNOWN, Channel, Device, LineReader,
                       Refused, f32, min_stream_buffer_size)

log = logging.getLogger("mist2daq")
NAN = math.nan


class Daq:
    """Scaling: value = offset + per_volt * volts, in the channel's unit.
    An output's value is "not known" (nan) until the first set of this run that the backend
    took; a set the backend did not take makes it "not known" again."""

    def __init__(self, config, backend, clock=time.monotonic):
        self.config, self.backend, self.clock = config, backend, clock
        svc = config.service
        self.held = {c.id: NAN for c in config.outputs}
        self.input_volts = {c.physical: NAN for c in config.inputs}
        self.read_failed = False
        self.ramping = {}
        self.counts = {"commands": {}, "invalid": 0, "sets_applied": 0, "sets_refused_limit": 0,
                       "sets_failed_backend": 0, "comm_lost": 0, "ramp_writes": 0}
        channels = []
        for c in config.channels:
            iden, num = c.id[0], int(c.id[1])
            if c.direction == "out":
                channels.append(Channel(iden, num, self._getter_out(c), self._setter_out(c)))
            else:
                channels.append(Channel(iden, num, self._getter_in(c), None))
        firmware = "mist2daq-%s" % __version__
        # The output buffer: no microcontroller's RAM to save here. Large enough for the stream
        # frames and for the identity reply (a tight buffer answered "I" with ERR2 when the
        # identity grew by one character: found by a mutation of the device case).
        ident = len("oID=%s;FW=%s;PROTO=2;CH=%s" % (svc["identity"], firmware,
                                                   ",".join(c.id for c in config.channels)))
        size = max(160, min_stream_buffer_size(len(channels)), ident + 1)
        self.device = Device(channels, svc["identity"], firmware, out_buffer=size,
                             refresh=self.refresh)
        if svc["comm_timeout_s"] > 0:
            self.device.set_comm_timeout(int(round(svc["comm_timeout_s"] * 1000)), self._comm_lost)

    # --- channels -------------------------------------------------------------------------------

    def _getter_out(self, c):
        return lambda: self.held[c.id]

    def _getter_in(self, c):
        return lambda: c.offset + c.per_volt * self.input_volts[c.physical]

    def _setter_out(self, c):
        return lambda value: self.set_output(c, value)

    @staticmethod
    def to_volts(c, value):
        return (value - c.offset) / c.per_volt

    def check(self, c, value):
        """Reason why `value` may not be set on output c, or None. The limits are compared as
        32-bit floats, as the value arrives (a set of exactly the limit is allowed)."""
        lo, hi = f32(c.limits[0]), f32(c.limits[1])
        if not lo <= value <= hi:
            return "%g %s outside limits %g to %g" % (value, c.unit, c.limits[0], c.limits[1])
        volts = self.to_volts(c, value)
        tol = 1e-6 * (c.volts[1] - c.volts[0])
        if not c.volts[0] - tol <= volts <= c.volts[1] + tol:
            return "%g %s is %g V, outside %g to %g V" % (value, c.unit, volts, c.volts[0], c.volts[1])
        return None

    def set_output(self, c, value, why="set"):
        reason = self.check(c, value)
        if reason:
            self.counts["sets_refused_limit"] += 1
            log.warning("%s %s refused: %s", why, c.id, reason)
            raise Refused(ERR_SYNTAX, reason)
        volts = min(max(self.to_volts(c, value), c.volts[0]), c.volts[1])
        self.ramping.pop(c.id, None)            # an explicit set ends a ramp
        try:
            self.backend.write(c.physical, volts)
        except BackendError as exc:
            self.held[c.id] = NAN               # what the output does now is not known
            self.counts["sets_failed_backend"] += 1
            log.error("%s %s = %g %s (%g V) failed: %s", why, c.id, value, c.unit, volts, exc)
            raise Refused(ERR_NOT_SUPPORTED, str(exc))
        self.held[c.id] = value
        self.counts["sets_applied"] += 1
        log.info("%s %s = %g %s (%g V)", why, c.id, value, c.unit, volts)

    def refresh(self):
        """One sample of every input, before the values of a reply are formatted."""
        try:
            self.input_volts.update(self.backend.read_inputs())
            if self.read_failed:
                log.info("inputs read again")
            self.read_failed = False
        except BackendError as exc:
            for p in self.input_volts:
                self.input_volts[p] = NAN       # sent as nan: the IOC shows INVALID
            if not self.read_failed:
                log.error("reading the inputs failed: %s (logged once until it works again)", exc)
            self.read_failed = True

    # --- one line -------------------------------------------------------------------------------

    def service(self, now_ms, line=None):
        if line:
            op = line[0] if line[0].isprintable() else "?"
            self.counts["commands"][op] = self.counts["commands"].get(op, 0) + 1
        reply, frames, code = self.device.service(now_ms, line)
        if line and code >= ERR_UNKNOWN:
            self.counts["invalid"] += 1
        return reply, frames, code

    # --- communication timeout ----------------------------------------------------------------

    def _comm_lost(self):
        self.counts["comm_lost"] += 1
        if self.config.service["on_comm_lost"] == "hold":
            log.warning("no valid command for %g s: outputs held (on_comm_lost: hold)",
                        self.config.service["comm_timeout_s"])
            return
        for c in self.config.outputs:
            if math.isfinite(self.held[c.id]) and self.held[c.id] != 0.0:
                self.ramping[c.id] = self.clock()
        log.warning("no valid command for %g s: ramp to zero of %s",
                    self.config.service["comm_timeout_s"], ", ".join(self.ramping) or "nothing (no output set)")

    def step_ramps(self):
        now = self.clock()
        for c in self.config.outputs:
            since = self.ramping.get(c.id)
            if since is None:
                continue
            step = c.ramp_rate * max(0.0, now - since)
            value = self.held[c.id]
            new = 0.0 if abs(value) <= step else value - math.copysign(step, value)
            try:
                self.set_output(c, f32(new), why="ramp")
                self.counts["ramp_writes"] += 1
            except Refused:
                self.ramping.pop(c.id, None)
                continue
            if new != 0.0:
                self.ramping[c.id] = now
            else:
                log.info("ramp of %s ended at 0 %s", c.id, c.unit)

    # --- status -----------------------------------------------------------------------------------

    def status(self):
        written = self.backend.outputs_written()
        chans = {}
        for c in self.config.channels:
            d = {"name": c.name, "direction": c.direction, "physical": c.physical, "unit": c.unit}
            if c.direction == "out":
                d["held"] = _json_number(self.held[c.id])
                d["volts_written"] = _json_number(written.get(c.physical, NAN))
                d["ramping"] = c.id in self.ramping
            else:
                d["volts"] = _json_number(self.input_volts[c.physical])
            chans[c.id] = d
        out = {"identity": self.config.service["identity"], "version": __version__,
               "backend": self.config.backend["type"], "channels": chans,
               "counts": json.loads(json.dumps(self.counts)), "comm_lost": self.device.comm_lost}
        if hasattr(self.backend, "state"):
            out["sim"] = self.backend.state()
        return out


def _json_number(v):
    return v if math.isfinite(v) else None


class Stop(Exception):
    pass


class Server:
    """One libcom1 client at a time. A second client is closed at once while the first has sent a
    valid command within takeover_s; after that silence the newcomer replaces it (a dead
    connection of a crashed IOC host must not lock the IOC out)."""

    def __init__(self, daq, clock=time.monotonic):
        self.daq, self.clock = daq, clock
        svc = daq.config.service
        self.sel = selectors.DefaultSelector()
        self.listener = self._listen(svc["listen_host"], svc["listen_port"])
        self.sel.register(self.listener, selectors.EVENT_READ, ("accept", None))
        self.status_listener = None
        if svc["status_port"] is not None:
            self.status_listener = self._listen(svc["status_host"], svc["status_port"])
            self.sel.register(self.status_listener, selectors.EVENT_READ, ("status_accept", None))
        self.client = None
        self.client_peer = None
        self.client_reader = None
        self.client_last_valid = 0.0
        self.status_clients = {}
        self.clients = {"accepted": 0, "refused": 0, "replaced": 0}
        self.stopping = False                   # tests end run() with it; the service uses signals

    @staticmethod
    def _listen(host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(4)
        s.setblocking(False)
        log.info("listening on %s:%d", host, port)
        return s

    def now_ms(self):
        return int(self.clock() * 1000)

    # --- libcom1 client -----------------------------------------------------------------------

    def _accept(self):
        conn, peer = self.listener.accept()
        now = self.clock()
        if self.client is not None:
            silent = now - self.client_last_valid
            if silent < self.daq.config.service["takeover_s"]:
                self.clients["refused"] += 1
                log.warning("client %s:%d refused: %s:%d is connected and active (%.1f s ago)",
                            peer[0], peer[1], self.client_peer[0], self.client_peer[1], silent)
                conn.close()
                return
            self.clients["replaced"] += 1
            log.warning("client %s:%d replaces %s:%d, silent for %.1f s", peer[0], peer[1],
                        self.client_peer[0], self.client_peer[1], silent)
            self._drop("replaced")
        conn.setblocking(False)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.client, self.client_peer = conn, peer
        self.client_reader = LineReader(128)
        self.client_last_valid = now
        self.clients["accepted"] += 1
        self.daq.device.set_stream_period(0)     # a stream belongs to the client that asked
        self.sel.register(conn, selectors.EVENT_READ, ("client", None))
        log.info("client %s:%d connected", peer[0], peer[1])

    def _drop(self, why):
        if self.client is None:
            return
        log.info("client %s:%d %s", self.client_peer[0], self.client_peer[1], why)
        self.sel.unregister(self.client)
        self.client.close()
        self.client = None
        self.daq.device.set_stream_period(0)

    def _send(self, lines):
        if self.client is None or not lines:
            return
        try:
            for line in lines:                  # reply and its LF in ONE write (README, TCP)
                self.client.sendall((line + "\n").encode("latin-1"))
        except OSError as exc:
            self._drop("lost (%s)" % exc)

    def _read_client(self):
        try:
            data = self.client.recv(4096)
        except (BlockingIOError, InterruptedError):
            return
        except OSError as exc:
            self._drop("lost (%s)" % exc)
            return
        if not data:
            self._drop("disconnected")
            return
        for line in self.client_reader.feed(data):
            reply, frames, code = self.daq.service(self.now_ms(), line)
            if code < ERR_UNKNOWN:
                self.client_last_valid = self.clock()
            self._send(([reply] if reply is not None else []) + frames)
            if self.client is None:
                return

    # --- status port (read-only) ------------------------------------------------------------------

    def _status_accept(self):
        conn, peer = self.status_listener.accept()
        conn.setblocking(False)
        self.status_clients[conn] = bytearray()
        self.sel.register(conn, selectors.EVENT_READ, ("status", None))

    def _status_read(self, conn):
        try:
            data = conn.recv(4096)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:
            self.sel.unregister(conn)
            conn.close()
            del self.status_clients[conn]
            return
        buf = self.status_clients[conn]
        buf += data
        if len(buf) > 4096 and b"\n" not in buf:
            buf.clear()
        while b"\n" in buf:
            raw, _, rest = bytes(buf).partition(b"\n")
            buf[:] = rest
            try:
                req = json.loads(raw.decode("utf-8") or "{}")
                cmd = req.get("cmd") if isinstance(req, dict) else None
            except ValueError:
                cmd = None
            if cmd == "status":
                st = self.daq.status()
                st["client"] = None if self.client is None else "%s:%d" % self.client_peer
                st["clients"] = dict(self.clients)
                reply = {"ok": True, "status": st}
            else:
                reply = {"ok": False, "error": 'read-only; the only command is {"cmd": "status"}'}
            try:
                conn.sendall((json.dumps(reply) + "\n").encode())
            except OSError:
                pass

    # --- the loop ---------------------------------------------------------------------------------

    def run(self):
        ramp_period = self.daq.config.service["ramp_period_s"]
        next_ramp = self.clock()
        while not self.stopping:
            due = self.daq.device.ms_until_due()
            timeout = 0.5 if due is None else min(0.5, due / 1000.0)
            if self.daq.ramping:
                timeout = min(timeout, max(0.0, next_ramp - self.clock()))
            for key, _ in self.sel.select(timeout):
                kind = key.data[0]
                if kind == "accept":
                    self._accept()
                elif kind == "client" and self.client is not None:
                    self._read_client()
                elif kind == "status_accept":
                    self._status_accept()
                elif kind == "status":
                    self._status_read(key.fileobj)
            _, frames, _ = self.daq.service(self.now_ms(), None)   # timeout, stream frames
            self._send(frames)
            if self.daq.ramping and self.clock() >= next_ramp:
                self.daq.step_ramps()
                next_ramp = self.clock() + ramp_period

    def close(self):
        self._drop("closed: service stops")
        for conn in list(self.status_clients):
            conn.close()
        self.listener.close()
        if self.status_listener:
            self.status_listener.close()
        self.sel.close()


def serve(config, backend):
    """Run until SIGTERM or SIGINT. Opens the backend (no output written), serves, closes."""

    def stop(signum, frame):
        raise Stop(signal.Signals(signum).name)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    backend.open()
    daq = Daq(config, backend)
    server = Server(daq)
    log.info("mist2daq %s: %s, backend %s, channels %s; no output written at the start", __version__,
             config.service["identity"], config.backend["type"],
             ", ".join("%s=%s(%s)" % (c.id, c.physical, c.direction) for c in config.channels))
    try:
        server.run()
    except Stop as exc:
        log.info("stopping (%s): outputs are left as they are, nothing written", exc)
    finally:
        server.close()
        backend.close()
