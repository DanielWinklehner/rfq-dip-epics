"""Startup: both IOC logs are free of database, protocol, link and startup errors, every PV of the
registry is connected and served by the IOC the registry names, and each simulator runs the line
settings of the real serial port it stands in for."""
import re
import socket
from datetime import datetime

import pytest

import system as S
from system import reg

IOCS = list(reg.iocs)

# A line of the startup (before "iocRun: All initialization complete") that means an error:
# dbLoadRecords (record type, field, macro, file), StreamDevice protocol parsing, asyn port
# configuration, links, iocsh commands. Echoed st.cmd lines and comments are not checked.
CONFIG_ERROR = re.compile(r"error|can't open|cannot|not found|undefined|no such|illegal|invalid"
                          r"|failed|unknown|syntax|bad |parse|link|warning|missing|duplicate"
                          r"|not allowed|abort|could not connect|not connected|autoconnect", re.I)
ECHO = re.compile(r"^\s*(#|on error|epicsEnvSet|dbLoad|iocshLoad|drvAsyn|asynSetOption"
                  r"|mist2_register|iocInit)")
INIT_DONE = "iocRun: All initialization complete"

# After iocInit the only messages allowed are those of StreamDevice and asyn about the traffic,
# which the fault tests cause on purpose: no reply, a reply that does not parse, a dropped or
# refused connection (and the line that ends such a message). Anything else is an error, also a
# Channel Access link message (the platform IOC reads interlock_open from the rack IOC).
TIMESTAMP = r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\.\d+ "
TRAFFIC = re.compile(
    TIMESTAMP + r"\S+ (?:\S+:? )?"
    r"(?:No reply within \d+ ms|No reply from device within \d+ ms"
    r"|Input \".*|mismatch after \d+ bytes? .*"
    r"|got \".*\"|No match for .*|device \S+ \d+ disconnected"
    r"|lockRequest: (?:port \S+ not connected|status returned to normal)"
    r"|connectCallback\(\w+\) called unexpectedly|\d+ additional errors of the following type"
    r"|Timeout after reading \d+ bytes? .*|Async read timeout.*"
    r"|.*still busy.*|Read error.*|Write error.*|.*Connection reset by peer.*"
    r"|.*Broken pipe.*|.*Connection refused.*)")
# autosave starts after iocInit (st.cmd): the request file of the current limits and the restore,
# which must find every PV of the saved file ("N of N")
AUTOSAVE = re.compile(r"^(afterIocRunning: (makeAutosaveFileFromDbInfo|create_monitor_set) \S+"
                      r"|\S+\.sav: (\d+) of \3 PV's connected$)")
CONTINUATION = re.compile(r"^\s+\S")      # StreamDevice prints the offending input on the next lines


def ioc_log(ioc):
    container = S.ioc_container(ioc)
    S.wait_for(lambda: any(INIT_DONE in l for l in S.log_lines(container)), 15,
               "%s in %s" % (INIT_DONE, S.log_path(container)))
    lines = [l for l in S.log_lines(container) if l.strip()]
    done = next(i for i, l in enumerate(lines) if INIT_DONE in l)
    return lines[:done], lines[done + 1:]


@pytest.mark.parametrize("ioc", IOCS)
def test_ioc_starts_without_database_protocol_or_link_error(ioc):
    init, _ = ioc_log(ioc)
    assert any("Starting iocInit" in l for l in init), "iocInit did not start"
    errors = [l for l in init if CONFIG_ERROR.search(l) and not ECHO.match(l)]
    assert errors == [], "errors in the startup of %s:\n%s" % (ioc, "\n".join(errors))


@pytest.mark.parametrize("ioc", IOCS)
def test_ioc_log_after_start_has_only_traffic_messages(ioc):
    _, run = ioc_log(ioc)
    errors, previous = [], None
    for l in run:
        if AUTOSAVE.match(l):
            continue
        if TRAFFIC.match(l) or (CONTINUATION.match(l) and previous == "traffic"):
            previous = "traffic"
            continue
        previous = None
        errors.append(l)
    assert errors == [], "%d lines of %s are not traffic messages:\n%s" % (
        len(errors), ioc, "\n".join(errors[:30]))


def first_fault_time():
    """Wall clock of the first fault injected into any simulator (sim logs), or None."""
    first = None
    for host in sorted({s["host"] for s in reg.simulators.values()}):
        for l in S.log_lines(host):
            m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d+) \S+ INFO fault (?!.*cleared)", l)
            if m:
                t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + \
                    int(m.group(2)) / 1000.0
                first = t if first is None else min(first, t)
                break
    return first


def stamp(line):
    m = re.match(r"(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d)\.(\d+) ", line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y/%m/%d %H:%M:%S").timestamp() + float("0." + m.group(2))


@pytest.mark.parametrize("ioc", IOCS)
def test_ioc_reaches_every_device_at_start(ioc):
    """Until the first fault a test injects, an IOC has nothing to complain about: no traffic
    message at all, in particular no "autoConnect could not connect" or "port ... not connected"
    (a device that was not reachable when the IOC started)."""
    _, run = ioc_log(ioc)
    first = first_fault_time()
    early = [l for l in run if stamp(l) is not None and (first is None or stamp(l) < first)]
    assert early == [], "%s before the first fault (%s):\n%s" % (
        ioc, first and datetime.fromtimestamp(first), "\n".join(early[:20]))


@pytest.mark.parametrize("ioc", IOCS)
def test_ioc_runs_with_simulator_ports(ioc):
    mode = reg.iocs[ioc]["roles"]["mode"]
    assert S.get(mode) == "sim"
    assert S.sevr(mode) == S.NO_ALARM


SIM_HOSTS = sorted({s["host"] for s in reg.simulators.values()})


@pytest.mark.parametrize("host", SIM_HOSTS)
def test_simulator_log_has_no_device_error(host):
    """A simulator logs a Python exception (device error, traceback) when a device module fails
    on a request; WARNING and ERROR lines are listed too."""
    lines = S.log_lines(host)
    assert any(" INFO " in l for l in lines), "%s is empty" % S.log_path(host)
    bad = [l for l in lines if re.search(r"Traceback|device error| ERROR | CRITICAL ", l)]
    # The NT 20 monitors couple to the Opta's control port; they warn while it is closed by a
    # fault test, which is the fault itself.
    bad += [l for l in lines if " WARNING " in l and "Opta" not in l]
    assert bad == [], "\n".join(bad[:30])


def server_address(host):
    """host:port of a channel's server (CA reports a name where it can resolve one) -> address."""
    return socket.gethostbyname(host.rsplit(":", 1)[0])


@pytest.mark.parametrize("device", list(reg.devices) + list(reg.iocs))
def test_every_pv_is_connected_to_the_ioc_of_the_registry(device):
    entry = reg.devices.get(device) or reg.iocs[device]
    ioc = entry.get("ioc", device)
    address = reg.ioc_address(ioc)
    names = list(entry["pvs"])
    missing = [n for n in names if not S.connected(n)]
    assert missing == [], "not connected (no IOC serves them): %s" % missing
    wrong = {n: S._pv(n).host for n in names if server_address(S._pv(n).host) != address}
    assert wrong == {}, "served by another IOC than %s (%s): %s" % (ioc, address, wrong)


# --- line settings -----------------------------------------------------------------------------

def real_port_settings():
    """asyn port -> settings of ports.real.cmd of both IOCs: {"kind": "serial"|"ip", baud ...}."""
    out = {}
    for ioc in reg.iocs.values():
        path = S.REPO / ioc["st_cmd"]
        text = (path.parent / "ports.real.cmd").read_text()
        for port, _ in re.findall(r'drvAsynSerialPortConfigure\("([^"]+)",\s*"([^"]+)"', text):
            out[port] = {"kind": "serial"}
        for port, _ in re.findall(r'drvAsynIPPortConfigure\("([^"]+)",\s*"([^"]+)"', text):
            out[port] = {"kind": "ip"}
        for port, key, value in re.findall(r'asynSetOption\("([^"]+)",\s*-?\d+,\s*"(\w+)",\s*"([^"]*)"\)', text):
            out.setdefault(port, {"kind": "serial"})[key] = value
    return out


LINE_FINDING = {"gauges": "FINDING: ports.real.cmd opens AVR6 (the Teensy) with 8 bits, even "
                          "parity, 1 stop (11 bits per character), the simulator times 10 bits "
                          "(rack.yaml: 'USB serial of the Teensy: only sets the reply delay'); "
                          "one of the two files is wrong, or the real port should say that the "
                          "setting has no effect on a USB serial"}


@pytest.mark.parametrize("sim", [pytest.param(s, marks=pytest.mark.xfail(strict=True,
                                                                          reason=LINE_FINDING[s]))
                                 if s in LINE_FINDING else s for s in reg.simulators])
def test_simulator_line_matches_the_real_port(sim):
    """The simulator's baud rate and bits per character are those of the serial port the real
    IOC opens (ports.real.cmd): the reply timing, and so every rate this suite measures, depends
    on them. A device on Ethernet in reality has no line to compare."""
    port = reg.simulators[sim]["asyn_port"]
    real = real_port_settings().get(port)
    assert real is not None, "asyn port %s of %s is not in ports.real.cmd" % (port, sim)
    settings = S.control(sim).info()["settings"]
    if real["kind"] == "ip":
        assert "baud" not in real
        return
    bits = 1 + int(real.get("bits", 8)) + (0 if real.get("parity", "none") == "none" else 1) \
        + int(real.get("stop", 1))
    assert (settings["baud"], settings["bits_per_char"]) == (int(real["baud"]), bits), (
        "%s simulates %s baud, %s bits per character; the real port %s is %s baud, %d bits per "
        "character" % (sim, settings["baud"], settings["bits_per_char"], port, real["baud"], bits))
