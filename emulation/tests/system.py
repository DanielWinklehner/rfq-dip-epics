"""Shared by the system tests: the registry, Channel Access, the simulators, the logs.

Every device and PV name comes from the registry (RAS/mist2/ReactApp/src/registry/registry.json).
A test names a PV only through a device id and a role (reg.role("ilk_old", "open")).
"""
import json
import os
import re
import socket
import threading
import time
from collections import deque
from pathlib import Path

import epics
import pytest

from mist2sim.control import ControlClient, ControlError

REPO = Path(__file__).resolve().parents[2]
BUILD = REPO / "emulation" / "build"
REGISTRY_FILE = REPO / "RAS" / "mist2" / "ReactApp" / "src" / "registry" / "registry.json"

NO_ALARM, MINOR, MAJOR, INVALID = 0, 1, 2, 3
SEVERITY = ["NO_ALARM", "MINOR", "MAJOR", "INVALID"]
# alarm status (menuAlarmStat of EPICS base 7); a CA enum has only 16 strings, so it is read as a number
STATUS = ["NO_ALARM", "READ", "WRITE", "HIHI", "HIGH", "LOLO", "LOW", "STATE", "COS", "COMM",
          "TIMEOUT", "HWLIMIT", "CALC", "SCAN", "LINK", "SOFT", "BAD_SUB", "UDF", "DISABLE",
          "SIMM", "READ_ACCESS", "WRITE_ACCESS"]
UDF = STATUS.index("UDF")

# Writes to the Matsusada set points are not sent during the first GRACE seconds after an IOC
# start (P20, matsusada_au20p7.db); the suite starts after that.
GRACE = 5


# --- registry ----------------------------------------------------------------------------------

class Registry:
    def __init__(self, path=REGISTRY_FILE):
        data = json.loads(Path(path).read_text())
        self.data = data
        self.devices = data["devices"]
        self.iocs = data["iocs"]
        self.simulators = data["simulators"]
        self.pvs = {}                        # name -> spec, with "device" and "ioc" added
        for did, d in self.devices.items():
            for name, spec in d["pvs"].items():
                self.pvs[name] = dict(spec, device=did, ioc=d["ioc"])
        for iid, i in self.iocs.items():
            for name, spec in i["pvs"].items():
                self.pvs[name] = dict(spec, device=iid, ioc=iid)

    def role(self, device, role):
        return self.devices[device]["roles"][role]

    def has_role(self, device, role):
        return role in self.devices[device].get("roles", {})

    def heartbeats(self):
        return {iid: i["roles"]["heartbeat"] for iid, i in self.iocs.items()}

    def not_polled(self, device):
        return "not_polled" in self.devices.get(device, {}).get("flags", {})

    def writes(self):
        """Written PVs an operator uses (not internal), in registry order."""
        return [n for n, s in self.pvs.items() if s["access"] == "w" and not s.get("internal")]

    def units(self, sim):
        """Unit addresses of a simulator named in the registry (from sim:unit references)."""
        units = set()
        for s in self.pvs.values():
            for ref in s.get("fails_with", []) + ([s["sim"]] if s.get("sim") else []):
                name, _, unit = ref.partition(":")
                if name == sim and unit:
                    units.add(int(unit))
        return sorted(units)

    def fails_with(self, sim, unit=None):
        """PVs whose `fails_with` covers a fault on the whole simulator (unit None) or one unit."""
        out = []
        for n, s in self.pvs.items():
            for ref in s.get("fails_with", []):
                name, _, u = ref.partition(":")
                if name == sim and (unit is None or u == "" or int(u) == unit):
                    out.append(n)
                    break
        return out

    def devices_behind(self, sim, unit=None):
        """Devices that list the simulator (or that unit of it) among their simulators."""
        out = []
        for did, d in self.devices.items():
            for ref in d.get("simulators", []):
                name, _, u = ref.partition(":")
                if name == sim and (unit is None or u == "" or int(u) == unit):
                    out.append(did)
                    break
        return out

    def sim_of(self, pv):
        """(simulator, unit or None) that a written PV talks to."""
        ref = self.pvs[pv].get("sim")
        if not ref:
            # a soft record (AU SetToggleOutput) acts on the device's one simulator
            sims = self.devices.get(self.pvs[pv]["device"], {}).get("simulators", [])
            if len(sims) != 1:
                return None, None
            ref = sims[0]
        name, _, unit = ref.partition(":")
        return name, (int(unit) if unit else None)

    def ioc_address(self, ioc):
        return socket.gethostbyname(self.iocs[ioc]["container"])


reg = Registry()


# --- Channel Access ------------------------------------------------------------------------------

class Watched:
    """A PV with a monitor that keeps every severity it posts (time, severity), so that a test can
    ask afterwards whether a PV went INVALID at any moment of a time window."""

    def __init__(self, name):
        self.name = name
        self.events = deque(maxlen=2000)
        self.lock = threading.Lock()
        self.pv = epics.PV(name, form="time", auto_monitor=True, callback=self._cb,
                           connection_timeout=5.0)

    def _cb(self, severity=None, **kw):
        with self.lock:
            self.events.append((time.monotonic(), severity))

    def invalid_since(self, t0):
        with self.lock:
            return any(t >= t0 and s == INVALID for t, s in self.events)


_watched = {}
_plain = {}


def watch(names):
    """Start monitors on PVs (once per session) and wait for their connections."""
    new = [n for n in names if n not in _watched]
    for n in new:
        _watched[n] = Watched(n)
    end = time.monotonic() + 10
    for n in new:
        _watched[n].pv.wait_for_connection(max(0.1, end - time.monotonic()))
    return [_watched[n] for n in names]


def watched(name):
    return _watched[name]


def _pv(name):
    if name in _watched:
        return _watched[name].pv
    if name not in _plain:
        _plain[name] = epics.PV(name, form="time", auto_monitor=False, connection_timeout=5.0)
        _plain[name].wait_for_connection(5.0)
    return _plain[name]


def connected(name):
    return _pv(name).connected


def read(name, as_string=False):
    """Fresh read from the IOC: dict with value, severity, status, timestamp."""
    d = _pv(name).get_with_metadata(use_monitor=False, form="time", as_string=as_string,
                                    timeout=3.0)
    if d is None:
        pytest.fail("%s does not answer (Channel Access read timed out)" % name)
    return d


def get(name, as_string=False):
    return read(name, as_string)["value"]


def sevr(name):
    return read(name)["severity"]


def stat(name):
    return read(name)["status"]


def field(name, fld):
    """A field as a plain Channel Access channel (record.FIELD)."""
    value = epics.caget("%s.%s" % (name, fld), as_string=True, use_monitor=False, timeout=3.0)
    if value is None:
        pytest.fail("%s.%s does not answer" % (name, fld))
    return value


def put(name, value, wait=True, timeout=10.0):
    """caput with completion: returns after the record (and its device I/O) finished."""
    ok = _pv(name).put(value, wait=wait, timeout=timeout)
    if wait and ok != 1:
        pytest.fail("caput %s = %r did not complete within %g s" % (name, value, timeout))


def put_field(name, fld, value):
    if epics.caput("%s.%s" % (name, fld), value, wait=True, timeout=5.0) != 1:
        pytest.fail("caput %s.%s = %r did not complete" % (name, fld, value))


def describe(names):
    """Short text of value and severity of PVs, for failure messages."""
    out = []
    for n in names:
        try:
            d = _pv(n).get_with_metadata(use_monitor=False, form="time", timeout=2.0)
        except Exception as exc:          # noqa: BLE001  the message must not fail itself
            d = None
        if d is None:
            out.append("%s=<no answer>" % n)
        else:
            v = d["value"]
            if hasattr(v, "__len__") and not isinstance(v, str):
                v = "[%d values]" % len(v)
            out.append("%s=%r %s/%s" % (n, v, SEVERITY[d["severity"]] if d["severity"] in range(4)
                                        else d["severity"], STATUS[d["status"]]
                                        if 0 <= d["status"] < len(STATUS) else d["status"]))
    return ", ".join(out)


def wait_for(cond, timeout, what, interval=0.1):
    """Wait until cond() returns a true value; returns the seconds it took. On timeout the test
    fails with `what` (a string, or a callable that describes the state at that moment)."""
    t0 = time.monotonic()
    while True:
        try:
            if cond():
                return time.monotonic() - t0
        except AssertionError:
            pass
        if time.monotonic() - t0 > timeout:
            pytest.fail("not within %g s: %s" % (timeout, what() if callable(what) else what))
        time.sleep(interval)


def wait_fresh(name, since, cond, timeout, what):
    """Wait until the record has been processed after `since` (wall clock, time.time()) and
    cond(value) holds: a read-back that was already right before a write proves nothing."""
    def ok():
        d = read(name)
        return d["timestamp"] > since and d["severity"] != INVALID and cond(d["value"])
    return wait_for(ok, timeout, lambda: "%s, processed after the write: %s" % (
        what, describe([name])))


def severities(names):
    return {n: sevr(n) for n in names}


def all_invalid(names):
    return all(sevr(n) == INVALID for n in names)


def not_invalid(names):
    return all(sevr(n) != INVALID for n in names)


def bad(names, test):
    """Names whose severity fails test(severity), with their state."""
    return describe([n for n in names if not test(sevr(n))])


def heartbeat_seconds(ioc):
    return get(reg.iocs[ioc]["roles"]["heartbeat"])


# --- simulators ----------------------------------------------------------------------------------

_controls = {}
_unreachable = {}
forced = set()          # (sim, signal) forced by the suite, released by the clean-up


def control(sim):
    """The control client of a simulator of the registry (kept for the session). A simulator that
    did not answer once fails every later call at once, so that a paused container does not make
    every test wait for its own timeout."""
    if sim in _unreachable:
        pytest.fail("simulator %s did not answer its control port before: %s" % (sim, _unreachable[sim]))
    c = _controls.get(sim)
    if c is None:
        s = reg.simulators[sim]
        try:
            c = ControlClient(s["host"], s["control_port"], timeout=5.0)
        except OSError as exc:
            _unreachable[sim] = "%s:%d %s" % (s["host"], s["control_port"], exc)
            pytest.fail("simulator %s: control port %s" % (sim, _unreachable[sim]))
        _controls[sim] = c
    return _Guarded(sim, c)


class _Guarded:
    def __init__(self, sim, client):
        self.sim, self.client = sim, client

    def __getattr__(self, name):
        method = getattr(self.client, name)

        def call(*args, **kw):
            try:
                return method(*args, **kw)
            except ControlError:
                raise
            except (OSError, ValueError, ConnectionError) as exc:
                _controls.pop(self.sim, None)
                _unreachable[self.sim] = repr(exc)
                pytest.fail("simulator %s: control call %s failed: %r" % (self.sim, name, exc))
        return call


def sim_set(sim, signal, value):
    forced.add((sim, signal))
    control(sim).set(signal, value)


def sim_release(sim, signal):
    control(sim).release(signal)
    forced.discard((sim, signal))


def sim_value(sim, signal, what="value"):
    return control(sim).get(signal)[what]


class fault:
    """with fault("mat_co", "silent", unit=5): ... - always cleared on exit."""

    def __init__(self, sim, mode, unit=None):
        self.sim, self.mode, self.unit = sim, mode, unit

    def __enter__(self):
        control(self.sim).fault(self.mode, unit=self.unit)
        self.t0 = time.monotonic()
        return self

    def __exit__(self, *exc):
        control(self.sim).clear(self.mode, unit=self.unit)


def clear_everything():
    """No fault in any simulator, no signal held by the suite."""
    problems = []
    for sim in reg.simulators:
        if sim in _unreachable:
            problems.append("%s unreachable" % sim)
            continue
        try:
            control(sim).clear()
        except BaseException as exc:      # noqa: BLE001  clean up as much as possible
            problems.append("%s: %r" % (sim, exc))
    for sim, signal in list(forced):
        try:
            sim_release(sim, signal)
        except BaseException as exc:      # noqa: BLE001
            problems.append("%s %s: %r" % (sim, signal, exc))
    return problems


# --- logs ----------------------------------------------------------------------------------------

def log_path(service):
    return BUILD / ("%s.log" % service)


def log_lines(service):
    path = log_path(service)
    if not path.exists():
        pytest.fail("%s does not exist: run the suite with `make -C emulation test`, which "
                    "saves the container logs there" % path)
    text = path.read_text(errors="replace")
    lines = [re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", l).rstrip("\r") for l in text.splitlines()]
    return [l[len("epics> "):] if l.startswith("epics> ") else l for l in lines]


def report(text, capsys=None):
    """Print past pytest's capture (the table belongs in the output of `make test`)."""
    if capsys is not None:
        with capsys.disabled():
            print("\n" + text)
    else:
        print("\n" + text)


def ioc_container(ioc):
    return reg.iocs[ioc]["container"]


def env(name, default=None):
    return os.environ.get(name, default)
