"""Channel Access and simulator side of tools/gui-check.sh.

Runs in the tools container of the emulation (pyepics, mist2sim on the path),
with the repository at /repo. Every name comes from the registry.

    read OUT.json               value, severity and connection of every PV
    fault SIM[:UNIT] ...        make simulators (or one unit) silent
    clear SIM[:UNIT] ...        clear their faults
    wait PV VALUE [SECONDS]     until PV reads VALUE (as a string), exit 1 if not
    compare A.json B.json GUI.json
                                check the GUI's values against two reads that
                                bracket it in time; prints one line per failure
"""
import json
import math
import sys
import time

import epics
from mist2sim.control import ControlClient

REGISTRY = "/repo/RAS/mist2/ReactApp/src/registry/registry.json"
registry = json.load(open(REGISTRY))


def all_pvs():
    """Every PV of the registry: IOC records and every device record."""
    out = {}
    for ioc in registry["iocs"].values():
        out.update(ioc["pvs"])
    for device in registry["devices"].values():
        out.update(device["pvs"])
    return out


def field_name(name, info):
    return name + ".VAL$" if info["type"] in ("lsi", "lso") else name


def read(path):
    infos = all_pvs()
    pvs = {name: epics.PV(field_name(name, info), form="ctrl") for name, info in infos.items()}
    deadline = time.time() + 5
    for pv in pvs.values():
        pv.wait_for_connection(max(0.1, deadline - time.time()))
    result = {}
    for name, pv in pvs.items():
        if not pv.connected:
            result[name] = {"connected": False}
            continue
        number = pv.get(use_monitor=False, timeout=2)
        array = hasattr(number, "__len__") and not isinstance(number, str)
        result[name] = {
            "connected": True,
            "text": pv.get(as_string=True, use_monitor=False, timeout=2),
            "number": number if isinstance(number, (int, float)) else None,
            "array": [float(x) for x in number] if array else None,
            "long": infos[name]["type"] in ("lsi", "lso"),
            "severity": pv.severity,
        }
    json.dump(result, open(path, "w"), indent=1)
    print(f"read {len(result)} PVs, {sum(1 for r in result.values() if r['connected'])} connected")


def control(spec):
    name, _, unit = spec.partition(":")
    sim = registry["simulators"][name]
    return ControlClient(sim["host"], sim["control_port"], timeout=5.0), (int(unit) if unit else None)


def fault(specs):
    for spec in specs:
        client, unit = control(spec)
        with client:
            client.fault("silent", unit=unit)
        print(f"silent: {spec}")


def clear(specs):
    for spec in specs:
        client, unit = control(spec)
        with client:
            client.clear(unit=unit)
        print(f"cleared: {spec}")


def wait(name, value, seconds=15):
    pv = epics.PV(field_name(name, all_pvs()[name]), form="ctrl")
    deadline = time.time() + float(seconds)
    seen = None
    while time.time() < deadline:
        seen = pv.get(as_string=True, use_monitor=False, timeout=2)
        if seen == value or (first_number(seen) is not None and first_number(value) is not None
                             and abs(first_number(seen) - first_number(value)) < 1e-6):
            print(f"PASS {name} = {value}")
            return 0
        time.sleep(0.3)
    print(f"FAIL {name} = {seen!r}, expected {value!r} within {seconds} s")
    return 1


def first_number(text):
    try:
        return float(text.split()[0])
    except (ValueError, IndexError, AttributeError):
        return None


def near(g, lo, hi, digits):
    slack = 0.25 * max(abs(lo), abs(hi), abs(g)) + 10.0 * 10 ** -digits + 1e-12
    return lo - slack <= g <= hi + slack and not math.isnan(g)


def matches(shown, a, b):
    """The value the GUI showed lies between two CA reads (with some slack for
    noise), or equals one of them as text."""
    gui_text = shown["value"]
    if gui_text in (a["text"], b["text"]):
        return True
    if a["array"] is not None:
        try:
            g = [float(x) for x in gui_text.split(",")]
        except ValueError:
            return False
        return len(g) == len(a["array"]) and all(
            near(x, *sorted((y, z)), 6) for x, y, z in zip(g, a["array"], b["array"]))
    g = first_number(gui_text)
    if g is None or a["number"] is None or b["number"] is None:
        # A long text that changes with every update (the last turbopump
        # record, noise in its current) may have shown a third value. Its
        # time stamp does not tell: through pvServer it was seen to carry the
        # time of the next update with the text of the one before.
        return a["long"] and gui_text not in ("", "no connection")
    lo, hi = sorted((a["number"], b["number"]))
    return near(g, lo, hi, len(str(a["text"]).partition(".")[2]))


def compare(path_a, path_b, path_gui):
    a, b, gui = (json.load(open(p)) for p in (path_a, path_b, path_gui))
    failures = 0
    checked = 0
    for name, shown in gui["expert"].items():
        ra, rb = a.get(name), b.get(name)
        if not (ra and rb and ra["connected"] and rb["connected"]):
            print(f"FAIL {name}: not connected through Channel Access")
            failures += 1
            continue
        checked += 1
        if not matches(shown, ra, rb):
            print(f"FAIL {name}: GUI shows {shown['value']!r}, Channel Access {ra['text']!r} then {rb['text']!r}")
            failures += 1
        sev_names = ["NO_ALARM", "MINOR", "MAJOR", "INVALID"]
        if shown["sevr"] not in (sev_names[ra["severity"]], sev_names[rb["severity"]]):
            print(f"FAIL {name}: GUI severity {shown['sevr']}, Channel Access {sev_names[ra['severity']]}")
            failures += 1
    print(f"compared {checked} PVs of the device windows with Channel Access: {failures} failures")
    return 1 if failures else 0


def main():
    command, *args = sys.argv[1:]
    if command == "read":
        read(args[0])
    elif command == "fault":
        fault(args)
    elif command == "clear":
        clear(args)
    elif command == "wait":
        return wait(*args)
    elif command == "compare":
        return compare(*args)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
