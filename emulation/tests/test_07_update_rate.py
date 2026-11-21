"""Update rate: for the monitor PVs of the polled AU supplies on both chains, and of the filament
heating supply (TDK) as a second example, the rate a Channel Access client sees and the rate the
simulator counts agree within 10 percent with the bus arithmetic: the line settings of the
simulator (baud, bits per character, turnaround), the polls the databases make, and the line
shared evenly among the supplies of a chain. The table goes to emulation/build/update-rate.md.

Where the prediction comes from, for each device:
  polls     read from the running IOC: every periodically scanned StreamDevice record of the
            device (SCAN, INP/OUT), and the StreamDevice records its forward links process; the
            monitor cycle is the protocols of the records with role vread and iread, repeated
            as fast as the line allows but at most at the fastest scan rate of the device
  commands  the out lines of each protocol in its .proto file, arguments substituted
  replies   the length of each reply, from the manuals (CO series rev 0.4 chapter 7, GENESYS
            chapter 7): REPLIES below
  line      a transaction holds the line for (request + reply characters, terminators
            included) x bits per character / baud, plus the turnaround when there is a reply
"""
import re
import time
from pathlib import Path

import pytest

import system as S
from system import reg

TOLERANCE = 0.10
SECONDS = 10.0                       # measuring time per case
OUT = S.BUILD / "update-rate.md"

# Reply to a request, by simulator type: (request pattern, reply text of typical length).
REPLIES = {
    "matsusada_co": [(r"#(\d+) MN1$", "MONI1=FFFH"), (r"#(\d+) MN2$", "MONI2=FFFH"),
                     (r"#(\d+) CH0\?$", "CH0=FFFFH"), (r"#(\d+) CH1\?$", "CH1=FFFFH"),
                     (r"#(\d+) SW\?$", "SW1"), (r"#(\d+) STS$", "#\\1 CO RM")],
    "tdk_genesys": [(r"MV\?$", "2.000"), (r"MC\?$", "080.00"), (r"OUT\?$", "ON"),
                    (r"MODE\?$", "CV"), (r"FLT\?$", "00")],
}
PERIOD = {"10 second": 10, "5 second": 5, "2 second": 2, "1 second": 1, ".5 second": 0.5,
          ".2 second": 0.2, ".1 second": 0.1}


# --- protocol files --------------------------------------------------------------------------------

_protocols = {}


def protocols(path):
    """{name: [out string, ...]} of a StreamDevice protocol file (exception handlers skipped)."""
    if path not in _protocols:
        text = Path(path).read_text()
        strings = []                         # string literals out of the way of the braces

        def keep(m):
            strings.append(m.group(1))
            return '"%d"' % (len(strings) - 1)
        lines = []
        for line in text.splitlines():   # a comment starts with # outside a string
            line = re.sub(r'"((?:[^"\\]|\\.)*)"', keep, line)
            lines.append(line.split("#", 1)[0])
        text = "\n".join(lines)
        text = re.sub(r"@\w+\s*\{[^{}]*\}", "", text)          # exception handlers
        out = {}
        for m in re.finditer(r"(\w+)\s*\{([^{}]*)\}", text):
            out[m.group(1)] = [strings[int(i)] for i in re.findall(r'\bout\s+"(\d+)"', m.group(2))]
        _protocols[path] = out
    return _protocols[path]


def expand(fmt, args):
    for k, a in enumerate(args, 1):
        fmt = fmt.replace("\\$%d" % k, a)
    fmt = re.sub(r"%\{([^}]*)\}", lambda m: max(m.group(1).split("|"), key=len), fmt)
    fmt = re.sub(r"%0?(\d+)[A-Za-z]", lambda m: "0" * int(m.group(1)), fmt)
    fmt = re.sub(r"%[-+.\d]*[A-Za-z]", "00000", fmt)
    return fmt.replace('\\"', '"').replace("\\\\", "\\")


def commands(record):
    """The requests a StreamDevice record sends: [str]."""
    fld = "INP" if reg.pvs[record]["type"] in ("ai", "bi", "mbbi", "longin", "stringin", "lsi",
                                                "aai") else "OUT"
    link = S.field(record, fld + "$")           # the whole link (a plain string ends at 40)
    m = re.match(r"@(\S+)\s+(\w+)(?:\(([^)]*)\))?\s+\S+", link)
    assert m, "%s: not a StreamDevice link: %r" % (record, link)
    proto = S.REPO / "EPICS" / "Db" / m.group(1)
    args = (m.group(3) or "").split(",") if m.group(3) else []
    return [expand(o, args) for o in protocols(proto)[m.group(2)]]


# --- the model ----------------------------------------------------------------------------------

class Line:
    def __init__(self, sim):
        info = S.control(sim).info()
        st = info["settings"]
        self.sim, self.type = sim, info["type"]
        self.baud, self.bits, self.turn = st["baud"], st["bits_per_char"], st["turnaround_ms"]
        self.inl, self.outl = len(st["in_terminator"]), len(st["out_terminator"])

    def reply(self, request):
        for pattern, reply in REPLIES[self.type]:
            m = re.match(pattern, request)
            if m:
                return m.expand(reply)
        return None

    def seconds(self, request):
        """Line time of one request and its reply; and 1 if it has a reply."""
        reply = self.reply(request)
        n = len(request) + self.inl + (0 if reply is None else len(reply) + self.outl)
        return n * self.bits / self.baud + (0 if reply is None else self.turn / 1000.0), \
            int(reply is not None)


def is_stream(name):
    return name in reg.pvs and S.field(name, "DTYP") == "stream"


def flnk_chain(name, seen):
    """Stream records processed by the forward links that follow a record."""
    out = []
    target = S.field(name, "FLNK").split()[0] if S.field(name, "FLNK").strip() else ""
    target = target.split(".")[0]
    if target and target not in seen and target in reg.pvs:
        seen.add(target)
        if is_stream(target):
            out.append(target)
        out += flnk_chain(target, seen)
    return out


def polls(device, line):
    """(monitor cycle seconds, replies per cycle, fixed load in s/s, fixed replies/s, cap Hz)."""
    pvs = reg.devices[device]["pvs"]
    monitors = [reg.role(device, r) for r in ("vread", "iread")]
    cycle = [line.seconds(c) for m in monitors for c in commands(m)]
    load = replies = 0.0
    cap = 0.0
    for name in pvs:
        scan = S.field(name, "SCAN")
        if scan not in PERIOD:
            continue
        cap = max(cap, 1.0 / PERIOD[scan])
        if name in monitors or not is_stream(name):
            continue
        for rec in [name] + [r for r in flnk_chain(name, {name}) if r not in monitors]:
            for c in commands(rec):
                t, r = line.seconds(c)
                load += t / PERIOD[scan]
                replies += r / PERIOD[scan]
    return sum(t for t, _ in cycle), sum(r for _, r in cycle), load, replies, cap


def predict(devices, line):
    """Even shares: every polled supply of the line gets the same monitor rate."""
    p = {d: polls(d, line) for d in devices}
    free = 1.0 - sum(v[2] for v in p.values())
    rate = min(min(v[4] for v in p.values()), free / sum(v[0] for v in p.values()))
    return rate, p


# --- measuring ------------------------------------------------------------------------------------

def measure(devices, line):
    """{device: (CA rate of vread, CA rate of iread)}, and the simulator's replies/s per unit."""
    monitors = {d: [reg.role(d, "vread"), reg.role(d, "iread")] for d in devices}
    names = [n for v in monitors.values() for n in v]
    for n in names:
        S.put_field(n, "MDEL", -1)           # every processing posted, also an unchanged value
    try:
        c = S.control(line.sim)
        c.stats(reset=True)
        t0 = time.monotonic()
        S.wait_for(lambda: time.monotonic() - t0 >= SECONDS, SECONDS + 2, "measuring")
        t1 = time.monotonic()
        stats = c.stats()
        ca = {d: tuple(sum(1 for t, _ in list(S.watched(n).events) if t0 <= t < t1) / (t1 - t0)
                       for n in v) for d, v in monitors.items()}
    finally:
        for n in names:
            S.put_field(n, "MDEL", 0)
    return ca, stats


def unit_of(device):
    ref = reg.devices[device]["simulators"][0]
    return ref.split(":")[1] if ":" in ref else None


rows = []


def run_case(label, sim, devices):
    line = Line(sim)
    rate, p = predict(devices, line)
    ca, stats = measure(devices, line)
    for d in devices:
        cycle_t, cycle_r, load, fixed_r, cap = p[d]
        unit = unit_of(d)
        if unit is not None:
            replies = stats["per_unit"].get(unit, {}).get("replies", 0) / stats["elapsed_s"]
        else:
            replies = stats["replies"] / stats["elapsed_s"]
        sim_rate = (replies - fixed_r) / cycle_r
        rows.append(dict(case=label, sim=sim, device=d, unit=unit or "-", baud=line.baud,
                         bits=line.bits, turn=line.turn, cycle_ms=cycle_t * 1000,
                         load=100 * sum(v[2] for v in p.values()), pred=rate,
                         ca_v=ca[d][0], ca_i=ca[d][1], sim_rate=sim_rate))
    write_table()
    return [r for r in rows if r["case"] == label]


def write_table():
    lines = ["# Update rate of the monitor PVs", "",
             "Predicted: bus arithmetic, the line shared evenly (see test_07_update_rate.py). "
             "Measured over %g s: CA V / CA I = monitor updates of the vread / iread PV seen by a "
             "Channel Access client, sim = monitor transactions per second counted by the "
             "simulator (replies of the unit minus the fixed polls, per monitor cycle)." % SECONDS,
             "", "| case | simulator | device | unit | baud | bits | turnaround ms | cycle ms | "
             "fixed load % | predicted Hz | CA V Hz | CA I Hz | sim Hz | CA/pred |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %d | %d | %g | %.1f | %.1f | %.2f | %.2f | %.2f | "
                     "%.2f | %.0f%% |" % (r["case"], r["sim"], r["device"], r["unit"], r["baud"],
                                          r["bits"], r["turn"], r["cycle_ms"], r["load"],
                                          r["pred"], r["ca_v"], r["ca_i"], r["sim_rate"],
                                          100 * (r["ca_v"] + r["ca_i"]) / 2 / r["pred"]))
    OUT.write_text("\n".join(lines) + "\n")


def check(case_rows):
    bad = []
    for r in case_rows:
        for what in ("ca_v", "ca_i", "sim_rate"):
            if abs(r[what] / r["pred"] - 1) > TOLERANCE:
                bad.append("%s %s: %s %.2f Hz, predicted %.2f Hz" % (
                    r["case"], r["device"], what, r[what], r["pred"]))
    assert bad == [], "more than %d %% from the bus arithmetic:\n%s" % (100 * TOLERANCE,
                                                                       "\n".join(bad))


def au_chains():
    """{simulator: [polled AU supplies on it]}: the devices of class supply on a matsusada_co
    simulator with more than one unit (the REK has its own line)."""
    out = {}
    for d, dev in reg.devices.items():
        if dev["class"] != "supply" or reg.not_polled(d):
            continue
        sim = dev["simulators"][0].split(":")[0]
        if reg.simulators[sim]["type"] == "matsusada_co" and len(reg.units(sim)) > 1:
            out.setdefault(sim, []).append(d)
    return out


@pytest.mark.parametrize("sim", sorted(au_chains()))
def test_au_monitor_rate_matches_the_bus_arithmetic(sim, capsys):
    devices = au_chains()[sim]
    case_rows = run_case("AU chain %s" % sim, sim, devices)
    check(case_rows)


@pytest.fixture
def tdk_on():
    d = "fil_heat"
    cmd, vset, iset = (reg.role(d, r) for r in ("out_cmd", "vset", "iset"))
    before = {n: S.get(n) for n in (cmd, vset, iset)}
    S.put(vset, reg.pvs[vset]["test"][1])
    S.put(iset, reg.pvs[iset]["test"][1])
    S.put(cmd, 1)
    S.wait_for(lambda: S.get(reg.role(d, "out_state")) == 1, 5, "TDK output on")
    yield d
    for n in (cmd, vset, iset):
        S.put(n, before[n])
    S.wait_for(lambda: S.get(reg.role(d, "out_state")) == before[cmd], 5, "TDK output back")


def test_filament_heating_rate_matches_the_line_arithmetic(tdk_on, capsys):
    """Output on at the end of the test ranges, so that the replies have their full length.
    Runs last in this module and prints the whole table."""
    sim = reg.devices[tdk_on]["simulators"][0]
    case_rows = run_case("filament heating", sim, [tdk_on])
    S.report(OUT.read_text(), capsys)
    check(case_rows)
