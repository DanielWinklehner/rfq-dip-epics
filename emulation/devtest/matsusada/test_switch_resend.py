"""A switching command stored in the busy ToggleOutput is sent when it is free (P47, task T21).

A value written into ToggleOutput while it is busy is stored in VAL and not sent, unless the
writer carries the put flag (then EPICS runs the record again, RPRO). The internal record
_out:resend checks every second: ToggleOutput not busy (PACT 0) and VAL != RVAL (RVAL is what it
last started to send), then it processes ToggleOutput once, and counts.

Such a write cannot be made by a client (a Channel Access put carries the flag). The helper
lost_write.db (this case only, loaded by ioc.cmd for AU-20P7-3 and REK-1) writes from a periodic
scan: step 1 writes a start value into the idle ToggleOutput, step 2, 100 ms later, writes up to
three values into it while it is busy. ToggleOutput is kept busy for about 130 ms after its SW
line by the simulator's fault "slow" (the reply to SW? 100 ms late, within the reply timeout of
150 ms). While a test runs, the unit's own periodic reads are paused (SCAN Passive, restored
afterwards): with the fault they would hold the line for 125 ms each, and the switching would
wait for them, so that step 2 could come before the SW line is formatted (a value written then
is sent by that processing itself, see the comment of _out:resend).

Each test prints its timeline: what the IOC wrote to the unit's line and what the unit replied
(asyn trace of ioc.cmd, records DEVTEST:asyn:<port>), what the simulator executed, and the
events of the records (IOC time stamps), in seconds after the first of them.
Runs after test_permit_enforce.py and test_rates.py (file order).
"""
import contextlib
import datetime
import os
import re
import time

import epics
import pytest

from mat import (BUILD, POLLED, UNPOLLED, control, get, put, restart_ioc, sevr, sim_log_mark,
                 sim_log_since, sim_signal, switch, wait_for)

SUPPLIES = ["AU-20P7-3", "REK-1"]            # one AU unit and one REK unit, with the helper
PORT = {"AU-20P7-3": ("mat_co", 5002), "REK-1": ("REK", 5003)}
CHAIN = {"AU-20P7-3": "mat_co", "REK-1": "rek"}
UNIT = {"AU-20P7-3": 3, "REK-1": 1}

SLOW_MS = 100          # extra delay of every reply of the unit (the reply timeout is 150 ms)
EVALUATION = 1.0       # the scan of _out:resend
SEND = 0.15            # RST, SW and SW? on the line after the evaluation, with margin
SETTLE = 3.0           # s watched for nothing more to be sent (three evaluations)
# The unit's periodic reads (their SCAN in the database), paused while a test runs
PAUSED = ["_poll:tick", "status:read", "voltage:get", "read_output_status", "_limit:apply"]
SWITCHING = re.compile(r"^(REN|RST|SW[01]|CH0 |CH1 |GTL)")   # commands, not queries


def count(d):
    return get(d + ":_out:resend")


def enforced(d):
    return get(d + ":_permit:enforce")


# --- the conditions of a test -------------------------------------------------------------------

@contextlib.contextmanager
def paused(d):
    """The unit's own periodic reads paused (SCAN Passive), restored afterwards."""
    scans = {r: epics.caget("%s:%s.SCAN" % (d, r), as_string=True, timeout=3, use_monitor=False)
             for r in PAUSED}
    assert None not in scans.values(), scans
    try:
        for r in PAUSED:
            put("%s:%s.SCAN" % (d, r), "Passive")
        time.sleep(0.5)                      # a read under way ends
        yield
    finally:
        for r, scan in scans.items():
            put("%s:%s.SCAN" % (d, r), scan)


@contextlib.contextmanager
def fault(d, mode, **args):
    with control(d) as c:
        c.fault(mode, unit=UNIT[d], **args)
        try:
            yield
        finally:
            c.clear(mode, unit=UNIT[d])


@contextlib.contextmanager
def rule_disabled(d):
    put(d + ":_out:resend.DISA", 1)
    try:
        yield
    finally:
        put(d + ":_out:resend.DISA", 0)


# --- the helper (lost_write.db) -----------------------------------------------------------------

def lost_run(d, start, writes, watch):
    """One run of the helper: `start` into the idle ToggleOutput, then `writes` into the busy one.
    Checks that each write was made (the start only into the idle record, the others only while
    it was busy)."""
    h = "DEVTEST:%s:lost:" % d
    values = list(writes) + [-1] * (3 - len(writes))
    watch.helper = {"s": "helper writes %d into the idle ToggleOutput" % start}
    watch.helper.update({"b%d" % i: "helper writes %d into the busy ToggleOutput" % v
                         for i, v in enumerate(values, 1)})
    put(h + "start", start)
    for i, v in enumerate(values, 1):
        put(h + "w%d" % i, v)
    writers = ["s", "b1", "b2", "b3"]
    before = {w: get(h + w + ".L") for w in writers}
    put(h + "go", get(h + "go") + 1)
    time.sleep(0.4)                          # two scans of .1 s, then a margin
    made = {w: get(h + w + ".L") - before[w] for w in writers}
    expected = {w: int(v >= 0) for w, v in zip(writers, [start] + values)}
    assert made == expected, "helper writes made %s, expected %s" % (made, expected)


# --- what happened: the line, the simulator, the records ------------------------------------------

def _ioc_log_mark():
    with open(os.path.join(BUILD, "ioc.log")) as f:
        return len(f.readlines())


def _posix(stamp, fmt):
    return datetime.datetime.strptime(stamp, fmt).replace(tzinfo=datetime.timezone.utc).timestamp()


class Watch:
    """While a test runs: the asyn trace of the unit's line, the simulator's log of the unit and
    monitors of the records. Call collect() at the end."""

    def __init__(self, d):
        self.d = d
        port, self.tcp = PORT[d]
        self.rec = "DEVTEST:asyn:" + port
        h = "DEVTEST:%s:lost:" % d
        self.names = {d + ":ToggleOutput": "ToggleOutput", d + ":ToggleOutput.RVAL": "ToggleOutput.RVAL",
                      d + ":_out:resend": "_out:resend", d + ":SetToggleOutput": "SetToggleOutput",
                      h + "s.L": "s", h + "b1.L": "b1", h + "b2.L": "b2", h + "b3.L": "b3"}
        self.helper = {}
        self.events = []
        self.seen = set()
        self.t0 = time.time()

    def __enter__(self):
        self.ioc_mark = _ioc_log_mark()
        self.sim_mark = sim_log_mark()
        put(self.rec + ".TIOM", 2)           # escaped text
        put(self.rec + ".TMSK", 9)           # errors and the driver's I/O
        self.pvs = [epics.PV(n, form="time", callback=self._event) for n in self.names]
        for pv in self.pvs:
            assert pv.wait_for_connection(3), pv.pvname
        time.sleep(0.2)
        self.t0 = time.time()
        return self

    def _event(self, pvname=None, value=None, timestamp=None, severity=None, **kw):
        if pvname not in self.seen:          # the value at the connection
            self.seen.add(pvname)
            return
        name = self.names[pvname]
        if name in ("s", "b1", "b2", "b3"):  # a writer of the helper counted a write
            self.events.append((timestamp, "record", self.helper.get(name, name)))
            return
        self.events.append((timestamp, "record", "%s = %s%s" % (
            name, value, " (INVALID)" if severity == 3 else
            " (MINOR)" if severity == 1 else " (MAJOR)" if severity == 2 else "")))

    def mark(self, text):
        """An action of the test, at the test's time."""
        self.events.append((time.time(), "test", "test: " + text))

    def __exit__(self, *exc):
        for pv in self.pvs:
            pv.clear_callbacks()
            pv.disconnect()
        put(self.rec + ".TMSK", 1)
        put(self.rec + ".TIOM", 0)

    def line(self):
        """(time, "write" or "read", text) of the unit since the start, in order. A read belongs
        to the unit whose write came before it (the port is held for one protocol at a time)."""
        time.sleep(1.0)                      # the harness writes the logs with a delay
        with open(os.path.join(BUILD, "ioc.log")) as f:
            lines = [l.rstrip("\n") for l in f.readlines()[self.ioc_mark:]]
        head = re.compile(r"^(\S+ \S+) sim:%d (write|read) \d+$" % self.tcp)
        out, mine = [], False
        for a, b in zip(lines, lines[1:]):
            m = head.match(a)
            if not m or not b.endswith("\\r"):
                continue
            t = _posix(m.group(1), "%Y/%m/%d %H:%M:%S.%f")
            text = b[:-2]
            if m.group(2) == "write":
                w = re.match(r"^#(\d+) (.*)$", text)
                mine = bool(w) and int(w.group(1)) == UNIT[self.d]
                if mine:
                    out.append((t, "write", w.group(2)))
            elif mine:
                out.append((t, "read", text))
        return out

    def written(self):
        return [text for _, kind, text in self.line() if kind == "write"]

    def commands(self):
        return [c for c in self.written() if SWITCHING.match(c)]

    def sim(self):
        pattern = r"%s INFO unit %d: " % (CHAIN[self.d], UNIT[self.d])
        out = []
        for l in sim_log_since(self.sim_mark, pattern):
            m = re.match(r"^(\S+ \S+) ", l)
            out.append((_posix(m.group(1), "%Y-%m-%d %H:%M:%S,%f"), "sim", l.split(pattern)[1]))
        return out

    def timeline(self, title):
        rows = [(t, "IOC -> " if k == "write" else "     <- ", x) for t, k, x in self.line()]
        rows += [(t, "simulator: ", x) for t, _, x in self.sim()]
        rows += [(t, "", x) for t, _, x in self.events if t >= self.t0 - 0.05]
        rows.sort(key=lambda r: r[0])
        t0 = rows[0][0] if rows else 0.0
        text = "\n%s\n" % title + "\n".join("  %+8.3f s  %s%s" % (t - t0, k, x) for t, k, x in rows)
        print(text)
        return rows

    def completion_after(self, t):
        """IOC time of the first completion of ToggleOutput after t (its monitor)."""
        times = [s for s, _, x in self.events if s > t and x.startswith("ToggleOutput = ")]
        return times[0] if times else None


def report(text, capsys):
    with capsys.disabled():
        print(text)


def toggle_state(d):
    return {"VAL": get(d + ":ToggleOutput"), "RVAL": get(d + ":ToggleOutput.RVAL"),
            "SEVR": sevr(d + ":ToggleOutput"),
            "STAT": epics.caget(d + ":ToggleOutput.STAT", as_string=True, timeout=3, use_monitor=False)}


def settle_free(d, timeout=3):
    wait_for(lambda: get(d + ":ToggleOutput.PACT") == 0, timeout, "%s: ToggleOutput free" % d)


def back_off(d):
    """Request off, and the output off by a client's write of ToggleOutput (valid again)."""
    put(d + ":SetToggleOutput", 0)
    time.sleep(0.3)
    if sim_signal(d, "sw") != 0 or sevr(d + ":ToggleOutput") != 0:
        put(d + ":ToggleOutput", 0)
    wait_for(lambda: sim_signal(d, "output") == 0 and sevr(d + ":ToggleOutput") == 0, 3,
             "%s off, ToggleOutput valid" % d)


def prepare(d, on):
    """The supply off (request 0) or on (by its request, as an operator)."""
    back_off(d)
    if on:
        switch(d, True)
        wait_for(lambda: get(d + ":read_output_status") == 1, 6, "%s: SW? read back ON" % d)


# --- 1. the lost write, without and with the rule ---------------------------------------------

CASES = {"off lost during a switch-on": (0, 1, 0), "on lost during a switch-off": (1, 0, 1)}
# name: (output before, start value, value written while busy)


@pytest.mark.parametrize("case", list(CASES))
@pytest.mark.parametrize("d", SUPPLIES)
def test_without_the_rule_the_value_is_stored_and_not_sent(d, case, capsys):
    """_out:resend disabled: the value written into the busy ToggleOutput is in VAL and not sent.
    ToggleOutput shows it with an INVALID alarm (its read-back compare used the stored value),
    RVAL holds the value it sent, the simulator followed the start value only, and nothing more
    is sent for 3 s. Then the rule enabled: it sends the stored value within one evaluation."""
    before, start, lost = CASES[case]
    prepare(d, before)
    n0 = count(d)
    with paused(d), fault(d, "slow", ms=SLOW_MS), Watch(d) as w:
        with rule_disabled(d):
            lost_run(d, start, [lost], w)
            settle_free(d)
            time.sleep(SETTLE)
            state = toggle_state(d)
            out = sim_signal(d, "output")
            sent = w.commands()
            assert sent == ["RST", "SW%d" % start], "precondition, start sent and nothing else: %s" % sent
            assert out == start, "the simulator did not follow the start value"
            assert (state["VAL"], state["RVAL"], state["SEVR"]) == (lost, start, 3), state
            assert count(d) == n0
            t_on = time.time()
            w.mark("_out:resend enabled (DISA 0)")
        wait_for(lambda: sim_signal(d, "output") == lost, EVALUATION + SEND + 0.5,
                 "%s: the stored value sent after the rule was enabled" % d)
        took = time.time() - t_on
        settle_free(d)
        wait_for(lambda: sevr(d + ":ToggleOutput") == 0, 2, "%s: ToggleOutput valid" % d)
        assert w.commands() == ["RST", "SW%d" % start, "RST", "SW%d" % lost], w.commands()
        assert count(d) == n0 + 1
        with capsys.disabled():
            w.timeline("%s, %s, without the rule (enabled at the end):" % (d, case))
            print("  without the rule, %.0f s after the record was free: ToggleOutput VAL %d, "
                  "RVAL %d, %s %s; simulator output %d. Rule enabled: sent after %.2f s"
                  % (SETTLE, state["VAL"], state["RVAL"], state["STAT"],
                     {0: "NO_ALARM", 3: "INVALID"}.get(state["SEVR"], state["SEVR"]), out, took))
    back_off(d)


@pytest.mark.parametrize("case", list(CASES))
@pytest.mark.parametrize("d", SUPPLIES)
def test_with_the_rule_the_stored_value_is_sent(d, case, capsys):
    """The value written into the busy ToggleOutput is sent within one evaluation after the
    record is free (RST, SW and SW? once more), the supply follows, the count goes up by one, and
    ToggleOutput's alarm is gone. Nothing more is sent for 3 s."""
    before, start, lost = CASES[case]
    prepare(d, before)
    n0 = count(d)
    with paused(d), fault(d, "slow", ms=SLOW_MS), Watch(d) as w:
        t_run = time.time()
        lost_run(d, start, [lost], w)
        wait_for(lambda: sim_signal(d, "output") == lost, 0.5 + EVALUATION + SEND + 0.5,
                 "%s: the stored value sent" % d)
        settle_free(d)
        wait_for(lambda: sevr(d + ":ToggleOutput") == 0, 2, "%s: ToggleOutput valid" % d)
        time.sleep(SETTLE)
        state = toggle_state(d)
        line = w.line()
        sent = [x for _, k, x in line if k == "write" and SWITCHING.match(x)]
        assert sent == ["RST", "SW%d" % start, "RST", "SW%d" % lost], sent
        t_free = w.completion_after(t_run)
        t_resend = [t for t, k, x in line if k == "write" and x == "RST"][1]
        assert t_free is not None and 0 < t_resend - t_free <= EVALUATION + 0.05, (t_free, t_resend)
        assert (state["VAL"], state["RVAL"], state["SEVR"]) == (lost, lost, 0), state
        assert sim_signal(d, "output") == lost
        assert count(d) == n0 + 1
        assert get(d + ":read_output_status") == lost
        with capsys.disabled():
            w.timeline("%s, %s, with the rule:" % (d, case))
            print("  sent %.3f s after ToggleOutput was free; count %d -> %d"
                  % (t_resend - t_free, n0, count(d)))
    back_off(d)


# --- 2. several values while busy -----------------------------------------------------------------

@pytest.mark.parametrize("d", SUPPLIES)
def test_several_values_while_busy_the_last_is_sent(d, capsys):
    """A switch-on, and off, on, off written into the busy record: the last (off) is sent, once."""
    prepare(d, False)
    n0 = count(d)
    with paused(d), fault(d, "slow", ms=SLOW_MS), Watch(d) as w:
        lost_run(d, 1, [0, 1, 0], w)
        wait_for(lambda: count(d) == n0 + 1, 0.5 + EVALUATION + 0.5, "%s: counted" % d)
        settle_free(d)
        time.sleep(SETTLE)
        assert w.commands() == ["RST", "SW1", "RST", "SW0"], w.commands()
        assert sim_signal(d, "output") == 0
        assert toggle_state(d)["SEVR"] == 0 and count(d) == n0 + 1
        with capsys.disabled():
            w.timeline("%s, a switch-on, then off, on, off while busy:" % d)
    back_off(d)


@pytest.mark.parametrize("d", SUPPLIES)
def test_values_while_busy_that_end_on_the_value_sent_send_nothing(d, capsys):
    """A switch-on, and off, on written into the busy record: VAL ends equal to what was sent, so
    nothing more is sent, the count does not move, and the read-back compare matched."""
    prepare(d, False)
    n0 = count(d)
    with paused(d), fault(d, "slow", ms=SLOW_MS), Watch(d) as w:
        lost_run(d, 1, [0, 1], w)
        settle_free(d)
        time.sleep(SETTLE)
        assert w.commands() == ["RST", "SW1"], w.commands()
        assert sim_signal(d, "output") == 1
        state = toggle_state(d)
        assert (state["VAL"], state["RVAL"], state["SEVR"]) == (1, 1, 0), state
        assert count(d) == n0
        with capsys.disabled():
            w.timeline("%s, a switch-on, then off, on while busy:" % d)
    back_off(d)


# --- 3. the event path (R5) -----------------------------------------------------------------------

@pytest.mark.parametrize("d", SUPPLIES)
def test_off_by_the_request_during_a_switch_on_goes_out_once(d, capsys):
    """The request on, and off while ToggleOutput is busy with the SW1 (the gate processed by the
    change event, which carries the put flag): EPICS runs ToggleOutput again when it is free
    (RPRO), the rule finds nothing to do. The supply ends off, each command went out once: REN,
    the limit, RST, SW1, then REN, RST, SW0; the count does not move."""
    prepare(d, False)
    n0 = count(d)
    with paused(d), fault(d, "slow", ms=SLOW_MS), Watch(d) as w:
        put(d + ":SetToggleOutput", 1)
        wait_for(lambda: epics.caget(d + ":ToggleOutput.PACT", timeout=1, use_monitor=False) == 1,
                 2, "%s: ToggleOutput busy with the switch-on" % d)
        time.sleep(0.03)                     # the SW1 is on the line
        assert get(d + ":ToggleOutput.PACT") == 1, "the switch-on was over before the off"
        put(d + ":SetToggleOutput", 0)
        settle_free(d)
        wait_for(lambda: sim_signal(d, "output") == 0, 2, "%s off" % d)
        time.sleep(SETTLE)
        sent = w.commands()
        assert len(sent) == 7 and sent[1].startswith("CH1 "), sent
        assert [sent[0]] + sent[2:] == ["REN", "RST", "SW1", "REN", "RST", "SW0"], sent
        assert count(d) == n0
        state = toggle_state(d)
        assert (state["VAL"], state["RVAL"], state["SEVR"]) == (0, 0, 0), state
        with capsys.disabled():
            w.timeline("%s, request on, and off while the SW1 is on the line:" % d)
    back_off(d)


# --- 4. a supply that does not answer (R4) --------------------------------------------------------

@pytest.mark.parametrize("d", SUPPLIES)
def test_a_silent_supply_gets_the_stored_value_once(d, capsys):
    """The supply silent (it neither answers nor executes): a switch-on, and off written while it
    waits for the reply (reply timeout 150 ms and 50 ms wait). The rule sends the off once (it
    times out as well), then nothing for 4 s, the count up by exactly one."""
    prepare(d, False)
    n0 = count(d)
    with paused(d), Watch(d) as w:
        with fault(d, "silent"):
            lost_run(d, 1, [0], w)
            wait_for(lambda: count(d) == n0 + 1, 0.5 + EVALUATION + 0.5, "%s: counted" % d)
            settle_free(d)
            time.sleep(4.0)
            sent = w.commands()
            state = toggle_state(d)
            assert sent == ["RST", "SW1", "RST", "SW0"], sent
            assert count(d) == n0 + 1
            assert (state["VAL"], state["RVAL"], state["SEVR"]) == (0, 0, 3), state
            assert sim_signal(d, "output") == 0
        with capsys.disabled():
            w.timeline("%s, silent: a switch-on, and off while it waits:" % d)
            print("  ToggleOutput %s INVALID after the resend; %d commands in 4 s after it"
                  % (state["STAT"], len(sent) - 4))
    back_off(d)


# --- 5. an IOC restart ----------------------------------------------------------------------------

def test_ioc_restart_counts_stay_zero(capsys):
    """AU-20P7-3 on and REK-1 off, the IOC restarted: after the first contact and GRACE, and 3 s
    more, both counts (_out:resend, _permit:enforce) are 0 and neither supply received a switching
    command (the limit CH1 is sent at the first contact, as today)."""
    on, off = SUPPLIES
    prepare(off, False)
    prepare(on, True)
    mark = sim_log_mark()
    restart_ioc()
    for d in (on, off):
        wait_for(lambda: get(d + ":_init:probe.DISA") == 1 and get(d + ":OutputIntlk.DISA") == 0,
                 30, "%s: first contact and gate enabled" % d)
    time.sleep(SETTLE)
    time.sleep(1.0)                          # the simulator log
    for d in (on, off):
        assert count(d) == 0 and enforced(d) == 0, (d, count(d), enforced(d))
        lines = [l.split("unit %d: " % UNIT[d])[1] for l in
                 sim_log_since(mark, r"%s INFO unit %d: " % (CHAIN[d], UNIT[d]))]
        assert [l for l in lines if SWITCHING.match(l) and not l.startswith("CH1 ")] == [], (d, lines)
    assert sim_signal(on, "output") == 1 and sim_signal(off, "output") == 0
    assert get(on + ":ToggleOutput") == 1 and get(off + ":ToggleOutput") == 0
    report("\nIOC restart with %s on and %s off: _out:resend and _permit:enforce 0 for both, "
           "no switching command sent" % (on, off), capsys)
    back_off(on)


# --- 7. the structure, read from the running IOC ------------------------------------------------

INPUTS = {"INPA": ":ToggleOutput.PACT", "INPB": ":ToggleOutput", "INPC": ":ToggleOutput.RVAL"}


@pytest.mark.parametrize("d", list(POLLED) + [UNPOLLED, "REK-9"])
def test_structure_of_the_resend_record(d):
    """_out:resend as its comment names it: a calcout scanned every 1 s, its inputs NPP database
    links to ToggleOutput's PACT, VAL and RVAL, no delay, On Change, OCAL 1 to ToggleOutput.PROC;
    no alarm, its value the count. ToggleOutput is Passive (an activity input of a periodically
    scanned record would be busy at every evaluation of the same list), has no MASK (RVAL is VAL)
    and no DOL (processing does not change VAL)."""
    r = d + ":_out:resend"
    f = lambda rec, fld: epics.caget("%s.%s" % (rec, fld), as_string=True, timeout=3, use_monitor=False)
    assert f(r, "RTYP") == "calcout"
    assert f(r, "SCAN") == "1 second"
    for fld, target in INPUTS.items():
        assert f(r, fld).split()[:2] == [d + target, "NPP"], (fld, f(r, fld))
    for fld in ("INP" + c for c in "DEFGHIJKL"):
        assert f(r, fld) == "", (fld, f(r, fld))
    assert f(r, "CALC") == "L:=L+(A=0&&B#C);L"
    assert f(r, "OOPT") == "On Change" and f(r, "DOPT") == "Use OCAL"
    assert f(r, "OCAL") == "1" and float(f(r, "ODLY")) == 0.0
    assert f(r, "OUT").split()[:2] == [d + ":ToggleOutput.PROC", "NPP"], f(r, "OUT")
    assert f(r, "IVOA") == "Continue normally" and f(r, "DISA") == "0"
    t = d + ":ToggleOutput"
    assert f(t, "RTYP") == "bo" and f(t, "SCAN") == "Passive"
    assert f(t, "MASK") == "0" and f(t, "DOL") in ("", "0") and f(t, "OMSL") == "supervisory"
    assert sevr(r) == 0
    assert get(r) == get(r + ".L")
