"""A late reply on a Matsusada line (P49, task T22).

A reply that comes after the reply timeout (150 ms) and the 50 ms the protocol waits after it is
read by the next request on the line, possibly of another supply: a stray reply. Two remedies in
matsusada_co_ctrl.proto and rek.proto:
  R1  @mismatch keeps the line for 50 ms after a mismatch, so that the reply still on its way to
      the request that mismatched arrives and is discarded before the next write (StreamDevice
      reads and drops old input before every write): one mismatch, then in step.
  R2  every protocol whose reply is copied or compared as a state or a setting (probe,
      get_output_status, get_voltage, get_current, the read-backs of toggle_output, set_voltage,
      set_current) first asks the same unit for its status and checks the unit number in the
      reply. A stray is older than every reply to a later request, so it is the first input such
      a protocol reads, and the check fails on it unless it is this unit's own status.
The monitors (MN1, MN2) stay one request, one reply (R3): a monitor can take a neighbour's value
for at most one cycle before the first mismatch puts the line in step.

The line of these tests is mat_late (sim.yaml): LATE-1 and LATE-2 polled as in the rack, LATE-3
loaded with its scans Passive (a test polls it for three supplies on a line, or reads it by
hand). A late reply is made by the simulator's fault "slow" (ms 300) for one unit with a duration
shorter than 300 ms: the simulator holds the line for the delayed reply (one transaction at a
time), so the fault has expired before it processes that unit's next request, and at most one
reply is late. For the reply to the query after a status check the fault "slow_second" (the
unit's second reply late, once) is used. That it
was exactly one is checked in the IOC log: one "No reply within 150 ms" on the line in the
window, to a request of that unit.

Each test prints its timeline in seconds after the fault was set: what the IOC wrote to the line
and read from it (asyn trace, DEVTEST:asyn:mat_late), StreamDevice's messages of the line, and
the values of the records with their alarm (Channel Access, the records' own time stamps).
"""
import contextlib
import datetime
import os
import random
import re
import time

import epics
import pytest

from mat import (BUILD, GRACE, control, get, put, sevr, sim_log_mark, sim_log_since, sim_signal,
                 wait_for)

A, B, C = "LATE-1", "LATE-2", "LATE-3"
CHAIN, TCP = "mat_late", 5005
UNIT = {A: 1, B: 2, C: 3, "BANG-1": 1, "BANG-2": 2}
LOAD = 4.0e6                          # ohm, every unit of sim.yaml's mat_late and mat_bang
VOLTS = {A: 4000.0, B: 12000.0, C: 8000.0, "BANG-1": 4000.0, "BANG-2": 12000.0}
LATE_MS = 300                         # the late reply: after timeout (150) and wait (50)
MONITORS = ["voltage:read", "current:read"]
READS = MONITORS + ["status:read", "read_output_status", "voltage:get", "current:get"]
# A unit's own periodic reads (their SCAN in the database), paused while a test orders the line
PERIODIC = {"_poll:tick": ".1 second", "status:read": "1 second", "voltage:get": "5 second",
            "read_output_status": "5 second", "_limit:apply": "5 second"}
TIMEOUT, CALC = 10, 12                # menuAlarmStat
ALARM = {0: "", 1: " MINOR", 2: " MAJOR", 3: " INVALID"}
STAT = {0: "", 10: " TIMEOUT", 12: " CALC", 17: " UDF"}


@pytest.fixture(autouse=True)
def after_grace():
    """The supplies switch only after the GRACE period of the database (also when this file runs
    alone, right after the IOC start)."""
    wait_for(lambda: get("DEVTEST:heartbeat") >= GRACE + 2, 30, "IOC past GRACE")


# --- values: whose is it ------------------------------------------------------------------------

def expected(d, rec):
    """The value the record of supply d shows in the tests' state (on at VOLTS[d]), or None."""
    if rec in ("voltage:read", "voltage:get", "voltage:setpoint"):
        return VOLTS[d]
    if rec == "current:read":
        return VOLTS[d] / LOAD * 1e3      # mA
    return None


TOLERANCE = {"voltage:read": 400.0, "voltage:get": 2.0, "current:read": 0.1}


def whose(rec, value, supplies):
    """The supply among `supplies` whose value this is, "?" for none, None if not a value of its
    own (states)."""
    if rec not in TOLERANCE:
        return None
    for d in supplies:
        if abs(expected(d, rec) - value) <= TOLERANCE[rec]:
            return d
    return "?"


# --- the line and the logs ----------------------------------------------------------------------

def _posix(stamp, fmt):
    return datetime.datetime.strptime(stamp, fmt).replace(tzinfo=datetime.timezone.utc).timestamp()


def ioc_log_mark():
    with open(os.path.join(BUILD, "ioc.log")) as f:
        return len(f.readlines())


def ioc_log_since(mark):
    with open(os.path.join(BUILD, "ioc.log")) as f:
        return [l.rstrip("\n") for l in f.readlines()[mark:]]


STREAM = re.compile(r"^(?:\d{4}/\d\d/\d\d \S+ )*(\d{4}/\d\d/\d\d \S+) (\S+) (\S+): (.*)$")


def stream_messages(lines, port):
    """(time, record, text) of StreamDevice's messages of a port."""
    out = []
    for l in lines:
        m = STREAM.match(l)
        if m and m.group(2) == port:
            out.append((_posix(m.group(1), "%Y/%m/%d %H:%M:%S.%f"), m.group(3), m.group(4)))
    return out


def trace(lines, tcp):
    """(time, "write" or "read", text) of the asyn trace of a line (all units), in order."""
    head = re.compile(r"^(\S+ \S+) sim:%d (write|read) \d+$" % tcp)
    out = []
    for a, b in zip(lines, lines[1:]):
        m = head.match(a)
        if m:
            out.append((_posix(m.group(1), "%Y/%m/%d %H:%M:%S.%f"), m.group(2),
                        b[:-2] if b.endswith("\\r") else b))
    return out


def sim_lines(mark, chain):
    """(time, text) of the simulator's log of a chain since a mark."""
    out = []
    for l in sim_log_since(mark, r"mist2sim\.%s " % chain):
        m = re.match(r"^(\S+ \S+) mist2sim\.\S+ \w+ (.*)$", l)
        if m:
            out.append((_posix(m.group(1), "%Y-%m-%d %H:%M:%S,%f"), m.group(2)))
    return out


class Watch:
    """While a test runs: the records of the supplies (every processing of the monitors, MDEL -1
    for the time; the other records on change), the asyn trace of the line, the IOC and the
    simulator log. Use as a context manager; the results are read after it."""

    def __init__(self, supplies, chain=CHAIN, tcp=TCP, reads=READS, trace_on=True):
        self.supplies, self.chain, self.tcp, self.reads = list(supplies), chain, tcp, reads
        self.asyn = "DEVTEST:asyn:" + chain if trace_on else None
        self.events = []                  # (time, supply, record, value, severity, status)
        self.marks = []                   # (time, text) of the test
        self.seen = set()

    def __enter__(self):
        self.ioc_mark = ioc_log_mark()
        self.sim_mark = sim_log_mark()
        for d in self.supplies:
            for r in MONITORS:
                put("%s:%s.MDEL" % (d, r), -1)
        if self.asyn:
            put(self.asyn + ".TIOM", 2)          # escaped text
            put(self.asyn + ".TMSK", 9)          # errors and the driver's I/O
        self.pvs = []
        for d in self.supplies:
            for r in self.reads:
                pv = epics.PV("%s:%s" % (d, r), form="time",
                              callback=lambda d=d, r=r, **kw: self._event(d, r, **kw))
                self.pvs.append(pv)
        for pv in self.pvs:
            assert pv.wait_for_connection(5), pv.pvname
        time.sleep(0.3)
        self.t0 = time.time()
        return self

    def _event(self, d, r, pvname=None, value=None, timestamp=None, severity=None, status=None,
               **kw):
        if pvname not in self.seen:              # the value at the connection
            self.seen.add(pvname)
            return
        self.events.append((timestamp, d, r, value, severity, status))

    def mark(self, text, t=None):
        self.marks.append((time.time() if t is None else t, "test: " + text))

    def __exit__(self, *exc):
        for pv in self.pvs:
            pv.clear_callbacks()
            pv.disconnect()
        if self.asyn:
            put(self.asyn + ".TMSK", 1)
            put(self.asyn + ".TIOM", 0)
        for d in self.supplies:
            for r in MONITORS:
                put("%s:%s.MDEL" % (d, r), 0)
        time.sleep(1.0)                          # the harness writes the logs with a delay
        lines = ioc_log_since(self.ioc_mark)
        self.messages = stream_messages(lines, self.chain)
        self.line = trace(lines, self.tcp) if self.asyn else []
        self.sim = sim_lines(self.sim_mark, self.chain)

    # --- what happened

    def no_reply(self, t0, t1):
        """The requests StreamDevice found no reply to in [t0, t1]: [(time, record, request)]."""
        out = []
        for t, rec, text in self.messages:
            m = re.match(r'No reply within \d+ ms to "(.*?)(<0d>)?"$', text)
            if m and t0 <= t <= t1:
                out.append((t, rec, m.group(1)))
        return out

    def alarms(self, stat, t0=0.0, supplies=None):
        """Events of the watched records with alarm status `stat` (TIMEOUT, CALC) after t0."""
        return [e for e in self.events if e[5] == stat and e[0] >= t0
                and (supplies is None or e[1] in supplies)]

    def foreign(self, t0=0.0, t1=1e99, among=None):
        """Valid values a record took that are another supply's (or nobody's: "?")."""
        among = among or self.supplies
        out = []
        for t, d, r, v, s, st in self.events:
            if t0 <= t <= t1 and s < 3:
                w = whose(r, v, among)
                if w is not None and w != d:
                    out.append((t, d, r, v, w))
        return out

    def shown_for(self, event):
        """Seconds the record showed the value of `event` (until its next event)."""
        t, d, r = event[:3]
        later = [e[0] for e in self.events if e[1] == d and e[2] == r and e[0] > t]
        return (min(later) - t) if later else None

    def mismatch_lines(self, n=12):
        return ["  %s %s: %s" % (datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-3],
                                 r, x) for t, r, x in self.messages
                if "No reply" in x or "got" in x or "Input" in x or "match" in x][-n:]

    def timeline(self, title, t0, t1=1e99, records=True, line=True):
        rows = []
        if line:
            rows += [(t, ("IOC -> " if k == "write" else "    <- ") + x) for t, k, x in self.line]
        rows += [(t, "stream: %s: %s" % (r, x)) for t, r, x in self.messages]
        rows += [(t, "simulator: " + x) for t, x in self.sim]
        rows += list(self.marks)
        if records:
            for t, d, r, v, s, st in self.events:
                w = whose(r, v, self.supplies)
                tag = "" if s >= 3 or w in (None, d) else "   <<< %s'S VALUE" % w
                rows.append((t, "%s:%s = %s%s%s%s" % (d, r, _fmt(r, v), ALARM.get(s, s),
                                                    STAT.get(st, " stat %s" % st), tag)))
        rows = sorted((r for r in rows if t0 - 0.2 <= r[0] <= t1), key=lambda r: r[0])
        text = "\n%s\n" % title + "\n".join("  %+8.3f s  %s" % (t - t0, x) for t, x in rows)
        print(text)


def _fmt(r, v):
    if r == "current:read" or r == "current:get":
        return "%.3f" % v
    if r.startswith("voltage"):
        return "%.0f" % v
    return "%s" % v


# --- the conditions of a test -------------------------------------------------------------------

@contextlib.contextmanager
def paused(*supplies):
    """The supplies' own periodic reads paused (SCAN Passive), restored afterwards."""
    scans = {(d, r): epics.caget("%s:%s.SCAN" % (d, r), as_string=True, timeout=3,
                                 use_monitor=False) for d in supplies for r in PERIODIC}
    assert None not in scans.values(), scans
    try:
        for d, r in scans:
            put("%s:%s.SCAN" % (d, r), "Passive")
        time.sleep(0.5)                          # a read under way ends
        yield
    finally:
        for (d, r), scan in scans.items():
            put("%s:%s.SCAN" % (d, r), scan)


@contextlib.contextmanager
def polled(d):
    """A supply loaded with its scans Passive (LATE-3) polled as the others, for the time."""
    scans = {r: epics.caget("%s:%s.SCAN" % (d, r), as_string=True, timeout=3, use_monitor=False)
             for r in PERIODIC}
    try:
        for r, scan in PERIODIC.items():
            put("%s:%s.SCAN" % (d, r), scan)
        yield
    finally:
        for r, scan in scans.items():
            put("%s:%s.SCAN" % (d, r), scan)


def late_once(d, window=0.2, chain=CHAIN, mode="slow"):
    """The next reply of unit d that the simulator processes within `window` s comes LATE_MS
    late (mode slow), or its second reply after now (mode slow_second: the reply to the query
    of a protocol with a status check, whose first reply is the status). Returns the time the
    fault was set."""
    t = time.time()
    with control(chain) as c:
        c.fault(mode, unit=UNIT[d], ms=LATE_MS, duration=window)
    return t


def on_at(supplies, volts=VOLTS):
    """The supplies on at their voltages (limit 7.5 mA: voltage mode), remote, the output
    settled. A supply that is not polled is checked in the simulator. First the line is made idle
    for a moment (the supplies' periodic reads paused): a stray then arrives on an idle line and is
    dropped, so that a line left out of step by a test before (without R1) starts in step."""
    polled_here = [d for d in supplies if d != C]
    with paused(*polled_here):
        pass
    for d in supplies:
        put(d + ":current:limit", 7.5)
        put(d + ":voltage:setpoint", volts[d])
        put(d + ":SetToggleOutput", 1)
    for d in supplies:
        wait_for(lambda: sim_signal(d, "output") == 1
                 and abs(sim_signal(d, "vout") - volts[d]) < 20, 8,
                 "%s on at %g V" % (d, volts[d]))


def settled(supplies, timeout=8):
    """Every watched record of the supplies valid and showing its own value (the line in step)."""
    def ok():
        for d in supplies:
            for r in READS:
                if sevr("%s:%s" % (d, r)) != 0:
                    return False
                e = expected(d, r)
                if e is not None and abs(get("%s:%s" % (d, r)) - e) > TOLERANCE[r]:
                    return False
        return True
    wait_for(ok, timeout, lambda: "the line is not in step: %s" % {
        "%s:%s" % (d, r): (get("%s:%s" % (d, r)), sevr("%s:%s" % (d, r)))
        for d in supplies for r in READS})


def one_late_reply(w, d, t0, t1):
    """Exactly one request found no reply in time, and it was one of unit d. Returns it."""
    late = w.no_reply(t0, t1)
    assert len(late) == 1 and late[0][2].startswith("#%d " % UNIT[d]), \
        "not exactly one late reply of %s: %s" % (d, late)
    return late[0]


def taker(w, t_late):
    """The request in progress when the late reply arrived, and what it read: the first read
    after StreamDevice gave up on the late request (t_late, the time of its "No reply" message)
    is the late reply, and the last write before that read is the request that read it."""
    last = None
    for t, k, x in w.line:
        if k == "write":
            last = x
        elif t > t_late and last is not None:
            return last, x
    return None, None


def in_step_after_first_mismatch(w, t_fault, among, settle=None):
    """The line is in step after the first mismatch: no other mismatch or timeout after it, and
    no record took another supply's value after it. Returns (first mismatch time, foreign values
    before it)."""
    calc = w.alarms(CALC, t_fault)
    if not calc:                              # the stray arrived on an idle line: discarded
        first = None
        after = w.foreign(t_fault, among=among)
        assert after == [], "foreign values without a mismatch: %s" % after
        return None, []
    first = min(e[0] for e in calc)
    more = [e for e in w.alarms(CALC, first + 1e-6) + w.alarms(TIMEOUT, first + 1e-6)]
    foreign_after = w.foreign(first + 1e-6, among=among)
    assert more == [] and foreign_after == [], (
        "the line is not in step after the first mismatch (%.3f s after the fault): further "
        "alarms %s, foreign values %s. A stall of the machine also gives this: the line's last "
        "messages:\n%s" % (first - t_fault, [(round(e[0] - t_fault, 3), e[1], e[2], e[5]) for e in more][:10],
                           [(round(e[0] - t_fault, 3),) + e[1:] for e in foreign_after][:10],
                           "\n".join(w.mismatch_lines())))
    return first, w.foreign(t_fault, first, among=among)


# --- 1. the fault as it is ----------------------------------------------------------------------

def test_1_one_late_reply_on_a_line_of_two_polled_supplies(capsys):
    """LATE-1 at 4 kV and LATE-2 at 12 kV, both on and polled. One reply of LATE-1 300 ms late.
    The timeline shows what each monitor record showed for 10 s. Without R1 the requests and
    replies stay out of step and one supply shows the other's values without alarm; with R1 the
    line is in step after the first mismatch."""
    on_at([A, B])
    settled([A, B])
    with Watch([A, B]) as w:
        time.sleep(1.0)
        t_fault = late_once(A, window=0.25)
        w.mark("fault slow %d ms on unit 1 for 250 ms" % LATE_MS, t_fault)
        time.sleep(9.0)
    with capsys.disabled():
        w.timeline("Test 1: one reply of LATE-1 late, LATE-1 at 4 kV, LATE-2 at 12 kV, both "
                   "polled; the monitors for 10 s:", t_fault, line=False,
                   records=True)
        w.timeline("  the line around the late reply:", t_fault, t_fault + 1.0, records=False)
        late = w.no_reply(t_fault, t_fault + 9)
        foreign = w.foreign(t_fault)
        print("  late: %s; values of the other supply accepted without alarm: %d, the last %.2f s "
              "after the fault; CALC alarms: %d"
              % ([x[2] for x in late], len(foreign),
                 (foreign[-1][0] - t_fault) if foreign else 0, len(w.alarms(CALC, t_fault))))
    one_late_reply(w, A, t_fault, t_fault + 9)
    in_step_after_first_mismatch(w, t_fault, [A, B])
    settled([A, B])


# --- 2. back in step: every phase, every kind -----------------------------------------------------

PHASES = 12


def _one_run(supplies, late, window, kick=None, title=None, capsys=None, watch=3.0, mode="slow"):
    """One late reply of `late`, watched for `watch` s. kick(): processes the record whose
    request is made late (for a unit that is not polled). Returns a summary dict."""
    with Watch(supplies) as w:
        time.sleep(random.uniform(0.3, 0.5))
        t_fault = late_once(late, window=window, mode=mode)
        if kick:
            kick()
        w.mark("fault slow %d ms on unit %d for %d ms" % (LATE_MS, UNIT[late], window * 1000),
               t_fault)
        time.sleep(watch)
    if title and capsys:
        with capsys.disabled():
            w.timeline(title, t_fault, t_fault + 1.0)
    if not w.no_reply(t_fault, t_fault + watch):
        return None       # no request of the unit was processed within the window: nothing late
    t_late, rec, request = one_late_reply(w, late, t_fault, t_fault + watch)
    took, stray = taker(w, t_late)
    first, before = in_step_after_first_mismatch(w, t_fault, supplies)
    return dict(request=request, taker=took, stray=stray, mismatch=first and first - t_fault,
                foreign=[(e[1], e[2], round(e[3], 3), e[4], w.shown_for(e)) for e in before],
                calc=len(w.alarms(CALC, t_fault)))


def _phases(supplies, title, capsys):
    """PHASES runs with one reply of LATE-1 late at a random moment. A run in which no request
    of LATE-1 reached the simulator within the window (250 ms) made nothing late; it is repeated,
    at most 3 times in all, and counted in the report."""
    runs, missed = [], 0
    while len(runs) < PHASES:
        run = _one_run(supplies, A, 0.25, title=title if not runs else None, capsys=capsys)
        settled(supplies)
        if run is None:
            missed += 1
            assert missed <= 3, "no request of LATE-1 within the window 3 times"
            continue
        runs.append(run)
    with capsys.disabled():
        print("\n  %d runs repeated: nothing was late in them" % missed)
    return runs


def _report(title, runs, capsys):
    with capsys.disabled():
        print("\n" + title)
        for i, r in enumerate(runs, 1):
            print("  %2d late %-8s taken by %-10s (%-10s) first mismatch %s, CALC alarms %d, "
                  "foreign values before it: %s"
                  % (i, r["request"], r["taker"], r["stray"],
                     "%.3f s" % r["mismatch"] if r["mismatch"] is not None else "none",
                     r["calc"], ", ".join("%s:%s = %s (%s's) shown %.3f s" % (d, rec, v, who, s or 0)
                                         for d, rec, v, who, s in r["foreign"]) or "none"))


def test_2_back_in_step_at_every_phase_two_polled_supplies(capsys):
    """R1 and R6a: LATE-1 and LATE-2 on and polled, one reply of LATE-1 late at a random moment,
    PHASES times. A 100 ms tick holds about four transactions of a full line, so the late request
    and the one that takes its reply are one of a few pairs; 12 random moments meet each slot of
    the cycle with a probability of 1 - (3/4)^12 = 97 %. Each run: in step after the first
    mismatch, no record takes another supply's value after it; the values taken before it are
    reported."""
    on_at([A, B])
    settled([A, B])
    runs = _phases([A, B], "Test 2, two polled supplies, run 1:", capsys)
    _report("Test 2, two polled supplies (LATE-1 4 kV, LATE-2 12 kV), one reply of LATE-1 late "
            "at %d random moments:" % PHASES, runs, capsys)


def test_2_back_in_step_at_every_phase_three_polled_supplies(capsys):
    """R1 and R6a: as above with LATE-3 (8 kV) polled as well, so that three supplies take turns."""
    with polled(C):
        on_at([A, B, C])
        settled([A, B, C])
        runs = _phases([A, B, C], "Test 2, three polled supplies, run 1:", capsys)
    _report("Test 2, three polled supplies (LATE-1 4 kV, LATE-2 12 kV, LATE-3 8 kV), one reply of "
            "LATE-1 late at %d random moments:" % PHASES, runs, capsys)


# kind of the late reply: (LATE-3's record read, the late request, fault mode). The state reads
# begin with the status check (R2): their first reply is the status, so the reply to SW?, CH0?
# or CH1? is the second (slow_second), and a late status check is a case of its own.
KINDS = {"MN1": ("voltage:read", "MN1", "slow"), "MN2": ("current:read", "MN2", "slow"),
         "STS": ("status:read", "STS", "slow"),
         "STS check of SW?": ("read_output_status", "STS", "slow"),
         "SW?": ("read_output_status", "SW?", "slow_second"),
         "CH0?": ("voltage:get", "CH0?", "slow_second"),
         "CH1?": ("current:get", "CH1?", "slow_second")}


@pytest.mark.parametrize("kind", list(KINDS))
def test_2_back_in_step_after_a_late_reply_of_each_kind(kind, capsys):
    """R1: LATE-1 and LATE-2 on and polled (a full line); LATE-3 (not polled, on at 8 kV) is read
    once by hand with its reply late: MN1 (voltage:read, whose forward link reads MN2 after it),
    MN2, STS (status:read), the status check of read_output_status, and the query after the status
    check: SW? (whose forward link reads CH1? after it), CH0?, CH1? (fault slow_second). Three runs
    per kind at random moments. Each: exactly one late reply, in step after the first mismatch."""
    on_at([A, B, C])
    settled([A, B])
    rec, request, mode = KINDS[kind]
    runs = []
    missed = 0
    while len(runs) < 3:
        # slow: the window ends before LATE-3's next request can be processed (the late reply
        # holds the simulated line 300 ms). If the kicked request waited longer than the window
        # for the full line, nothing was late: that run is repeated (counted, at most 3 times).
        run = _one_run([A, B, C], C, 0.28 if mode == "slow" else 1.0,
                       kick=lambda: epics.caput("%s:%s.PROC" % (C, rec), 1),
                       title="Test 2, a late %s of LATE-3, run 1:" % kind if not runs else None,
                       capsys=capsys, mode=mode)
        if run is None:
            missed += 1
            assert missed <= 3, "the request of LATE-3 reached the line after the window 3 times"
            settled([A, B])
            continue
        runs.append(run)
        assert runs[-1]["request"] == "#3 %s" % request, runs[-1]
        settled([A, B])
    _report("Test 2, a late %s of LATE-3 (8 kV, not polled) on the line of LATE-1 (4 kV) and "
            "LATE-2 (12 kV), polled (%d runs repeated: nothing late):" % (kind, missed), runs, capsys)


# --- 3. R2: a state or setting read never takes a neighbour's reply --------------------------------

def _states(a_on, b_on):
    put(A + ":SetToggleOutput", int(a_on))
    put(B + ":SetToggleOutput", int(b_on))
    for d, on in ((A, a_on), (B, b_on)):
        wait_for(lambda: sim_signal(d, "output") == int(on), 5, "%s output %d" % (d, on))
        put(d + ":read_output_status.PROC", 1)       # also when nothing was switched
        wait_for(lambda: get(d + ":read_output_status") == int(on) and
                 sevr(d + ":read_output_status") == 0, 7, "%s: SW? read back %d" % (d, on))


SETTINGS = {A: (4000.0, 2.0), B: (12000.0, 5.0)}      # voltage V, current limit mA


def _settings():
    for d, (v, i) in SETTINGS.items():
        put(d + ":voltage:setpoint", v)
        put(d + ":current:limit", i)
    for d, (v, i) in SETTINGS.items():
        wait_for(lambda: abs(get(d + ":voltage:get") - v) < 1 and abs(get(d + ":current:get") - i) < 1e-3,
                 5, "%s: settings read back" % d)


def status_checked(protocol):
    """True if this protocol of the file the IOC loads (the repository's EPICS/Db, mounted at
    /repo in this container) begins with the status check (R2). Test 3 then makes the reply to
    LATE-1's query late, the second of its protocol (fault slow_second), not the status."""
    text = open("/repo/EPICS/Db/matsusada_co_ctrl.proto").read()
    body = re.search(r"\n%s\s*\{([^}]*)\}" % protocol, text).group(1)
    return '"#\\$1 STS"' in body


PROTOCOL_OF = {"read_output_status": "get_output_status", "voltage:get": "get_voltage",
               "current:get": "get_current"}


@contextlib.contextmanager
def local(d):
    """The supply under front-panel control: it answers queries and ignores commands."""
    with control(CHAIN) as c:
        c.set("%d.remote" % UNIT[d], 0)
    try:
        yield
    finally:
        with control(CHAIN) as c:
            c.set("%d.remote" % UNIT[d], 1)
            c.release("%d.remote" % UNIT[d])
        put(d + ":_out:remote.PROC", 1)              # REN: remote control again


# case: (records of A read with the late reply, what B does next, B's record that must not
#        show A's value, B's value of its own, A's value, B in local control)
CASES = {
    "get_output_status": ("read_output_status", "read_output_status", 0, 1),
    "get_voltage": ("voltage:get", "voltage:get", 12000.0, 4000.0),
    "get_current": ("current:get", "current:get", 5.0, 2.0),
    "toggle_output": ("read_output_status", "ToggleOutput", None, None),
    "set_voltage": ("voltage:get", "voltage:setpoint", None, None),
    "set_current": ("current:get", "current:limit", None, None),
}


@pytest.mark.parametrize("case", list(CASES))
def test_3_a_state_read_does_not_take_a_neighbours_reply(case, capsys):
    """R2, each protocol: LATE-1 on at 4 kV, limit 2 mA; LATE-2 off at 12 kV, limit 5 mA. The
    periodic reads of both paused, so that the line carries only what the test sends: a read of
    LATE-1 whose reply is late, then at once LATE-2's request of the same kind. LATE-2's record
    must never show LATE-1's value: it is INVALID or shows its own.
      get_output_status, get_voltage, get_current: LATE-2's read.
      toggle_output: LATE-2 under front-panel control (it ignores the commands) is switched on by a
        direct write of ToggleOutput; LATE-1's late reply is SW1. The read-back must not confirm a
        switching the supply did not execute.
      set_voltage, set_current: LATE-2 under front-panel control is given LATE-1's setting; LATE-1's
        late reply is that setting. The read-back must not confirm a set the supply did not
        execute."""
    a_rec, b_rec, own, theirs = CASES[case]
    with contextlib.ExitStack() as stack:
        # Paused first: an idle line is in step also when a test before left it out of step
        # (without R1). The sets and the switching read their settings back by forward links.
        stack.enter_context(paused(A, B))
        _settings()
        _states(True, False)
        if own is None:
            stack.enter_context(local(B))
        w = stack.enter_context(Watch([A, B], reads=READS + ["ToggleOutput", "voltage:setpoint",
                                                             "current:limit"]))
        b_before = {k: sim_signal(B, k) for k in ("sw", "vset", "iset")}
        mode = "slow_second" if status_checked(PROTOCOL_OF[a_rec]) else "slow"
        t_fault = late_once(A, window=1.0 if mode == "slow_second" else 0.2, mode=mode)
        epics.caput("%s:%s.PROC" % (A, a_rec), 1)
        # LATE-1's request on the line first: the set records have PRIO HIGH and would overtake
        # it. With the status check its query goes out about 25 ms after its STS.
        time.sleep(0.05 if mode == "slow" else 0.08)
        if case == "toggle_output":
            epics.caput(B + ":ToggleOutput", 1)
        elif case == "set_voltage":
            epics.caput(B + ":voltage:setpoint", SETTINGS[A][0])
        elif case == "set_current":
            epics.caput(B + ":current:limit", SETTINGS[A][1])
        else:
            epics.caput("%s:%s.PROC" % (B, b_rec), 1)
        w.mark("fault %s on unit 1, %s:%s processed, then LATE-2's %s" % (mode, A, a_rec, b_rec),
               t_fault)
        time.sleep(2.0)
        b_after = {k: sim_signal(B, k) for k in ("sw", "vset", "iset")}
        final = (get("%s:%s" % (B, b_rec)), sevr("%s:%s" % (B, b_rec)))
    with capsys.disabled():
        w.timeline("Test 3, %s: LATE-1's %s late, then LATE-2's %s:" % (case, a_rec, b_rec), t_fault)
        print("  LATE-2's %s at the end: %s, severity %d; LATE-2 in the simulator before %s, after %s"
              % (b_rec, final[0], final[1], b_before, b_after))
    one_late_reply(w, A, t_fault, t_fault + 2)
    b_events = [e for e in w.events if e[1] == B and e[2] == b_rec]
    if own is not None:
        wrong = [e for e in b_events if e[4] < 3 and abs(e[3] - theirs) < abs(e[3] - own)]
        assert wrong == [], "LATE-2's %s showed LATE-1's value: %s" % (b_rec, wrong)
        assert final[1] == 3 or abs(final[0] - own) < 1e-3 * max(1, abs(own)), final
    else:
        assert b_after == b_before, "precondition: LATE-2 did not execute anything"
        confirmed = [e for e in b_events if e[4] < 3]
        assert confirmed == [] and final[1] == 3, (
            "LATE-2's %s confirmed by LATE-1's reply although the supply did not execute it: %s"
            % (b_rec, confirmed or final))
    # back: LATE-2 as it was (remote again after local())
    if case == "toggle_output":
        put(B + ":ToggleOutput", 0)
    elif case == "set_voltage":
        put(B + ":voltage:setpoint", SETTINGS[B][0])
    elif case == "set_current":
        put(B + ":current:limit", SETTINGS[B][1])
    wait_for(lambda: sevr("%s:%s" % (B, b_rec)) == 0, 8, "LATE-2's %s valid again" % b_rec)


# --- 4. the first contact ---------------------------------------------------------------------------

HOLD = 12.0      # s the late replies last after the new IOC connected: probes, echoes, a 5 s scan


@pytest.mark.parametrize("a_on", [True, False], ids=["LATE-1 on, LATE-2 off", "LATE-1 off, LATE-2 on"])
def test_4_first_contact_beside_a_supply_whose_replies_are_late(a_on, capsys):
    """An IOC start with LATE-1 and LATE-2 in opposite states and at different voltages (4 and
    12 kV), every reply of LATE-1 late from before the restart until HOLD s after the new IOC
    connected to the line (the simulator's log), then normal. Each supply takes over its own
    state and setting: the request (SetToggleOutput), ToggleOutput, the gate (OutputIntlk after
    GRACE, and the simulator's output, which the gate would switch), the voltage set point.
    Nothing here depends on when this test's Channel Access client finds the restarted IOC:
    the fault is timed by the simulator's log, and the take-over is read when the IOC is back."""
    state = {A: a_on, B: not a_on}
    for d in (A, B):
        put(d + ":current:limit", 7.5)
        put(d + ":voltage:setpoint", VOLTS[d])
        put(d + ":SetToggleOutput", int(state[d]))
    for d in (A, B):
        wait_for(lambda: sim_signal(d, "output") == int(state[d]) and
                 abs(sim_signal(d, "vset") - VOLTS[d]) < 1, 8, "%s prepared" % d)
    time.sleep(6)                                    # autosave: the limits saved
    sim_mark = sim_log_mark()
    ioc_mark = ioc_log_mark()
    import mat
    mat._restarts[0] += 1
    with control(CHAIN) as c:
        c.fault("slow", unit=UNIT[A], ms=LATE_MS)
        t_fault = time.time()
        with open(os.path.join(BUILD, "ioc-restart"), "w") as f:
            f.write("%d\n" % mat._restarts[0])
        try:
            wait_for(lambda: any("connected" in x and "disconnected" not in x
                                 for _, x in sim_lines(sim_mark, CHAIN)),
                     60, "the new IOC connects to mat_late")
            time.sleep(HOLD)
        finally:
            c.clear("slow", unit=UNIT[A])
            t_clear = time.time()
    hb = epics.PV("DEVTEST:heartbeat")
    wait_for(lambda: hb.connected and hb.get(timeout=1) is not None, 60, "the IOC is back")
    waited = {}
    for d in (A, B):
        # Without R1 the line can stay out of step after the fault: the take-over of a supply
        # may then never come. Wait for each, but print the timeline before any assertion.
        try:
            wait_for(lambda: get(d + ":_init:probe.DISA") == 1 and
                     get(d + ":voltage:setpoint.SIMM") == 0 and get(d + ":OutputIntlk.DISA") == 0,
                     40, "%s: first contact, set point and gate" % d)
            waited[d] = True
        except BaseException:                    # pytest.fail
            waited[d] = False
    time.sleep(3.0)                              # the gate has acted, the simulator log
    got = {}
    for d in (A, B):
        got[d] = {r: epics.caget("%s:%s" % (d, r), use_monitor=False, timeout=3)
                  for r in ("SetToggleOutput", "ToggleOutput", "OutputIntlk", "voltage:setpoint",
                            "_init:probe.DISA", "voltage:setpoint.SIMM")}
        got[d]["output"] = sim_signal(d, "output")
        got[d]["vset"] = sim_signal(d, "vset")
    stamps = {}
    for d in (A, B):
        for r in ("SetToggleOutput", "voltage:setpoint"):
            pv = epics.PV("%s:%s" % (d, r), form="time")
            pv.get(timeout=3, use_monitor=False)
            stamps["%s:%s" % (d, r)] = pv.timestamp
            pv.disconnect()
    lines = ioc_log_since(ioc_mark)
    messages = stream_messages(lines, CHAIN)
    sim = sim_lines(sim_mark, CHAIN)
    with capsys.disabled():
        rows = [(t, "simulator: " + x) for t, x in sim]
        rows += [(t, "stream: %s: %s" % (r, x)) for t, r, x in messages]
        rows += [(t, "record time stamp: %s = %s" % (k, got[k.split(":")[0]][k.split(":", 1)[1]]))
                 for k, t in stamps.items() if t]
        rows += [(t_fault, "test: fault slow on unit 1, IOC restart requested"),
                 (t_clear, "test: fault cleared")]
        rows.sort(key=lambda r: r[0])
        print("\nTest 4, IOC start with LATE-1 %s (4 kV) and LATE-2 %s (12 kV), LATE-1's replies "
              "late until %.0f s after the new IOC connected (first 150 lines):" % (
                  "on" if a_on else "off", "off" if a_on else "on", HOLD))
        print("\n".join("  %+8.3f s  %s" % (t - t_fault, x) for t, x in rows[:150]))
        for d in (A, B):
            print("  %s: state %d; first contact made %s; took over: request %s, ToggleOutput %s, "
                  "gate %s, set point %s (SIMM %s); simulator output %d, vset %.0f"
                  % (d, state[d], waited[d], got[d]["SetToggleOutput"], got[d]["ToggleOutput"],
                     got[d]["OutputIntlk"], got[d]["voltage:setpoint"],
                     got[d]["voltage:setpoint.SIMM"], got[d]["output"], got[d]["vset"]))
    for d in (B, A):
        g = got[d]
        assert (g["SetToggleOutput"], g["ToggleOutput"], g["OutputIntlk"]) == (state[d],) * 3, (d, g)
        assert g["voltage:setpoint"] is not None and abs(g["voltage:setpoint"] - VOLTS[d]) < 1, (d, g)
        assert g["output"] == int(state[d]) and abs(g["vset"] - VOLTS[d]) < 1, (d, g)
        assert waited[d], "%s: no first contact within 40 s after the IOC was back" % d
    commands = [x for _, x in sim if re.match(r"unit [12]: (SW|CH0|RST)", x)]
    assert commands == [], "a switching or set command went out: %s" % commands


# --- 5. a line nobody asked for ---------------------------------------------------------------------

def test_5_a_line_nobody_asked_for(capsys):
    """BANG-1 (4 kV) and BANG-2 (12 kV) on and polled, on a line whose units send "!" when their
    output goes off (manual 7-2). BANG-1 cuts off (fault trip): its "!" is read by whatever
    request is on the line. One mismatch, then in step: BANG-2 shows its own values only."""
    supplies = ["BANG-1", "BANG-2"]
    on_at(supplies)
    try:
        with Watch(supplies, chain="mat_bang", tcp=5006) as w:
            time.sleep(1.0)
            t_fault = time.time()
            with control("mat_bang") as c:
                c.fault("trip", unit=1)
            w.mark("fault trip on unit 1: it sends \"!\"", t_fault)
            time.sleep(4.0)
        with capsys.disabled():
            w.timeline("Test 5, BANG-1 cuts off and sends \"!\":", t_fault, t_fault + 1.0)
        bangs = sum(x.count("!") for t, k, x in w.line if k == "read")
        assert bangs == 1, "precondition: the IOC read one \"!\", not %d" % bangs
        calc = w.alarms(CALC, t_fault)
        assert len(calc) <= 1, ("more than one mismatch after the \"!\": %s\n%s"
                                % ([(round(e[0] - t_fault, 3), e[1], e[2]) for e in calc][:10],
                                   "\n".join(w.mismatch_lines())))
        wrong = [e for e in w.events if e[1] == "BANG-2" and e[0] > t_fault and e[4] < 3
                 and whose(e[2], e[3], ["BANG-2"]) == "?"]
        assert wrong == [], "BANG-2 showed values not its own: %s" % wrong[:10]
    finally:
        with control("mat_bang") as c:
            c.clear("trip")
        for d in supplies:
            put(d + ":SetToggleOutput", 0)               # REN, RST (ends the cut-off), SW0
        for d in supplies:
            wait_for(lambda: sim_signal(d, "output") == 0 and sim_signal(d, "cutoff") == 0, 5,
                     "%s off" % d)


# --- R6: reported, not changed ------------------------------------------------------------------------

def _rates(supplies, seconds=10.0):
    """Monitor updates per second of each supply (Channel Access, MDEL -1), and the simulator's
    count of requests per unit and the line's busy time."""
    counts = {(d, r): 0 for d in supplies for r in MONITORS}
    pvs = []
    for d in supplies:
        for r in MONITORS:
            put("%s:%s.MDEL" % (d, r), -1)
            pv = epics.PV("%s:%s" % (d, r), callback=lambda k=(d, r), **kw:
                          counts.__setitem__(k, counts[k] + 1))
            pv.wait_for_connection(3)
            pvs.append(pv)
    time.sleep(1.0)
    with control(CHAIN) as c:
        for k in counts:
            counts[k] = 0
        c.stats(reset=True)
        time.sleep(seconds)
        stats = c.stats()
        n = dict(counts)
    for pv in pvs:
        pv.clear_callbacks()
        pv.disconnect()
    for d in supplies:
        for r in MONITORS:
            put("%s:%s.MDEL" % (d, r), 0)
    el = stats["elapsed_s"]
    return ({k: v / seconds for k, v in n.items()},
            {u: (x["requests"] / el, x["replies"] / el) for u, x in stats["per_unit"].items()},
            stats["busy_s"] / el)


def test_r6b_update_rates_one_and_two_polled_supplies(capsys):
    """R6b and R4, a report: update rates of the monitors with one and with two polled supplies on
    a line (LATE-1, LATE-2), the simulator's requests and replies per unit and second, and the
    share of time the line is busy. Run once with the protocol file as committed and once with
    a copy whose monitors are checked as in R2 (not committed)."""
    on_at([A, B])
    rows = []
    with paused(B):
        rows.append(("one polled (LATE-1)",) + _rates([A]))
        # R4: what the status checks add. LATE-1's monitors paused as well: the line carries only
        # its status poll (REN, STS every 1 s) and its echo reads (CH0?, SW? and CH1? every 5 s,
        # each with its status check when the protocol file has it), measured over 30 s.
        put(A + ":_poll:tick.SCAN", "Passive")
        try:
            time.sleep(0.5)
            rows.append(("LATE-1 status and echoes only",) + _rates([A], seconds=30.0))
        finally:
            put(A + ":_poll:tick.SCAN", PERIODIC["_poll:tick"])
    rows.append(("two polled (LATE-1, LATE-2)",) + _rates([A, B]))
    with capsys.disabled():
        print("\nR6b/R4: monitor updates per second, simulator requests and replies per second per "
              "unit, line busy (protocol file with the status check: %s)"
              % status_checked("get_voltage"))
        for label, mon, units, busy in rows:
            print("  %-28s %s | %s | line busy %.1f %%" % (
                label, ", ".join("%s %s %.2f/s" % (d, r.split(":")[0], v) for (d, r), v in mon.items()
                             if v > 0),
                ", ".join("unit %s %.2f req %.2f rep" % (u, q, p) for u, (q, p) in sorted(units.items())),
                100 * busy))
        print("  (line busy = the simulator's transmission and turnaround time per second)")


def test_r6c_every_reply_of_a_supply_late(capsys):
    """R6c, a report: every reply of LATE-1 300 ms late for 10 s (the fault left on), LATE-1 and
    LATE-2 on and polled. What LATE-2's records showed: valid own values, valid values of LATE-1,
    INVALID (CALC, TIMEOUT)."""
    on_at([A, B])
    settled([A, B])
    with Watch([A, B], trace_on=False) as w:
        time.sleep(1.0)
        with control(CHAIN) as c:
            c.fault("slow", unit=UNIT[A], ms=LATE_MS)
            t0 = time.time()
            try:
                time.sleep(10.0)
            finally:
                c.clear("slow", unit=UNIT[A])
                t1 = time.time()
        time.sleep(2.0)
    with capsys.disabled():
        print("\nR6c: every reply of LATE-1 late (300 ms) for %.1f s; LATE-2's records in that time:" % (t1 - t0))
        for r in READS:
            ev = [e for e in w.events if e[1] == B and e[2] == r and t0 <= e[0] <= t1]
            own = sum(1 for e in ev if e[4] < 3 and whose(r, e[3], [A, B]) in (B, None))
            theirs = sum(1 for e in ev if e[4] < 3 and whose(r, e[3], [A, B]) == A)
            other = sum(1 for e in ev if e[4] < 3 and whose(r, e[3], [A, B]) == "?")
            inv = sum(1 for e in ev if e[4] >= 3)
            print("  %-20s events %3d: valid own %3d, valid LATE-1's %3d, valid other %3d, INVALID %3d"
                  % (r, len(ev), own, theirs, other, inv))
        ev = [e for e in w.events if e[1] == A and t0 <= e[0] <= t1]
        print("  LATE-1's records: %d events, %d valid" % (len(ev), sum(1 for e in ev if e[4] < 3)))
        last_bad = max([e[0] for e in w.events if e[0] > t1 and e[4] >= 3] or [t1])
        print("  after the fault was cleared: the last INVALID event %.3f s later" % (last_bad - t1))
    settled([A, B])
