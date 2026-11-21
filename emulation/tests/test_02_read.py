"""Read: every PV of every device answers and is not INVALID. The exceptions are asserted, not
skipped: a record that has never been processed since the IOC started (alarm status UDF), which
is allowed only for a set record or an internal record that nothing scans, and for every record of
a device the registry flags `not_polled`. The identity PVs of the libcom1 boards name the
simulator that the registry puts behind them (the wiring of ports and simulators)."""
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
    if reg.not_polled(spec["device"]):
        return "device not polled (%s)" % reg.devices[spec["device"]]["flags"]["not_polled"]
    if (spec["access"] == "w" or spec.get("internal")) and S.field(name, "SCAN") == "Passive":
        return "set or internal record, not scanned, not written since the IOC started"
    return None


@pytest.mark.parametrize("device", DEVICES)
def test_every_pv_reads_and_is_not_invalid(device):
    entry = reg.devices.get(device) or reg.iocs[device]
    # A fault test before this one may still be recovering when tests are selected with -k.
    names = list(entry["pvs"])
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
    assert problems == [], "INVALID without a reason the registry gives: %s" % problems
    if excused:
        print("\n".join(["%s, INVALID (UDF) as allowed:" % device] + excused))


def test_not_polled_device_records_are_never_read():
    """A device flagged not_polled: its monitor and status records are never processed, so they
    stay INVALID with status UDF; everything an operator writes, and the echoes read after a
    write, may be valid. Asserted for each such device of the registry."""
    devices = [d for d in reg.devices if reg.not_polled(d)]
    assert devices, "the registry flags no device not_polled (lens 3 was): update this test"
    for device in devices:
        for name, spec in reg.devices[device]["pvs"].items():
            if spec["access"] == "r" and spec.get("role") in ("vread", "iread", "power", "status"):
                d = S.read(name)
                assert (d["severity"], d["status"]) == (S.INVALID, S.UDF), \
                    "%s of a device that is not polled: %s" % (name, S.describe([name]))
                assert S.field(name, "SCAN") in ("Passive", "Event", "I/O Intr")


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
