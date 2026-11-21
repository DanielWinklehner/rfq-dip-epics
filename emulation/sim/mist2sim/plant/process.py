"""The plant process: the model behind the simulators, through their control ports only.

Every cycle (rate_hz): read all signals of every simulator it needs ({"cmd": "get"}), step the
model, write the process values ({"cmd": "set"}). A simulator that is not there, or goes away,
is tried again every retry_s; meanwhile the model runs on its last known values and the log
says so. On stop (SIGTERM, SIGINT, or stop_event) every signal the plant has taken is released.

Its own control port speaks the simulators' protocol (JSON lines): info, get (model state),
set / release (disturbances, see model.DISTURBANCES).
"""

import asyncio
import json
import logging
import math
import numbers
import threading
import time

import yaml

from .model import DISTURBANCES, INPUTS, PlantModel, params_from

TOP_KEYS = {"rate_hz", "log_period_s", "retry_s", "timeout_s", "control", "links", "inputs",
            "outputs", "model"}


class PlantConfigError(Exception):
    pass


def load_plant_config(path):
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise PlantConfigError("cannot read %s: %s" % (path, exc)) from None
    return check_plant_config(data)


def check_plant_config(data):
    if not isinstance(data, dict):
        raise PlantConfigError("expected a mapping")
    unknown, missing = set(data) - TOP_KEYS, TOP_KEYS - set(data)
    if unknown or missing:
        raise PlantConfigError("unknown keys %s, missing keys %s" % (sorted(unknown), sorted(missing)))
    try:
        params_from(data["model"])
    except ValueError as exc:
        raise PlantConfigError(str(exc)) from None
    links = data["links"]
    for name, link in links.items():
        if not isinstance(link, dict) or set(link) != {"host", "port"}:
            raise PlantConfigError("links.%s: expected {host, port}" % name)
    for name, spec in data["inputs"].items():
        if name not in INPUTS:
            raise PlantConfigError("inputs: unknown model input %r (known: %s)" % (name, ", ".join(INPUTS)))
        if not isinstance(spec, dict) or "signal" not in spec or set(spec) - {"signal", "scale"}:
            raise PlantConfigError("inputs.%s: expected {signal, scale}" % name)
        if split_signal(spec["signal"])[0] not in links:
            raise PlantConfigError("inputs.%s: no link for %r" % (name, spec["signal"]))
    for target in data["outputs"]:
        if split_signal(target)[0] not in links:
            raise PlantConfigError("outputs: no link for %r" % target)
    return data


def split_signal(text):
    """'rek.1.vset' -> ('rek', '1.vset'): simulator name, signal name."""
    sim, _, sig = str(text).partition(".")
    if not sim or not sig:
        raise PlantConfigError("%r is not <simulator>.<signal>" % text)
    return sim, sig


def output_value(out, path):
    """'thermocouples.t1' -> out['thermocouples']['t1']."""
    v = out
    for part in path.split("."):
        v = v[part]
    return float(v)


class Link:
    """The control port of one simulator."""

    def __init__(self, name, host, port, timeout, retry_s):
        self.name, self.host, self.port = name, host, port
        self.timeout, self.retry_s = timeout, retry_s
        self.reader = self.writer = None
        self.values = {}           # last known signal values
        self.taken = set()         # signals this plant holds under outside control
        self.bad = set()           # outputs refused by the simulator (logged once)
        self.next_try = 0.0
        self.down_since = None     # None: never connected or connected now
        self.ever_up = False

    @property
    def up(self):
        return self.writer is not None

    async def connect(self, now):
        if self.up or now < self.next_try:
            return False
        self.next_try = now + self.retry_s
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout)
        except (OSError, asyncio.TimeoutError):
            self.reader = self.writer = None
            return False
        self.taken, self.bad = set(), set()
        return True

    def drop(self):
        if self.writer is not None:
            self.writer.close()
        self.reader = self.writer = None

    async def calls(self, requests):
        """Send the requests pipelined, return the replies in order. Raises on any I/O error."""
        self.writer.write(b"".join(json.dumps(r).encode() + b"\n" for r in requests))
        replies = []
        for _ in requests:
            line = await asyncio.wait_for(self.reader.readline(), self.timeout)
            if not line:
                raise ConnectionError("connection closed")
            replies.append(json.loads(line))
        return replies


class Plant:
    def __init__(self, config, log=None):
        self.cfg = check_plant_config(config)
        self.log = log or logging.getLogger("mist2sim.plant")
        self.model = PlantModel(params_from(config["model"]))
        self.state = self.model.initial_state()
        self.outputs = {}
        self.inputs = {}
        self.period = 1.0 / float(config["rate_hz"])
        self.links = {}
        for name, link in config["links"].items():
            self.links[name] = Link(name, link["host"], int(link["port"]),
                                    float(config["timeout_s"]), float(config["retry_s"]))
        self.wanted_in = {}        # input -> (link, signal, scale)
        for name, spec in config["inputs"].items():
            sim, sig = split_signal(spec["signal"])
            self.wanted_in[name] = (sim, sig, float(spec.get("scale", 1.0)))
        self.wanted_out = {}       # link -> [(signal, output path)]
        for target, path in config["outputs"].items():
            sim, sig = split_signal(target)
            self.wanted_out.setdefault(sim, []).append((sig, path))
        self.control_host = config["control"]["host"]
        self.control_port = int(config["control"]["port"])
        self.steps = 0
        self._notes = []
        self._last_line = -1e9
        self._last_status = -1e9
        self._server = None

    # --- logging: at most one line per second -----------------------------------------------

    def note(self, text):
        self._notes.append(text)

    def _flush_log(self, now, force=False):
        status_due = now - self._last_status >= float(self.cfg["log_period_s"])
        if not (force or self._notes or status_due) or (now - self._last_line < 1.0 and not force):
            return
        parts = list(self._notes)
        if status_due or force:
            parts.append(self.status())
            self._last_status = now
        self._notes = []
        self._last_line = now
        self.log.info("; ".join(parts))

    def status(self):
        o = self.outputs
        if not o:
            return "no step yet"
        down = [n for n, lk in self.links.items() if not lk.up]
        return ("If %.1f A, T %.0f K, emission %.3g A, discharge %.3g A at %.1f V, "
                "p source %.2e, diag %.2e, foreline %.2e torr, beam %.3g mA, cup %.3g mA, "
                "links %d/%d up%s" % (
                    self.inputs.get("filament_current", 0.0), o["filament_temperature"],
                    o["emission"], o["discharge_current"], o["discharge_voltage"],
                    o["source_pressure"], o["diag_pressure"], o["foreline_pressure"],
                    o["beam_current"] * 1e3, o["cup_current"] * 1e3,
                    len(self.links) - len(down), len(self.links),
                    (" (down, last known values used: %s)" % ", ".join(down)) if down else ""))

    # --- one cycle --------------------------------------------------------------------------

    async def _read(self, lk, now):
        if not lk.up:
            if await lk.connect(now):
                was = lk.down_since
                lk.down_since = None
                lk.ever_up = True
                self.note("%s connected (%s:%d)%s" % (
                    lk.name, lk.host, lk.port,
                    "" if was is None else " after %.0f s" % (now - was)))
            else:
                if lk.down_since is None and not lk.ever_up and self.steps == 0:
                    self.note("%s not there yet (%s:%d), retrying every %g s" % (
                        lk.name, lk.host, lk.port, lk.retry_s))
                    lk.down_since = now
                return
        try:
            (reply,) = await lk.calls([{"cmd": "get"}])
            for name, st in reply.get("signals", {}).items():
                lk.values[name] = st["value"]
        except (OSError, ConnectionError, asyncio.TimeoutError, ValueError) as exc:
            self._lost(lk, now, exc)

    def _lost(self, lk, now, exc):
        lk.drop()
        lk.down_since = now
        lk.next_try = now + lk.retry_s
        self.note("%s lost (%s); the model runs on its last known values" % (
            lk.name, exc.__class__.__name__ if not str(exc) else exc))

    async def _write(self, lk, now):
        pairs = [(sig, output_value(self.outputs, path)) for sig, path in self.wanted_out.get(lk.name, [])
                 if sig not in lk.bad]
        if not lk.up or not pairs:
            return
        try:
            replies = await lk.calls([{"cmd": "set", "signal": s, "value": v} for s, v in pairs])
        except (OSError, ConnectionError, asyncio.TimeoutError, ValueError) as exc:
            self._lost(lk, now, exc)
            return
        for (sig, _), rep in zip(pairs, replies):
            if rep.get("ok"):
                lk.taken.add(sig)
            else:
                lk.bad.add(sig)
                self.note("%s refuses %s: %s" % (lk.name, sig, rep.get("error")))

    def _inputs(self):
        u = {}
        for name, (sim, sig, scale) in self.wanted_in.items():
            v = self.links[sim].values.get(sig)
            if v is not None:
                u[name] = float(v) * scale
        return u

    async def cycle(self, dt):
        now = time.monotonic()
        await asyncio.gather(*(self._read(lk, now) for lk in self.links.values()))
        self.inputs = self._inputs()
        self.state, self.outputs = self.model.step(self.state, self.inputs, dt)
        await asyncio.gather(*(self._write(lk, now) for lk in self.links.values()))
        self.steps += 1
        self._flush_log(now)

    async def release_all(self):
        n, sims = 0, 0
        for lk in self.links.values():
            if not lk.up or not lk.taken:
                continue
            try:
                await lk.calls([{"cmd": "release", "signal": s} for s in sorted(lk.taken)])
                n, sims = n + len(lk.taken), sims + 1
                lk.taken = set()
            except (OSError, ConnectionError, asyncio.TimeoutError, ValueError) as exc:
                self.note("%s: release failed (%s)" % (lk.name, exc))
        self.note("released %d signals on %d simulators" % (n, sims))

    # --- run --------------------------------------------------------------------------------

    async def run(self, stop_event=None, started=None):
        """Run until stop_event is set. `started` (a threading.Event) is set once the control
        port listens."""
        stop_event = stop_event or asyncio.Event()
        self._server = await asyncio.start_server(self._control_client, self.control_host,
                                                  self.control_port)
        self.control_port = self._server.sockets[0].getsockname()[1]
        self.log.info("plant model: %d simulators, %g Hz, control port %d",
                      len(self.links), 1.0 / self.period, self.control_port)
        if started is not None:
            started.set()
        loop = asyncio.get_running_loop()
        last = t_next = loop.time()
        try:
            while not stop_event.is_set():
                now = loop.time()
                dt = min(1.0, max(0.0, now - last))
                last = now
                await self.cycle(dt)
                t_next += self.period
                delay = t_next - loop.time()
                if delay < -self.period:          # far behind: do not try to catch up
                    t_next = loop.time()
                    delay = 0.0
                try:
                    await asyncio.wait_for(stop_event.wait(), max(0.0, delay))
                except asyncio.TimeoutError:
                    pass
        finally:
            self._server.close()
            await self.release_all()
            for lk in self.links.values():
                lk.drop()
            self._flush_log(time.monotonic(), force=True)

    # --- the plant's own control port -------------------------------------------------------

    def signals(self):
        sig = {}
        for k, v in self.outputs.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    sig["%s.%s" % (k, kk)] = vv
            else:
                sig[k] = v
        for k in DISTURBANCES:
            sig[k] = self.state[k]
        sig["chamber_pressure"] = self.state["chamber_pressure"]
        return sig

    def command(self, req):
        if not isinstance(req, dict):
            raise ValueError("expected a JSON object")
        cmd = req.get("cmd")
        if cmd == "info":
            return {"name": "plant", "type": "plant", "control_port": self.control_port,
                    "signals": sorted(self.signals()), "settable": sorted(DISTURBANCES),
                    "rate_hz": 1.0 / self.period}
        if cmd == "get":
            sig = self.signals()
            if "signal" in req:
                if req["signal"] not in sig:
                    raise ValueError("no signal %r (signals: %s)" % (req["signal"], ", ".join(sorted(sig))))
                return {"signal": req["signal"], "value": sig[req["signal"]]}
            links = {n: {"up": lk.up, "host": lk.host, "port": lk.port, "taken": sorted(lk.taken)}
                     for n, lk in self.links.items()}
            return {"signals": {k: {"value": v} for k, v in sorted(sig.items())},
                    "inputs": dict(self.inputs), "links": links, "steps": self.steps}
        if cmd in ("set", "release"):
            name = req.get("signal")
            if name not in DISTURBANCES:
                raise ValueError("%s: signal must be one of %s" % (cmd, ", ".join(DISTURBANCES)))
            if cmd == "release":
                value = DISTURBANCES[name]
            else:
                value = req.get("value")
                if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
                    raise ValueError("'value' must be a finite number")
                if name != "emission_drift_per_min" and value < 0:
                    raise ValueError("%s must be >= 0" % name)
            self.state[name] = float(value)
            self.note("%s %s = %g" % (cmd, name, value))
            return {"signal": name, "value": float(value)}
        raise ValueError("unknown command %r, known: info, get, set, release" % cmd)

    async def _control_client(self, reader, writer):
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                if not line.strip():
                    continue
                try:
                    reply = self.command(json.loads(line))
                    reply["ok"] = True
                except (ValueError, TypeError) as exc:
                    reply = {"ok": False, "error": str(exc)}
                writer.write((json.dumps(reply) + "\n").encode())
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()


class PlantThread:
    """Runs a Plant in a background thread (tests, notebooks):

        with PlantThread(Plant(config)) as t:
            ... ControlClient("127.0.0.1", t.plant.control_port) ...
    """

    def __init__(self, plant):
        self.plant = plant
        self._started = threading.Event()
        self._error = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._started.wait(10) or self._error is not None:
            raise RuntimeError("plant did not start: %s" % self._error)
        return self

    def stop(self):
        if self._thread.is_alive():
            self.loop.call_soon_threadsafe(self._stop.set)
            self._thread.join(10)

    def __exit__(self, *exc):
        self.stop()

    def _run(self):
        self.loop = asyncio.new_event_loop()

        async def main():
            self._stop = asyncio.Event()
            await self.plant.run(self._stop, self._started)

        try:
            self.loop.run_until_complete(main())
        except Exception as exc:     # reported by __enter__ if it happens before the start
            self._error = exc
            self._started.set()
            raise
        finally:
            self.loop.close()
