"""The Simulator base class: one TCP port = one serial line or bus.

A device module subclasses Simulator, overrides setup() and handle() (a bus also route()), and
registers the class with @register("type"). Everything else lives here: the TCP server, line
timing, unit routing, faults, statistics and the signals shown on the control interface.
"""

import asyncio
import copy
import logging
import numbers
import random
import socket

from .signals import Signal, SystemClock


class ConfigError(Exception):
    """A configuration mistake. The message says which simulator and which key."""


class Unsupported(Exception):
    """Raised by a device for a request it does not support (for example a trip)."""


class _All:
    def __repr__(self):
        return "ALL"


ALL = _All()          # route(): the request is for every unit (broadcast)
REQUIRED = object()   # OPTIONS: this option has no default and must be given

FAULT_MODES = ("silent", "close", "garbage", "trip", "slow", "slow_second")
# slow         every reply (of the unit) comes `ms` later while the fault lasts
# slow_second  the second reply (of the unit) after the fault was set comes `ms` later, once;
#              then the fault ends by itself. For a protocol that asks twice in one exchange
#              (the Matsusada status check before a query, task T22): its second reply late.

LINE_DEFAULTS = {
    "baud": 9600,
    "bits_per_char": 10,
    "turnaround_ms": 0.0,
    "in_terminator": "\n",
    "out_terminator": "\n",
}

GARBAGE = b"#$%&*@?~"


class Stats:
    def __init__(self, clock):
        self.clock = clock
        self.reset()

    def reset(self):
        self.since = self.clock.now()
        self.requests = 0
        self.replies = 0
        self.bytes_in = 0
        self.bytes_out = 0
        self.busy_s = 0.0
        self.per_unit = {}
        self.heads = {}           # requests by their first character (libcom1 "S": a set)

    def count(self, unit, replied):
        if unit is None:
            return
        u = self.per_unit.setdefault(str(unit), {"requests": 0, "replies": 0})
        u["requests"] += 1
        u["replies"] += 1 if replied else 0

    def as_dict(self):
        return {
            "elapsed_s": self.clock.now() - self.since,
            "requests": self.requests,
            "replies": self.replies,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "busy_s": self.busy_s,
            "per_unit": copy.deepcopy(self.per_unit),
            "heads": dict(self.heads),
        }


def _to_bytes(x):
    return x if isinstance(x, bytes) else str(x).encode("latin-1")


class Simulator:
    """Base class of every simulated device or bus.

    Override in a subclass:
      OPTIONS   {option: default}, REQUIRED for a mandatory one. Unknown options are an error.
      DEFAULTS  overrides of the line settings, e.g. {"baud": 19200, "in_terminator": "\\r"}
      setup()                   create signals (add_signal) and units (add_unit)
      handle(request, unit)     -> None, a line, or a list of lines (bytes or str, no terminator)
      route(request)            bus only: a unit address, ALL, or None (nobody answers)
      trip(unit), trip_cleared(unit)   what the fault "trip" means for this device
      tick(now) -> next|None    optional periodic work (unsolicited output with send())
    """

    TYPE = None
    OPTIONS = {}
    DEFAULTS = {}

    def __init__(self, name, port=0, control_port=None, options=None, clock=None, rng=None,
                 **line):
        self.name = name
        self.log = logging.getLogger("mist2sim." + name)
        self.clock = clock or SystemClock()
        self.rng = rng or random.Random()
        self.port = port
        self.control_port = (port + 1000 if port else 0) if control_port is None else control_port
        self.settings = self._line_settings(line)
        self.baud = self.settings["baud"]
        self.bits_per_char = self.settings["bits_per_char"]
        self.turnaround_ms = self.settings["turnaround_ms"]
        self.in_term = _to_bytes(self.settings["in_terminator"])
        self.out_term = _to_bytes(self.settings["out_terminator"])
        self.options = self._check_options(options or {})
        self.signals = {}
        self.units = []
        self.faults = []
        self.outbox = []          # send() before start(): kept here (unit tests read it)
        self.stats = Stats(self.clock)
        self._couplings = []
        self._t0 = self.clock.now()
        self._last_step = self._t0
        self._loop = None
        self._queue = None
        self._wake = None
        self._conn = None
        self._conn_id = 0
        self._line_free = 0.0
        self._servers = []
        self._tasks = []
        self.handlers = set()     # connection handler tasks (device and control port)
        self.setup()

    # --- configuration -----------------------------------------------------------------------

    def _line_settings(self, line):
        settings = dict(LINE_DEFAULTS)
        settings.update(self.DEFAULTS)
        for key, value in line.items():
            if key not in LINE_DEFAULTS:
                raise ConfigError("%s: unknown setting %r" % (self.name, key))
            settings[key] = value
        for key in ("baud", "bits_per_char", "turnaround_ms"):
            v = settings[key]
            if isinstance(v, bool) or not isinstance(v, numbers.Real) or v < 0 or \
                    (key != "turnaround_ms" and v == 0):
                raise ConfigError("%s: %s must be a positive number, not %r" % (self.name, key, v))
        for key in ("in_terminator", "out_terminator"):
            v = settings[key]
            if not isinstance(v, (str, bytes)) or (key == "in_terminator" and not v):
                raise ConfigError("%s: %s must be a non-empty string, not %r" % (self.name, key, v))
        return settings

    def _check_options(self, options):
        if not isinstance(options, dict):
            raise ConfigError("%s: options must be a mapping" % self.name)
        unknown = sorted(set(options) - set(self.OPTIONS))
        if unknown:
            raise ConfigError("%s: unknown option(s) %s for type %s; allowed: %s" % (
                self.name, ", ".join(unknown), self.TYPE, ", ".join(sorted(self.OPTIONS)) or "none"))
        result = {}
        for key, default in self.OPTIONS.items():
            if key not in options:
                if default is REQUIRED:
                    raise ConfigError("%s: option %r is required for type %s" % (self.name, key, self.TYPE))
                result[key] = copy.deepcopy(default)
                continue
            value = options[key]
            if default is not REQUIRED and default is not None and not _same_kind(value, default):
                raise ConfigError("%s: option %r must be %s, not %r" % (
                    self.name, key, type(default).__name__, value))
            result[key] = value
        return result

    # --- for subclasses ----------------------------------------------------------------------

    def setup(self):
        pass

    def route(self, request):
        return ALL

    def handle(self, request, unit):
        return None

    def trip(self, unit):
        raise Unsupported("type %s has no trip fault" % self.TYPE)

    def trip_cleared(self, unit):
        pass

    def tick(self, now):
        return None

    def add_signal(self, name, value=0.0, **params):
        """Create a Signal (params: tau, noise, lo, hi, step), visible on the control port."""
        if name in self.signals:
            raise ConfigError("%s: signal %r defined twice" % (self.name, name))
        sig = Signal(name, value, clock=self.clock, rng=self.rng, **params)
        self.signals[name] = sig
        return sig

    def add_unit(self, address):
        if address in self.units:
            raise ConfigError("%s: unit %r defined twice" % (self.name, address))
        self.units.append(address)

    def add_coupling(self, fn):
        """fn(dt, signals) is called before every request, tick and control command."""
        self._couplings.append(fn)

    def now(self):
        """Seconds since the simulator was created, from its clock."""
        return self.clock.now() - self._t0

    def send(self, line, unit=None):
        """Send a line on our own (stream frame, talk-only device). It respects the line timing
        and never lands inside a reply."""
        if self._queue is None:
            self.outbox.append(_to_bytes(line))
        else:
            self._queue.put_nowait(("out", self._loop.time(), None, _to_bytes(line), unit))

    def faulted(self, mode, unit=None):
        """True if a fault `mode` is active for the whole simulator or for this unit."""
        self.expire_faults()
        return any(f["mode"] == mode and (f["unit"] is None or f["unit"] == unit)
                   for f in self.faults)

    # --- faults ------------------------------------------------------------------------------

    def find_unit(self, address):
        for u in self.units:
            if u == address or str(u) == str(address):
                return u
        raise KeyError(address)

    def add_fault(self, mode, unit=None, duration=None, ms=None):
        if mode not in FAULT_MODES:
            raise ValueError("mode must be one of %s" % ", ".join(FAULT_MODES))
        if unit is not None:
            if not self.units:
                raise ValueError("%s is a single device, it has no units" % self.name)
            try:
                unit = self.find_unit(unit)
            except KeyError:
                raise ValueError("no unit %r (units: %s)" % (unit, self.units)) from None
            if mode == "close":
                raise ValueError("close applies to the whole line, not to one unit")
        if duration is not None and (isinstance(duration, bool) or
                                     not isinstance(duration, numbers.Real) or duration <= 0):
            raise ValueError("duration must be a positive number of seconds")
        if mode in ("slow", "slow_second"):
            if isinstance(ms, bool) or not isinstance(ms, numbers.Real) or ms < 0:
                raise ValueError("%s needs ms, the extra delay in milliseconds" % mode)
        elif ms is not None:
            raise ValueError("ms is only for modes slow and slow_second")
        if mode == "trip":
            self.trip(unit)           # may raise Unsupported
        fault = {"mode": mode, "unit": unit, "ms": ms,
                 "until": None if duration is None else self.clock.now() + duration}
        if mode == "slow_second":
            fault["replies"] = 0      # replies of the unit seen since the fault was set
        self.faults.append(fault)
        self.log.info("fault %s%s%s", mode, "" if unit is None else " unit %s" % unit,
                      "" if duration is None else " for %g s" % duration)
        if mode == "close":
            self._drop_connection()
        if duration is not None and self._loop is not None:
            self._loop.call_later(duration + 0.001, self.expire_faults)
        return fault

    def clear_faults(self, mode=None, unit=None):
        if unit is not None:
            try:
                unit = self.find_unit(unit)
            except KeyError:
                raise ValueError("no unit %r" % (unit,)) from None
        gone = [f for f in self.faults
                if (mode is None or f["mode"] == mode) and (unit is None or f["unit"] == unit)]
        self._remove(gone)
        return len(gone)

    def expire_faults(self):
        now = self.clock.now()
        self._remove([f for f in self.faults if f["until"] is not None and f["until"] <= now])

    def _remove(self, gone):
        for f in gone:
            self.faults.remove(f)
            self.log.info("fault %s cleared", f["mode"])
            if f["mode"] == "trip":
                self.trip_cleared(f["unit"])

    def fault_list(self):
        self.expire_faults()
        now = self.clock.now()
        return [{"mode": f["mode"], "unit": f["unit"], "ms": f["ms"],
                 "remaining_s": None if f["until"] is None else f["until"] - now}
                for f in self.faults]

    def _garble(self, line):
        return bytes(self.rng.choice(GARBAGE) for _ in range(max(1, len(line))))

    # --- one transaction, without I/O --------------------------------------------------------

    def step_couplings(self):
        now = self.clock.now()
        dt, self._last_step = now - self._last_step, now
        for fn in self._couplings:
            fn(dt, self.signals)

    def process(self, request):
        """Run one request through routing, faults and the device. Returns the reply lines
        (bytes, without terminator). Used by the line worker and directly by unit tests."""
        return self._process(_to_bytes(request))[0]

    def _process(self, request):
        self.stats.requests += 1
        head = request[:1].decode("latin-1")
        self.stats.heads[head] = self.stats.heads.get(head, 0) + 1
        self.step_couplings()
        try:
            target = self.route(request)
            if target is None:
                return [], 0.0
            if target is ALL:
                targets = list(self.units) or [None]
            else:
                try:
                    targets = [self.find_unit(target)]
                except KeyError:
                    return [], 0.0     # no such address on the bus: nobody answers
            out, extra, done = [], 0.0, []
            for unit in targets:
                if self.faulted("silent", unit):
                    self.stats.count(unit, False)
                    continue
                lines = self.handle(request, unit)
                if lines is None:
                    lines = []
                elif isinstance(lines, (bytes, str)):
                    lines = [lines]
                lines = [_to_bytes(x) for x in lines]
                if self.faulted("garbage", unit):
                    lines = [self._garble(x) for x in lines]
                for f in self.faults:
                    if f["mode"] == "slow" and (f["unit"] is None or f["unit"] == unit):
                        extra = max(extra, f["ms"] / 1000.0)
                    if f["mode"] == "slow_second" and lines and \
                            (f["unit"] is None or f["unit"] == unit):
                        f["replies"] += 1
                        if f["replies"] == 2:
                            extra = max(extra, f["ms"] / 1000.0)
                            done.append(f)
                self.stats.count(unit, bool(lines))
                out += lines
            self._remove([f for f in done if f in self.faults])
        except Exception:
            self.log.exception("device error on request %r", request)
            return [], 0.0
        if out:
            self.stats.replies += 1
        return out, extra

    # --- TCP and line timing -----------------------------------------------------------------

    def char_time(self, n_bytes):
        return n_bytes * self.bits_per_char / self.baud

    async def start(self, host="0.0.0.0"):
        from .control_server import serve_control
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._wake = asyncio.Event()
        for line in self.outbox:
            self.send(line)
        self.outbox = []
        server = await asyncio.start_server(self._on_client, host, self.port)
        self.port = server.sockets[0].getsockname()[1]
        self._servers.append(server)
        control = await serve_control(self, host, self.control_port)
        self.control_port = control.sockets[0].getsockname()[1]
        self._servers.append(control)
        self._tasks.append(asyncio.ensure_future(self._worker()))
        if type(self).tick is not Simulator.tick:
            self._tasks.append(asyncio.ensure_future(self._ticker()))
        self.log.info("%s on port %d, control port %d, %g baud", self.TYPE, self.port,
                      self.control_port, self.baud)

    async def stop(self):
        for server in self._servers:
            server.close()                # stop accepting
        self._drop_connection()
        tasks = self._tasks + list(self.handlers)
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        for server in self._servers:      # since 3.12 this waits for open connections
            await server.wait_closed()
        self._tasks, self._servers = [], []
        self.handlers.clear()

    def _drop_connection(self):
        self._conn_id += 1
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def track_handler(self):
        """Called by a connection handler, so that stop() can end it."""
        task = asyncio.current_task()
        self.handlers.add(task)
        task.add_done_callback(self.handlers.discard)

    async def _on_client(self, reader, writer):
        self.track_handler()
        if self.faulted("close"):
            writer.close()
            return
        self._drop_connection()       # a new connection replaces the old one
        self._conn_id += 1
        me = self._conn_id
        self._conn = writer
        sock = writer.get_extra_info("socket")
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.log.info("client %s connected", writer.get_extra_info("peername"))
        buf = b""
        try:
            while True:
                data = await reader.read(4096)
                if not data or me != self._conn_id:
                    break
                t = self._loop.time()
                self.stats.bytes_in += len(data)
                buf += data
                while self.in_term in buf:
                    request, buf = buf.split(self.in_term, 1)
                    self._queue.put_nowait(("req", t, me, request, None))
                if len(buf) > 65536:
                    buf = b""         # nobody sends this much without a terminator
        except (ConnectionError, OSError):
            pass
        finally:
            if me == self._conn_id:
                self._conn = None
                self.log.info("client disconnected")
            writer.close()

    async def _sleep_until(self, t):
        delay = t - self._loop.time()
        if delay > 0:
            await asyncio.sleep(delay)

    async def _worker(self):
        """The line: one transaction at a time, in order of arrival, each held back by the
        transmission time of its characters. Times are absolute, so queued requests do not
        accumulate sleeping errors."""
        while True:
            kind, t_in, conn, data, unit = await self._queue.get()
            start = max(t_in, self._line_free)
            await self._sleep_until(start)
            if kind == "req":
                if conn != self._conn_id:
                    continue          # from a connection that has been replaced
                lines, extra = self._process(data)
                out = b"".join(x + self.out_term for x in lines)
                duration = self.char_time(len(data) + len(self.in_term) + len(out))
                if out:
                    duration += self.turnaround_ms / 1000.0 + extra
            else:
                conn = self._conn_id
                if self.faulted("silent", unit):
                    continue
                if self.faulted("garbage", unit):
                    data = self._garble(data)
                out = data + self.out_term
                duration = self.char_time(len(out))
            due = start + duration
            self._line_free = due
            self.stats.busy_s += duration
            self._wake.set()
            if out:
                await self._sleep_until(due)
                if conn == self._conn_id and self._conn is not None:
                    try:
                        self._conn.write(out)
                        self.stats.bytes_out += len(out)
                    except (ConnectionError, OSError):
                        pass

    async def _ticker(self):
        while True:
            self._wake.clear()
            try:
                self.step_couplings()
                nxt = self.tick(self.now())
            except Exception:
                self.log.exception("device error in tick")
                nxt = self.now() + 1.0
            timeout = None if nxt is None else max(0.0, nxt - self.now())
            try:
                await asyncio.wait_for(self._wake.wait(), timeout)
            except asyncio.TimeoutError:
                pass

    def info(self):
        settings = dict(self.settings)
        settings["in_terminator"] = self.in_term.decode("latin-1")
        settings["out_terminator"] = self.out_term.decode("latin-1")
        return {"name": self.name, "type": self.TYPE, "port": self.port,
                "control_port": self.control_port, "units": list(self.units),
                "signals": sorted(self.signals), "settings": settings,
                "options": self.options}


def _same_kind(value, default):
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, numbers.Real):
        return isinstance(value, numbers.Real) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, (list, tuple)):
        return isinstance(value, (list, tuple))
    if isinstance(default, dict):
        return isinstance(value, dict)
    return True
