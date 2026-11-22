#!/usr/bin/env python3
"""Write the device registry for the GUI and the tests: RAS/mist2/ReactApp/src/registry/registry.json.

    python plan/registry.py            # write it
    python plan/registry.py --check    # only compare with the committed file, exit 1 if it differs

Inputs: plan/controls.yaml (devices, roles, labels, test ranges), the databases in EPICS/Db, the
st.cmd files of both IOCs and, for the simulators, ports.sim.cmd next to each st.cmd,
emulation/compose.yaml and emulation/sim/config/*.yaml. The output depends on nothing else, so the
same inputs give the same file. Runs the consistency check of build.py and writes nothing when it
warns. Needs Python 3.9+ and PyYAML.
"""
import argparse
import json
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import REPO, WRITE_TYPES, Model, db_states, loads_of  # noqa: E402

OUT = os.path.join(REPO, "RAS", "mist2", "ReactApp", "src", "registry", "registry.json")


class Error(Exception):
    pass


def simulators(model):
    """Asyn port of each IOC -> simulator: {(host, asyn port): {name, type, host, port, control_port, config}}."""
    with open(os.path.join(REPO, "emulation", "compose.yaml"), encoding="utf-8") as handle:
        services = yaml.safe_load(handle)["services"].values()
    configs, containers = {}, {}
    for service in services:
        command = service.get("command") or []
        if "--config" in command:
            config = os.path.join(service.get("working_dir", "/repo").replace("/repo", "", 1).lstrip("/"),
                                  command[command.index("--config") + 1])
            configs[service["hostname"]] = config
        elif len(command) == 2 and command[1] == "sim":
            containers[command[0]] = service["hostname"]
    sims, iocs = {}, {}
    for host in model.d["hosts"]:
        if not host.get("st_cmd"):
            continue
        boot = os.path.dirname(host["st_cmd"])
        iocs[host["id"]] = containers.get(os.path.basename(boot))
        ports_file = os.path.join(boot, "ports.sim.cmd")
        if not os.path.exists(os.path.join(REPO, ports_file)):
            continue        # an IOC without ports (iocLoop): Channel Access only
        with open(os.path.join(REPO, ports_file), encoding="utf-8") as handle:
            for asyn, sim_host, port in re.findall(r'^\s*drvAsynIPPortConfigure\(\s*"([^"]+)"\s*,\s*"([^":]+):(\d+)"',
                                                  handle.read(), re.M):
                if sim_host not in configs:
                    raise Error("%s: port %s goes to %s, which is no simulator in emulation/compose.yaml" % (ports_file, asyn, sim_host))
                with open(os.path.join(REPO, configs[sim_host]), encoding="utf-8") as cfg:
                    entries = [e for e in yaml.safe_load(cfg) if e["port"] == int(port)]
                if len(entries) != 1:
                    raise Error("%s: port %s goes to %s:%s, which %s does not define once" % (ports_file, asyn, sim_host, port, configs[sim_host]))
                sim = entries[0]
                sims[(host["id"], asyn)] = {"name": sim["name"], "type": sim["type"], "host": sim_host, "port": sim["port"],
                                            "control_port": sim.get("control_port", sim["port"] + 1000),
                                            "config": configs[sim_host], "ioc": host["id"], "asyn_port": asyn}
    return sims, iocs


def stream_port(fields):
    """Asyn port of a StreamDevice record and whether it reads (INP) or writes (OUT)."""
    if fields.get("DTYP") != "stream":
        return None, None
    link = fields.get("INP") or fields.get("OUT") or ""
    return link.split()[-1], "in" if "INP" in fields else "out"


def build(model):
    sims, containers = simulators(model)
    owners = {o["id"]: o for o in model.owners}
    hosts = {h["id"] for h in model.d["hosts"]}
    subsystems = {s["id"]: s for s in model.d["subsystems"]}
    records, used = {}, {}
    # Every record of both IOCs: its owner and the simulator (and unit) behind it.
    for owner in model.owners:
        host = owner["id"] if owner["id"] in hosts else owner["host"]
        for pv in owner["pvs"]:
            if pv["state"] != "existing":
                continue
            port, direction = stream_port(pv["fields"])
            sim = None
            if port:
                if (host, port) not in sims:
                    raise Error("%s: record %s uses asyn port %s, which ports.sim.cmd of %s does not configure"
                                % (owner["id"], pv["name"], port, host))
                unit_macro = (model.rules.get(pv["db"]) or {}).get("unit")
                unit = model.macros(pv["load"]).get(unit_macro) if unit_macro else None
                sim = sims[(host, port)]["name"] + (":%s" % unit if unit is not None else "")
                used[sims[(host, port)]["name"]] = sims[(host, port)]
            records[pv["name"]] = dict(pv, owner=owner["id"], sim=sim, direction=direction)
    # Which records turn INVALID when a simulator is silent, and when its connection is closed: the
    # rule of build.py (fault_analysis), with the simulator (and unit) behind each device record.
    faults = model.faults(lambda pv, port, unit: records[pv["name"]]["sim"])

    def entry(owner):
        out_roles, out_channels, pvs = {}, {}, {}
        labels, states = owner.get("labels") or {}, owner.get("states") or {}
        spare, confirm = set(owner.get("spare") or []), owner.get("confirm") or {}
        for pv in owner["pvs"]:
            if pv["state"] != "existing":
                continue
            r = records[pv["name"]]
            item = {"type": pv["type"], "access": "w" if pv["type"] in WRITE_TYPES else "r"}
            for key in ("egu", "desc"):
                if pv[key]:
                    item[key] = pv[key]
            if pv.get("aliases"):
                item["aliases"] = pv["aliases"]
            if db_states(pv):
                item["states"] = db_states(pv)
            if pv.get("internal"):
                item["internal"] = True
            if pv.get("role"):
                item["role"] = pv["role"]
                scope = out_roles
                if pv.get("channel"):
                    item["channel"] = pv["channel"]
                    if pv["channel"] not in out_channels:
                        channel = out_channels[pv["channel"]] = {"label": labels.get(pv["channel"])}
                        if pv["channel"] in spare:
                            channel["spare"] = True
                        if pv["channel"] in states:
                            channel["states"] = states[pv["channel"]]
                        channel["roles"] = {}
                    scope = out_channels[pv["channel"]]["roles"]
                scope[pv["role"]] = pv["name"]
                spec = pv["spec"]
                for key in ("test", "ack", "note"):
                    if key in spec:
                        item[key] = spec[key]
                if "readback" in spec:
                    item["readback"] = spec["readback"]
                ask = confirm.get(pv.get("channel")) or confirm.get(pv["role"])
                if ask and item["access"] == "w":
                    item["confirm"] = ask
            if r["sim"]:
                item["sim"] = r["sim"]
            if faults["silent"][pv["name"]]:
                item["fails_with"] = sorted(faults["silent"][pv["name"]])
            if faults["closed"][pv["name"]]:
                item["fails_closed"] = sorted(faults["closed"][pv["name"]])
            pvs[pv["name"]] = item
        # readback: role name -> PV name, looked up in the channel first, then in the device
        for item in pvs.values():
            if item.get("readback"):
                scope = dict(out_roles, **(out_channels[item["channel"]]["roles"] if "channel" in item else {}))
                if item["readback"] not in scope:
                    raise Error("%s: the read-back role %r of %s does not exist" % (owner["id"], item["readback"], item["role"]))
                item["readback"] = scope[item["readback"]]
        classes = sorted({pv["cls"] for pv in owner["pvs"] if pv.get("cls")})
        result = {"name": owner["name"], "class": classes[0] if classes else None}
        result["roles"] = out_roles
        if out_channels:
            result["channels"] = out_channels
        role_labels = {k: v for k, v in labels.items() if k in out_roles}
        if role_labels:
            result["labels"] = role_labels
        role_states = {k: v for k, v in states.items() if k in out_roles}
        if role_states:
            result["states"] = role_states
        result["simulators"] = sorted({r["sim"] for r in records.values() if r["owner"] == owner["id"] and r["sim"]})
        result["loads"] = [{"db": l["db"], "macros": {k: str(v) for k, v in model.macros(l).items()}} for l in loads_of(owner)]
        result["pvs"] = pvs
        return result

    registry = {
        "about": "Generated by plan/registry.py from plan/controls.yaml, EPICS/Db and the st.cmd files. Do not edit.",
        "plan_revision": model.d["meta"]["revision"],
        "iocs": {}, "devices": {}, "simulators": {},
    }
    for host in model.d["hosts"]:
        if host["id"] in owners:
            item = entry(host)
            head = {"name": host["name"], "st_cmd": host["st_cmd"], "container": containers.get(host["id"])}
            registry["iocs"][host["id"]] = dict(head, **{k: v for k, v in item.items() if k not in head})
    for dev in model.devices:
        if dev["id"] not in owners:
            continue  # planned, no database yet
        item = entry(dev)
        sub = subsystems[dev["subsystem"]]
        head = {"name": dev["name"], "model": dev.get("model"), "class": item["class"], "subsystem": dev["subsystem"],
                "page": sub.get("page"), "ioc": dev["host"], "status": dev["status"], "flags": dev.get("flags") or {}}
        registry["devices"][dev["id"]] = dict(head, **{k: v for k, v in item.items() if k not in head})
    for name in sorted(used):
        sim = dict(used[name])
        del sim["name"]
        registry["simulators"][name] = sim
    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yaml", default=os.path.join(REPO, "plan", "controls.yaml"))
    parser.add_argument("--db-dir", default=os.path.join(REPO, "EPICS", "Db"))
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--check", action="store_true", help="compare with the file, write nothing")
    args = parser.parse_args()
    model = Model(args.yaml, args.db_dir)
    if model.warnings:
        for warning in model.warnings:
            print("ERROR:", warning)
        sys.exit("registry.py: controls.yaml, the databases and the st.cmd files disagree (%d problem(s)), nothing written"
                 % len(model.warnings))
    try:
        text = json.dumps(build(model), indent=1, ensure_ascii=False) + "\n"
    except Error as error:
        sys.exit("registry.py: ERROR: %s" % error)
    if args.check:
        same = os.path.exists(args.out) and open(args.out, encoding="utf-8").read() == text
        print("registry.py: %s is %s" % (os.path.relpath(args.out, REPO), "up to date" if same else "OUT OF DATE"))
        sys.exit(0 if same else 1)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(text)
    data = json.loads(text)
    print("registry.py: %d devices, %d IOCs, %d PVs, %d simulators -> %s" % (
        len(data["devices"]), len(data["iocs"]),
        sum(len(d["pvs"]) for d in list(data["devices"].values()) + list(data["iocs"].values())),
        len(data["simulators"]), os.path.relpath(args.out, REPO)))


if __name__ == "__main__":
    main()
