"""Read: every PV of every device answers and is not INVALID. The exceptions are asserted, not
skipped: a record that has never been processed since the IOC started (alarm status UDF), which
is allowed only for a set record or an internal record that nothing scans. Aliases answer with the
value of their record, spare channels are read and valid. The identity PVs of the libcom1 boards name the
simulator that the registry puts behind them (the wiring of ports and simulators)."""
import time

import pytest

import system as S
from system import reg
from conftest import snapshot

DEVICES = list(reg.devices) + list(reg.iocs)


def exception_reason(name, d):
    """Why an INVALID PV is acceptable, or None. Asserts what such a PV must show."""
    spec = reg.pvs[name]
    if d["status"] != S.UDF:
        return None                       # INVALID for a reason other than "never processed"
    if (spec["access"] == "w" or spec.get("internal")) and S.field(name, "SCAN") == "Passive":
        return "set or internal record, not scanned, not written since the IOC started"
    return None


# The slowest source sends every 8 s (NT 20 data output, listen only): right after an IOC start a
# PV may wait that long for its first value. Each device gets this long to have no unexplained
# INVALID PV.
FIRST_VALUE_LIMIT = 10.0


def unexplained(names):
    problems, excused = [], []
    for name in names:
        d = S.read(name)
        assert d["value"] is not None, "%s has no value" % name
        if d["severity"] != S.INVALID:
            continue
        why = exception_reason(name, d)
        if why:
            excused.append("%s: %s" % (name, why))
        else:
            problems.append(S.describe([name]))
    return problems, excused


@pytest.mark.parametrize("device", DEVICES)
def test_every_pv_reads_and_is_not_invalid(device):
    entry = reg.devices.get(device) or reg.iocs[device]
    names = list(entry["pvs"])
    S.wait_for(lambda: unexplained(names)[0] == [], FIRST_VALUE_LIMIT,
               lambda: "INVALID without a reason the registry gives: %s" % unexplained(names)[0])
    excused = unexplained(names)[1]
    if excused:
        print("\n".join(["%s, INVALID (UDF) as allowed:" % device] + excused))


def test_every_alias_answers_with_the_value_of_its_pv():
    """An alias (AU and REK current:setpoint, the lab's name of current:limit) is served by the
    same IOC and shows the record's value and severity."""
    aliases = [(n, a) for n, spec in reg.pvs.items() for a in spec.get("aliases", [])]
    assert aliases, "the registry lists no alias"
    for name, alias in aliases:
        assert S.connected(alias), "alias %s of %s is not served" % (alias, name)
        assert S.field(alias, "NAME") == name
        a, d = S.read(alias), S.read(name)
        assert (a["value"], a["severity"]) == (d["value"], d["severity"]), (alias, a, name, d)


SPARE_LIMIT = 3.0      # s: the boards are polled every 0.1 to 0.5 s; a silent board's reply timeout
                       # (1 s) turns its PVs INVALID


def test_spare_channels_are_read_and_valid():
    """A channel the registry marks spare (not connected) is still polled with its board: its
    read PVs are processed again and valid (its set records are written by the write test)."""
    spare = [pv for d in reg.devices.values() for ch in (d.get("channels") or {}).values()
             if ch.get("spare") for pv in ch["roles"].values() if reg.pvs[pv]["access"] == "r"]
    assert spare, "the registry marks no channel spare"
    now = time.time()
    for n in spare:                       # processed again (polled) and valid
        S.wait_fresh(n, now, lambda v: True, SPARE_LIMIT, "spare channel %s read again" % n)


IDENTITY = [d for d in reg.devices if reg.has_role(d, "id")]


@pytest.mark.parametrize("device", IDENTITY)
def test_identity_names_the_simulator_behind_the_device(device):
    """id, firmware and channel list come from the simulator the registry names for the device:
    a swapped port or simulator shows up here."""
    sims = [s for s in reg.devices[device]["simulators"] if reg.simulators[s.split(":")[0]]["type"] == "libcom1"]
    assert len(sims) == 1, sims
    options = S.control(sims[0]).info()["options"]
    assert S.get(reg.role(device, "id")) == options["identity"]
    assert S.get(reg.role(device, "firmware")) == options["firmware"]
    channels = S.field(reg.role(device, "channel_list"), "VAL$")
    assert channels == ",".join(c["id"] for c in options["channels"])
